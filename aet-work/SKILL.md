---
name: aet-work
description: Work queue management and sequential task execution. Use when you have plan.md files to run in order, want hands-free task execution, or need to check what's ready. Triggers on "run the queue", "pick next task", "what's next", "what's unblocked", "run all tasks", "keep working", "run tasks", "execute plans", "night shift", "AFK mode", "queue status", "init queue", "what can I work on", "run unblocked tasks".
---

# aet-work

Queue management for agentic engineering. The single job of this skill is to manage the work queue and orchestrate task execution — not to plan, implement, or review.

## When to Use

- You have multiple `docs/plans/*.md` files from a PRD breakdown
- You want to run tasks sequentially without manual intervention
- You want to check what's blocked, what's unblocked, what's done
- You want the "night shift" AFK loop

## Shared Preamble

Before executing any command in this skill, collect the following context:

- `BRANCH` — current git branch
- `REPO_STATE` — clean / dirty / merge-conflict
- `AGENTS_MD` — presence and last-modified date of AGENTS.md
- `LEARNINGS` — top-3 relevant entries from `.agents/learnings.jsonl` (if exists)
- `ACTIVE_PLAN` — any `docs/plans/*.md` modified in last 7 days
- `LAST_PIV` — date of last completed plan-implement-validate cycle (from git log if available)
- `ACTIVE_PRD_STAGE` — current `*Stage:` value from the most-recently-modified `docs/prds/*.md` footer (if exists)
- `ACTIVE_PLAN_STAGE` — current `*Stage:` value from the most-recently-modified `docs/plans/*.md` footer (if exists)

Use this context to ground all recommendations. Do not ask the user to provide it manually.

If a stage is found, print at the start of execution: `"📍 Current stage: {stage}."`

## Forward-Only State Model

Workflow state is **recorded forward by code and trusted on read**.

- **One writer.** `aet-state transition` is the only code path that mutates `tasks[].state`. It validates legality, atomically applies the change, appends a `{from, to, at, by, evidence}` history entry, and updates dependents.
- **Audit off the hot path.** `aet-state audit` reconciles stored state against git ground truth on demand. It is never invoked by `status`, `next`, `run`, or the orchestrator during normal operation.
- **Live / settled partition.** `.agents/work-queue.json` holds only non-terminal tasks. Terminal tasks (`merged`, `abandoned`) are sealed to `.agents/work-history.jsonl` automatically and are never loaded for scheduling.
- **Stage as sub-state.** While a task is `in_progress`, its `stage` field records the pipeline stage (`tdd`, `implement`, `qa`, `review`, `cso`, `sync-docs`). The plan footer `*Stage:*` is a human breadcrumb, not a scheduler input.

## Commands

### Queue Terminal Statuses

The work queue uses the following terminal statuses:

| Status           | Meaning                                                                                                                        | Set by                                |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------- |
| `merged`         | Code is verified on `origin/main`                                                                                              | `post-ship-verify` or `mark-terminal` |
| `merge_verified` | **Legacy alias for `merged`.** Some pipelines historically set this status. Normalized to `merged` by `init-queue` and `sync`. | Orchestrator (legacy)                 |
| `done`           | **Deprecated.** Pipeline completed but not yet verified on main. Treated as terminal for blocker-resolution purposes.          | Orchestrator (legacy)                 |
| `abandoned`      | Task explicitly cancelled with a documented reason                                                                             | `mark-terminal`                       |
| `failed`         | Pipeline failed; requires human inspection                                                                                     | Orchestrator                          |

New tasks should reach `merged` or `abandoned`. `done` and `merge_verified` are retained for backwards compatibility and normalized to `merged` during queue sync.

### `init-queue`

Rebuild `.agents/work-queue.json` from `docs/plans/*.md`. Use this after a major reorganization or when creating the queue for the first time.

**Procedure:**

1. Scan `docs/plans/` for atomic, implementable task plans. Roadmaps, audits, and meta-plans belong in `docs/roadmaps/` or `docs/audits/` and are ignored.
2. If `.agents/work-queue.json` exists, load it as `existing_queue`.
3. For each plan.md, extract title, task ID (from filename or frontmatter), and blocking relationships.
4. Build the DAG as `blocked_by` and `blocks` arrays.
5. For each plan:
   - If its `plan_file` exists in `existing_queue`, preserve `branch`, `worktree`, `merge_commit`, `completed_at`, `merged_at`, and terminal `status`.
   - **Normalize legacy status:** if an existing task has `status: "merge_verified"`, rewrite it to `status: "merged"`.
   - If new or non-terminal, set `status: "planned"` and clear execution metadata.
6. Set `source_prd` to the most recent PRD in `docs/prds/` (if any).
7. Set `queue_updated_at` to the current ISO-8601 timestamp.
8. Write `.agents/work-queue.json`.

`init-queue` does **not** call `aet-state audit` or promote tasks to `ready`.

### `sync`

Append-only sync of `docs/plans/*.md` into the existing queue. Implemented by `aet-work/bin/sync`. Use this after adding new plan files.

**Procedure:**

1. Read `.agents/work-queue.json` if it exists; otherwise treat it as empty.
2. Read `.agents/work-history.jsonl` and collect settled `plan_file` paths and task IDs.
3. Scan `docs/plans/` for all `*.md` files.
4. For each plan whose `plan_file` is not already in the queue:
   - **Settled-history deduplication:** skip if its `plan_file` or task ID is already settled.
   - **Validate intake contract on candidates only:** run fail-closed intake validation (frontmatter, size, atomicity, legacy sections) only on plans that are actually candidates to be added. Already-queued plans are preserved as-is.
   - **Validate size:** skip plans that exceed the complexity limit unless they contain `⚠️ ATOMIC OVERSIZED` (set `oversized: true` if allowed).
   - **Validate atomicity:** skip plans that reference other plan files or contain multiple "Phase" sections.
   - Append a new task with `status: "planned"`.
5. Recompute `blocks` for the entire queue.
6. **Normalize legacy status:** rewrite `merge_verified` to `merged`.
7. Report any queue entry whose `plan_file` is missing as drift; do **not** mutate the stored status.
8. Update `queue_updated_at` and write `.agents/work-queue.json`.

`sync` does **not** call `aet-state audit` or promote dependents.

### `status`

Show the current state of the work queue.

**Procedure:**

Invoke the status helper, which runs a settled-history-aware `plan-drift` check, reads stored state, and prints the summary:

```bash
python3 ~/.claude/skills/aet-work/bin/status \
  --queue-file .agents/work-queue.json \
  --history-file .agents/work-history.jsonl \
  --plans-dir docs/plans
```

The helper reports:

1. Any plan drift (plans on disk that are neither queued nor settled)
2. Active task counts: `planned`, `unblocked`, `blocked`, `in-progress`, `failed`, `done` (counts are a projection of stored `state`; `failed` is read from stored state)
3. The stored `state` for each active task
4. The next 3 tasks whose stored state is `ready`
5. Any failed tasks (from stored state)
6. Stale worktree warnings

### `next`

Identify and output the next ready task.

**Procedure:**

1. Run the `plan-drift` check. If drift is detected, refuse to pick a task and instruct the user to run `init-queue` first
2. Read `.agents/work-queue.json`
3. Find tasks whose stored `state` is `ready` (falling back to legacy `status` during migration)
4. Pick the first in topological order (respecting the DAG)
5. Output: task ID, title, plan_file path
6. Transition to `in_progress` via `python3 ~/.claude/skills/aet-work/bin/aet-state transition <task_id> <current_state> in_progress .agents/work-queue.json`, then record `branch: <task_id>` and `worktree: .worktrees/<task_id>`

### `run`

AFK loop with OS-level process isolation and parallel execution. Invokes the centralized `aet-work/bin/orchestrator` Python script, which spawns fresh agent sessions per pipeline stage. Independent tasks execute simultaneously—each in its own git worktree—up to a configurable concurrency cap. Context leakage between skills is eliminated by session isolation.

**Procedure:**

1. **Plan-drift guard:** Run the `plan-drift` check. If drift is detected, refuse to start the AFK loop and instruct the user to run `init-queue` first

2. **Pre-branch git hygiene:**

   Before spawning the first task, the orchestrator ensures `main` is clean and synchronized with `origin/main`. If `main` is dirty, ahead, or behind, the orchestrator prints actionable warnings and halts before creating any worktrees. In unattended mode, warnings are logged but the loop continues.

3. **Invoke the unified orchestrator:**

   Background the orchestrator with shell redirection so the launching shell
   observes its true exit status; do not pipe through `tee` without `set -o
pipefail`:

   ```bash
   ~/.claude/skills/aet-work/bin/orchestrator \
     --queue-file .agents/work-queue.json \
     --repo-root . \
     --cli-bin $(which kimi) \
     --isolation standard \
     --max-jobs 4 \
     > aet-work.log 2>&1 &
   ```

   The orchestrator handles CLI detection, worktree management, parallel execution, and stage advancement automatically.

4. **Concurrency cap:**

   - Default: `4` jobs (override with `AET_WORK_JOBS` env var), hard cap at 8
   - Override: set `AET_WORK_JOBS` environment variable
   - The orchestrator never exceeds the cap to prevent resource exhaustion

5. **Resume behavior:**
   - Re-running `run` resumes from the current queue state
   - Already-done or in-progress tasks with existing worktrees are skipped automatically

**Context isolation mechanism:**

```
Parent agent session (clean)
  → invokes aet-work/bin/orchestrator
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

**Unattended mode:** The orchestrator sets `AET_EXECUTION_MODE=unattended` in the environment of every spawned subagent. Skills that have interactive approval gates (e.g., `aet-implement`) detect this variable and skip gates that require human input, logging the bypass for auditability. See `references/context-isolation.md` for details.

### `run-one`

Run the full pipeline on a single plan with session-isolated stages. Replaces the manual multi-skill pipeline workflow.

**Procedure:**

1. Accept a plan file path: `aet-work run-one docs/plans/FEAT-001-plan.md`
2. Invoke the orchestrator in single-plan mode:

   ```bash
   ~/.claude/skills/aet-work/bin/orchestrator \
     --plan-file docs/plans/FEAT-001-plan.md \
     --repo-root . \
     --cli-bin $(which kimi) \
     --isolation standard \
     > aet-work-run-one.log 2>&1 &
   ```

3. The orchestrator advances the plan through all stage groups sequentially.
4. On completion, the branch is ready for `aet-ship`.

**Queue bookkeeping:** When the plan file corresponds to a task already tracked in `.agents/work-queue.json`, `run-one` records the task's `branch` and `worktree`, transitions it to `in_progress` at the start of the run, and transitions it to `awaiting_merge` on success. This lets `aet-state record-merge` resolve the merge commit automatically after the PR ships. If the plan is not in the queue, or if `run-one` was spawned by `run` (`AET_TASK_ID` is set), the queue is left unchanged.

**When to use:** For one-off plans where you want the full pipeline but don't need a queue.

### Worktree dependency warmup

The orchestrator can automatically symlink heavy dependency directories from the main worktree into each new task worktree. This avoids reinstalling dependencies (e.g. `node_modules`, `vendor`) on every stage.

Configure it in `.agents/aet-work.json`:

```json
{
  "symlink_dependencies": [
    {
      "name": "node_modules",
      "source": "app/node_modules",
      "target": "app/node_modules"
    },
    { "name": "vendor", "source": "api/vendor", "target": "api/vendor" }
  ]
}
```

- `source` is relative to the repository root.
- `target` is relative to the new worktree root.
- Missing target parents are created automatically.
- If the source is missing, the orchestrator emits an `environment_issue` telemetry event instead of failing the task.

### `audit`

Reconcile stored state against git ground truth without mutating the queue. `audit` is a human-run diagnostic; it is never called during normal operation.

**Procedure:**

1. Run `python3 ~/.claude/skills/aet-work/bin/aet-state audit .agents/work-queue.json`
2. For each task, compute the expected status from git ground truth in order:
   - `merged` — `branch` or `merge_commit` is an ancestor of `origin/main`
   - `in-progress` — local `branch` exists
   - `unblocked` — `plan_file` exists, no local branch, and every task in `blocked_by` is terminal (`merged` or `abandoned`)
   - `blocked` — `plan_file` exists, no local branch, and some blocker is not terminal
   - `drift` — `plan_file` is missing
3. Compare stored `state` against the expected status for each task
4. Report any discrepancies (e.g., `⚠️ Task {id} stored as awaiting_merge but expected in-progress from git`)
5. Return a JSON object showing `stored`, `expected`, and `discrepancy` for every task

**When to use:** When you suspect the stored queue state has drifted from git reality (e.g., after manual branch cleanup, a crash, or an external merge). Do not rely on `audit` during normal operation; `status`, `next`, and `run` read stored state directly.

### `report`

Print an execution telemetry summary from `.agents/execution.log.jsonl`.

**Procedure:**

1. Run `python3 ~/.claude/skills/aet-work/bin/report`
2. The helper reads `.agents/execution.log.jsonl` and prints:
   - Total runs
   - Tasks spawned, succeeded, and failed
   - Total wall-clock time
   - Average isolation level observed across stage records
3. Use `--since <ISO-8601-timestamp>` to restrict the summary to recent runs

**When to use:** After one or more orchestrator runs to inspect throughput, failure rate, and resource usage.

### `plan-drift`

Detect plan files that exist on disk but are not represented in the active work queue.

**Procedure:**

1. Read `.agents/work-queue.json` and collect all `plan_file` paths
2. Read `.agents/work-history.jsonl` and collect all settled `plan_file` paths
3. List all `docs/plans/*.md` files. Only atomic plans in this directory are considered; roadmaps and audits stored elsewhere are ignored.
4. Identify any plan files whose path is not found in the queue's `plan_file` set **and** not found in the settled history's `plan_file` set
5. Compare the most recent modification time of any `docs/plans/*.md` against the `queue_updated_at` field (or the queue file's mtime as fallback)
6. Report findings:
   - Orphaned plans: print each filename and `⚠️ Plan drift detected: N plan file(s) not in queue. Run init-queue to sync.`
   - Stale queue: if plans are newer than the queue, print `⚠️ Queue is stale (plans modified after last init-queue). Run init-queue to sync.`
   - If none: print `✅ No plan drift detected. All plans are tracked in the queue.`

`plan-drift` checks only the active queue. Settled tasks are ignored; their plan files may still exist on disk but are no longer tracked as active work.

### `drift-check`

Detect tasks marked `done` or `merged` whose commits are not on `origin/main`.

**Procedure:**

1. Read `.agents/work-queue.json`
2. Run `git fetch origin`
3. For each task with status `done`, `merged`, or `merge_verified`:
   a. If `merge_commit` is set and `git merge-base --is-ancestor <merge_commit> origin/main` passes, skip (verified)
   b. If `branch` is set, run `git merge-base --is-ancestor <branch> origin/main`. If it fails, record as drifted
   c. If neither `merge_commit` nor `branch` is available, record as unverifiable
4. Report findings:
   - Drifted tasks: print task ID, title, and branch name
   - Unverifiable tasks: print task ID and note missing metadata
   - If none: print `✅ No drift detected. All done/merged tasks are on origin/main.`

### `mark-terminal`

Mark a task as `merged` or `abandoned`. This is the only supported way to set a terminal status manually. Uses the centralized `aet-state` helper for legality validation and atomic updates.

**Procedure:**

1. Read `.agents/work-queue.json` to determine the task's current status
2. Find the task by ID
3. If the requested status is `merge_verified`:
   - STOP and print: `⛔ merge_verified is a legacy status. Use merged instead.`
4. If setting to `merged`:
   - Run `python3 ~/.claude/skills/aet-work/bin/aet-state validate <task_id> <current_status> merged .agents/work-queue.json`
   - If validation fails, STOP and print the error message
   - If validation passes, run `python3 ~/.claude/skills/aet-work/bin/aet-state transition <task_id> <current_status> merged .agents/work-queue.json`
5. If setting to `abandoned`:
   - Require a `reason` argument (non-empty string)
   - Run `python3 ~/.claude/skills/aet-work/bin/aet-state transition <task_id> <current_status> abandoned .agents/work-queue.json --reason="<reason>"`
   - Print: `⚠️ Task {id} marked abandoned. Reason: {reason}`

**Rules:**

- Never mark a task `merged` without verifying its merge_commit is on origin/main
- Never mark a task `done` manually; use `merged` (if on main) or `abandoned` (if cancelled)
- Never mark a task `merge_verified`; it is normalized automatically to `merged`
- Always use `aet-state transition` instead of direct JSON mutation

### `cleanup`

Seal terminal tasks and remove their worktrees atomically. Repairs stale queue entries.

**Procedure:**

1. Run `python3 ~/.claude/skills/aet-work/bin/aet-state audit .agents/work-queue.json` to reconcile stored state against git for active (non-terminal) tasks only.
2. Read `.agents/work-queue.json`
3. Identify terminal tasks: status is `merged`, `done`, or `abandoned`. Normalize any `merge_verified` statuses to `merged`.
4. Seal any legacy terminal tasks still present in the live queue:

   ```bash
   python3 ~/.claude/skills/aet-work/bin/aet-state archive .agents/work-queue.json
   ```

   Terminal transitions now seal tasks to `.agents/work-history.jsonl` automatically. The deprecated `archive` command remains as a migration helper that seals any remaining terminal tasks and reports what it did.

5. **Atomicity:** If sealing fails, STOP. Do not remove any worktrees. Investigate the failure and re-run `cleanup`.
6. Remove worktrees for archived tasks:

   ```bash
   git worktree remove .worktrees/<task-id>
   # If it refuses due to uncommitted changes, inspect first:
   # git -C .worktrees/<task-id> status
   # Then force-remove if safe: git worktree remove --force .worktrees/<task-id>
   ```

7. **Stale worktree repair (universal):** For each remaining task with a `worktree` field, regardless of status:
   - If the directory does not exist, clear `worktree: null` via `aet-state transition` (or direct JSON update if the task status is unchanged) and print `Repaired stale worktree field for {task_id}`
   - If the directory exists but has 0 commits ahead of main (`git rev-list --count main..HEAD` in the worktree returns 0), remove the worktree and clear `worktree: null`
8. Report archived, removed, repaired, and remaining worktrees

For the full one-time upgrade procedure for older projects that predate the forward-only state model, see [`references/upgrading-existing-project.md`](references/upgrading-existing-project.md).

## Key Principles

- **Queue-unaware pipeline** — individual skills (aet-tdd, aet-implement, aet-qa, etc.) know nothing about the queue. The orchestrator checks results and updates the queue.
- **OS-process isolation** — `run` invokes the unified orchestrator, which spawns fresh OS processes for each pipeline stage. See `references/context-isolation.md` for details.
- **Agent-agnostic** — uses only git commands and generic session language; no tool-specific APIs.
- **Queue file is the memory** — `.agents/work-queue.json` persists state across process boundaries by design.
- **Stored state, explicit audit** — `status`, `next`, and `run` read the recorded `state` field directly. `aet-state audit` reconciles stored state against git for human review, but never runs during normal operation.
- **Live / settled partition** — the live queue holds only non-terminal tasks; terminal tasks are sealed to `.agents/work-history.jsonl` automatically.
- **Stage as sub-state** — pipeline progress is recorded in the task record's `stage` field while `state == in_progress`, not inferred from plan footers.
- **Execution telemetry** — `.agents/execution.log.jsonl` is an append-only record of stage and run-summary events produced by the orchestrator. Use `aet-work report` to summarize it.
- **Worktree isolation** — each task gets its own branch; branches persist for independent review and PR.
- **Drain on failure** — running tasks finish, new spawns halt. Preserves in-progress work while stopping the pipeline.
