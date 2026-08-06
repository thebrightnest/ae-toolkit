# aet-work Command Reference

Detailed procedures for `aet` commands. The skill file describes the mental model; this file describes the mechanics.

## `backlog add`

Put a plan on the board. This is the entry point for making a plan visible in GitHub Issues.

**Procedure:**

1. Resolve `<plan>` to a plan file in `docs/plans/` (by path or by id).
2. Refuse if the plan's `status` is not `draft` or `approved`.
3. Commit and push the plan's status (draft stays draft; approved stays approved).
4. Call the configured projection to create exactly one issue keyed by plan id, labeled:
   - `aet:draft` for `status: draft`
   - `aet:backlog` for `status: approved`
5. If the issue already exists — because the command was re-run or run from a second clone — reconcile its label instead of creating a duplicate.

**Fail semantics:**

- Plan resolution and the status commit fail closed (the command exits non-zero).
- Projection failures warn on stderr but do not fail the command or roll back the commit (R-4).

**When to use:** After `aet-pipeline-plan` produces a plan file and you want it visible on the backlog board.

## `sprint add`

Promote an approved plan into the runnable sprint.

**Procedure:**

1. Resolve `<plan>` to a plan file in `docs/plans/` (by path or by id).
2. Validate the plan and refuse unless its stage is `plan-approved`.
3. Set `status: queued` in the plan frontmatter. No commit or push happens at intake; plan durability is deferred to the PR closure.
4. Add the task to `.agents/work-queue.json`, computing `ready` or `blocked` from `blocked_by`.
5. Call the configured projection to relabel the issue to `aet:ready` or `aet:blocked`.

**When to use:** When you deliberately choose to work on an approved plan now. This is the only human scheduling act in the loop.

## `run`

AFK loop with OS-level process isolation and parallel execution. Invokes the orchestrator, which spawns fresh agent sessions per pipeline stage. Independent tasks execute simultaneously—each in its own git worktree—up to a configurable concurrency cap. Context leakage between skills is eliminated by session isolation.

**Procedure:**

1. **Plan-drift warning:** Run the `plan-drift` check and print an informational warning if drift is detected; do **not** refuse to start the AFK loop.

2. **Pre-branch git hygiene:**

   Before spawning the first task, the orchestrator ensures the trunk branch is clean and synchronized with its remote tracking branch. If the trunk has dirty non-plan paths, is behind its remote, or is ahead with any non-plan changes, the orchestrator prints an actionable reason and halts before creating any worktrees. Trunk hygiene is a mechanical durability hard-stop: the loop halts in unattended mode too (ADR-027). Mutations to `.agents/work-queue.json` and `.agents/work-history.jsonl` are ignored by the dirty check because the orchestrator writes them as part of normal operation; the `.agents/work-queue.json.lock` and `.agents/work-queue.lease` sidecars are ignored too — they linger on disk by design (the lock file is never unlinked; the lease self-reclaims on the next mutation after a crash). Untracked or modified `docs/plans/*.md` files are also ignored at intake: mid-sprint plan status is local-only until a terminal transition (merged/abandoned) commits it (ADR-054). Operators must treat untracked plans as load-bearing — `git clean -fdx` or git-following backups can discard in-flight work.

3. **Invoke the detached orchestrator:**

   Run the command as a normal foreground invocation. It spawns the orchestrator in its own detached session, prints the run ID, log path, and follow command, and returns immediately:

   ```bash
   aet run
   ```

   The orchestrator handles CLI detection, worktree management, parallel execution, and stage advancement automatically.

   **Failure handling:** `--on-failure={triage|continue|halt}` (default `triage`). `triage` spawns a cheap triage session that decides whether to requeue a transient failure or quarantine a design defect; `continue` marks the task failed and keeps spawning new tasks; `halt` stops the shift on the first failure.

4. **Observe a running batch:**

   To wait for an already-spawned run to finish and print a bounded completion report:

   ```bash
   aet run --follow <run-id>
   ```

   `--follow` does **not** tail or stream the run log; it waits silently and emits the same fixed-shape report that `run-one` prints.

5. **Concurrency cap:**

   - Default: `4` parallel tasks
   - Override: `aet run --max-jobs <n>` (accepted values: `1`–`8`)
   - The orchestrator never exceeds the cap to prevent resource exhaustion

6. **Resume behavior:**
   - Re-running `run` resumes from the current queue state
   - Already-done or in-progress tasks with existing worktrees are skipped automatically

**Context isolation mechanism:**

```
Parent agent session (clean)
  → invokes aet run
  → Orchestrator spawns Stage 1 session (clean context, worktree A)
    → TDD + Implement + QA run in one isolated session
  → Orchestrator spawns Stage 2 session (clean context, worktree A)
    → Review runs with no implementation context
  → Orchestrator spawns Stage 3 session (clean context, worktree A)
    → CSO + Sync-docs run with no review bias
  → … up to concurrency cap for parallel tasks
  → Orchestrator returns
  → Parent session remains clean
```

**Unattended mode:** The orchestrator sets `AET_EXECUTION_MODE=unattended` in the environment of every spawned subagent. Skills that have interactive approval gates (e.g., `aet-implement`) detect this variable and skip gates that require human input, logging the bypass for auditability. See [`context-isolation.md`](context-isolation.md) for details.

## `run-one`

Run the full pipeline on a single plan with session-isolated stages. Replaces the manual multi-skill pipeline workflow.

**Procedure:**

1. Accept a plan file path or task id: `aet run-one docs/plans/FEAT-001-plan.md` or `aet run-one FEAT-001`
2. Invoke the orchestrator in single-plan mode:

   ```bash
   aet run-one docs/plans/FEAT-001-plan.md
   ```

3. The command spawns the orchestrator in a detached process and **blocks** until the run reaches a terminal state.
4. The command exits with the run's exit code and prints a bounded completion report.
5. Telemetry is written to `~/.aet/telemetry/{project-slug}/{date}/{run-id}/` and the path is printed on completion.
6. On completion, the branch is ready for `aet-ship`.

**Queue bookkeeping:** When the plan file corresponds to a task already tracked in `.agents/work-queue.json`, `run-one` records the task's `branch` and `worktree`, transitions it to `in_progress` at the start of the run, and transitions it to `awaiting_merge` on success. This lets `aet state record-merge` resolve the merge commit automatically after the PR ships. If the plan is not in the queue, or if `run-one` was spawned by `run` (`AET_TASK_ID` is set), the queue is left unchanged.

**When to use:** For one-off plans where you want the full pipeline but don't need a queue.

## Cleanup

Seal terminal tasks and remove their worktrees atomically. Repairs stale queue entries.

**Procedure:**

1. Run `aet state audit .agents/work-queue.json` to reconcile stored state against git for active (non-terminal) tasks only.
2. Read `.agents/work-queue.json`
3. Identify terminal tasks: status is `merged`, `done`, or `abandoned`. Normalize any `merge_verified` statuses to `merged`.
4. Seal any legacy terminal tasks still present in the live queue:

   ```bash
   aet state heal --apply .agents/work-queue.json
   ```

   Terminal transitions now seal tasks to `.agents/work-history.jsonl` automatically. `aet state heal --apply` seals any remaining terminal tasks and reports what it did.

5. **Atomicity:** If sealing fails, STOP. Do not remove any worktrees. Investigate the failure and re-run `aet state heal --apply`.
6. Remove worktrees for archived tasks:

   ```bash
   git worktree remove .worktrees/<task-id>
   # If it refuses due to uncommitted changes, inspect first:
   # git -C .worktrees/<task-id> status
   # Then force-remove if safe: git worktree remove --force .worktrees/<task-id>
   ```

7. **Stale worktree repair (universal):** For each remaining task with a `worktree` field, regardless of status:
   - If the directory does not exist, clear `worktree: null` via `aet state transition` (or direct JSON update if the task status is unchanged) and print `Repaired stale worktree field for {task_id}`
   - If the directory exists but has 0 commits ahead of trunk (`git rev-list --count <trunk>..HEAD` in the worktree returns 0), remove the worktree and clear `worktree: null`
8. Report archived, removed, repaired, and remaining worktrees

For the full one-time upgrade procedure for older projects that predate the forward-only state model, see [`upgrading-existing-project.md`](upgrading-existing-project.md).

## `audit`

Reconcile stored state against git ground truth without mutating the queue. `audit` is a human-run diagnostic; it is never called during normal operation.

**Procedure:**

1. Run `aet state audit .agents/work-queue.json`
2. For each task, compute the expected status from git ground truth in order:
   - `merged` — `branch` or `merge_commit` is an ancestor of the resolved trunk branch
   - `in-progress` — local `branch` exists
   - `unblocked` — `plan_file` exists, no local branch, and every task in `blocked_by` is terminal (`merged` or `abandoned`)
   - `blocked` — `plan_file` exists, no local branch, and some blocker is not terminal
   - `drift` — `plan_file` is missing
3. Compare stored `state` against the expected status for each task
4. Report any discrepancies (e.g., `⚠️ Task {id} stored as awaiting_merge but expected in-progress from git`)
5. Return a JSON object showing `stored`, `expected`, and `discrepancy` for every task

**When to use:** When you suspect the stored queue state has drifted from git reality (e.g., after manual branch cleanup, a crash, or an external merge). Do not rely on `audit` during normal operation; `status`, `next`, and `run` read stored state directly.

## `report`

Print an execution telemetry summary from the archive.

**Procedure:**

1. Run `aet report`
2. The helper scans `~/.aet/telemetry/{project-slug}/` and prints:
   - Total runs
   - Tasks spawned, succeeded, and failed
   - Total wall-clock time
   - Average isolation level observed across stage records
3. Use `--since <ISO-8601-timestamp>` to restrict the summary to recent runs
4. Use `--run-dir <path>` to summarize a single run
5. Use `--task-log <path>` to summarize a single task

**When to use:** After one or more orchestrator runs to inspect throughput, failure rate, and resource usage.

## Plan-drift detection

Detect plan files that exist on disk but are not represented in the active work queue.

**Procedure:**

1. Read `.agents/work-queue.json` and collect all `plan_file` paths
2. Read `.agents/work-history.jsonl` and collect all settled `plan_file` paths
3. List all `docs/plans/*.md` files. Only atomic plans in this directory are considered; roadmaps and audits stored elsewhere are ignored.
4. Identify any plan files whose path is not found in the queue's `plan_file` set **and** not found in the settled history's `plan_file` set
5. Compare the most recent modification time of any `docs/plans/*.md` against the `queue_updated_at` field (or the queue file's mtime as fallback)
6. Report findings:
   - Orphaned plans: print each filename and `⚠️ Plan drift detected: N plan file(s) not in queue. Run aet init-queue to sync.`
   - Stale queue: if plans are newer than the queue, print `⚠️ Queue is stale (plans modified after last init-queue). Run aet init-queue to sync.`
   - If none: print `✅ No plan drift detected. All plans are tracked in the queue.`

Plan-drift detection checks only the active queue. Settled tasks are ignored; their plan files may still exist on disk but are no longer tracked as active work.

## Drift check

Detect tasks marked `done` or `merged` whose commits are not on the resolved trunk branch.

**Procedure:**

1. Read `.agents/work-queue.json`
2. Run `git fetch origin`
3. For each task with status `done`, `merged`, or `merge_verified`:
   a. If `merge_commit` is set and `git merge-base --is-ancestor <merge_commit> <trunk>` passes, skip (verified)
   b. If `branch` is set, run `git merge-base --is-ancestor <branch> <trunk>`. If it fails, record as drifted
   c. If neither `merge_commit` nor `branch` is available, record as unverifiable
4. Report findings:
   - Drifted tasks: print task ID, title, and branch name
   - Unverifiable tasks: print task ID and note missing metadata
   - If none: print `✅ No drift detected. All done/merged tasks are on <trunk>.`

## Marking tasks terminal

Mark a task as `merged` or `abandoned`. This is the only supported way to set a terminal status manually. Uses the centralized `aet state` helper for legality validation and atomic updates.

**Procedure:**

1. Read `.agents/work-queue.json` to determine the task's current status
2. Find the task by ID
3. If the requested status is `merge_verified`:
   - STOP and print: `⛔ merge_verified is a legacy status. Use merged instead.`
4. If setting to `merged`:
   - Run `aet state validate <task_id> <current_status> merged .agents/work-queue.json`
   - If validation fails, STOP and print the error message
   - If validation passes, run `aet state transition <task_id> <current_status> merged .agents/work-queue.json`
5. If setting to `abandoned`:
   - Require a `reason` argument (non-empty string)
   - Run `aet state transition <task_id> <current_status> abandoned .agents/work-queue.json --reason="<reason>"`
   - Print: `⚠️ Task {id} marked abandoned. Reason: {reason}`

**Rules:**

- Never mark a task `merged` without verifying its merge_commit is on the resolved trunk branch
- Never mark a task `done` manually; use `merged` (if on trunk) or `abandoned` (if cancelled)
- Never mark a task `merge_verified`; it is normalized automatically to `merged`
- Always use `aet state transition` instead of direct JSON mutation
