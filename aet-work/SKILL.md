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

`init-queue` does **not** call `aet-state derive` or promote tasks to `unblocked`.

### `sync`

Append-only sync of `docs/plans/*.md` into the existing queue. Implemented by `aet-work/bin/sync`. Use this after adding new plan files.

**Procedure:**

1. Read `.agents/work-queue.json` if it exists; otherwise treat it as empty.
2. Read `.agents/work-archive.json` and collect archived `plan_file` paths and task IDs.
3. Scan `docs/plans/` for all `*.md` files.
4. For each plan whose `plan_file` is not already in the queue:
   - **Archive deduplication:** skip if its `plan_file` or task ID is already archived.
   - **Validate size:** skip plans that exceed the complexity limit unless they contain `⚠️ ATOMIC OVERSIZED` (set `oversized: true` if allowed).
   - **Validate atomicity:** skip plans that reference other plan files or contain multiple "Phase" sections.
   - Append a new task with `status: "planned"`.
5. Recompute `blocks` for the entire queue.
6. **Normalize legacy status:** rewrite `merge_verified` to `merged`.
7. Report any queue entry whose `plan_file` is missing as drift; do **not** mutate the stored status.
8. Update `queue_updated_at` and write `.agents/work-queue.json`.

`sync` does **not** call `aet-state derive` or promote dependents.

### `status`

Show the current state of the work queue.

**Procedure:**

Invoke the status helper, which runs an archive-aware `plan-drift` check, derives ground-truth statuses, and prints the summary:

```bash
python3 ~/.claude/skills/aet-work/bin/status \
  --queue-file .agents/work-queue.json \
  --archive-file .agents/work-archive.json \
  --plans-dir docs/plans
```

The helper reports:

1. Any plan drift (plans on disk that are neither queued nor archived)
2. Active task counts: `unblocked`, `blocked`, `in-progress`, `failed`, `done` (counts are computed from derived status; `failed` is read from stored status)
3. A derived-status column for each active task, highlighting only derive-time warnings (e.g., `done` without merge verification), not ordinary stored-vs-derived mismatches
4. The next 3 tasks whose derived status is `unblocked`
5. Any failed tasks (from stored status)
6. Stale worktree warnings

### `next`

Identify and output the next unblocked task.

**Procedure:**

1. Run the `plan-drift` check. If drift is detected, refuse to pick a task and instruct the user to run `init-queue` first
2. Run `python3 ~/.claude/skills/aet-work/bin/aet-state derive .agents/work-queue.json` to get ground-truth statuses
3. Read `.agents/work-queue.json`
4. Find tasks whose **derived** status is `unblocked` (do not rely on the stored `status` field)
5. Pick the first in topological order (respecting the DAG)
6. Output: task ID, title, plan_file path
7. Update status to `in-progress` via `python3 ~/.claude/skills/aet-work/bin/aet-state transition <task_id> <current_status> in-progress .agents/work-queue.json`, then record `branch: <task_id>` and `worktree: .worktrees/<task_id>`

### `run`

AFK loop with OS-level process isolation and parallel execution. Invokes the centralized `aet-work/bin/orchestrator` Python script, which spawns fresh agent sessions per pipeline stage. Independent tasks execute simultaneously—each in its own git worktree—up to a configurable concurrency cap. Context leakage between skills is eliminated by session isolation.

**Procedure:**

1. **Plan-drift guard:** Run the `plan-drift` check. If drift is detected, refuse to start the AFK loop and instruct the user to run `init-queue` first

2. **Pre-branch git hygiene:**

   Before spawning the first task, the orchestrator ensures `main` is clean and synchronized with `origin/main`. If `main` is dirty, ahead, or behind, the orchestrator prints actionable warnings and halts before creating any worktrees. In unattended mode, warnings are logged but the loop continues.

3. **Invoke the unified orchestrator:**

   ```bash
   ~/.claude/skills/aet-work/bin/orchestrator \
     --queue-file .agents/work-queue.json \
     --repo-root . \
     --cli-bin $(which kimi) \
     --isolation standard \
     --max-jobs 4
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
     --isolation standard
   ```

3. The orchestrator advances the plan through all stage groups sequentially.
4. On completion, the branch is ready for `aet-ship`.

**When to use:** For one-off plans where you want the full pipeline but don't need a queue.

### `derive`

Recompute all actionable status fields from ground truth (git, filesystem, and `blocked_by`) using the centralized `aet-state` helper. `derive` is the single source of truth for whether a task is pickable.

**Procedure:**

1. Run `python3 ~/.claude/skills/aet-work/bin/aet-state derive .agents/work-queue.json`
2. For each task, the derived status is computed in order:
   - `merged` — `branch` or `merge_commit` is an ancestor of `origin/main`
   - `in-progress` — local `branch` exists
   - `unblocked` — `plan_file` exists, no local branch, and every task in `blocked_by` is terminal (`merged` or `abandoned`)
   - `blocked` — `plan_file` exists, no local branch, and some blocker is not terminal
   - `drift` — `plan_file` is missing
3. Compare derived status against stored `status` for each task
4. Report any mismatches as warnings (e.g., `⚠️ Task {id} stored as done but derived as in-progress`)
5. Return the derived JSON for use by other commands

**When to use:** Before any command that reads queue status (`status`, `next`, `run`), and after any sync or initialization. Do not rely on `sync` or `init-queue` to promote tasks to `unblocked`; derive that state on read instead.

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
2. Read `.agents/work-archive.json` and collect all archived `plan_file` paths (archive uses dict-wrapper format `{"archived_at": "...", "tasks": [...]}`)
3. List all `docs/plans/*.md` files. Only atomic plans in this directory are considered; roadmaps and audits stored elsewhere are ignored.
4. Identify any plan files whose path is not found in the queue's `plan_file` set **and** not found in the archive's `plan_file` set
5. Compare the most recent modification time of any `docs/plans/*.md` against the `queue_updated_at` field (or the queue file's mtime as fallback)
6. Report findings:
   - Orphaned plans: print each filename and `⚠️ Plan drift detected: N plan file(s) not in queue. Run init-queue to sync.`
   - Stale queue: if plans are newer than the queue, print `⚠️ Queue is stale (plans modified after last init-queue). Run init-queue to sync.`
   - If none: print `✅ No plan drift detected. All plans are tracked in the queue.`

`plan-drift` checks only the active queue. Archived tasks are ignored; their plan files may still exist on disk but are no longer tracked as active work.

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

Archive terminal tasks and remove their worktrees atomically. Repairs stale queue entries.

**Procedure:**

1. Run `python3 ~/.claude/skills/aet-work/bin/aet-state derive .agents/work-queue.json` to get ground-truth statuses for active (non-terminal) tasks only.
2. Read `.agents/work-queue.json`
3. Identify terminal tasks: status is `merged`, `done`, or `abandoned`. Normalize any `merge_verified` statuses to `merged`.
4. Archive terminal tasks without active dependents:

   ```bash
   python3 ~/.claude/skills/aet-work/bin/aet-state archive .agents/work-queue.json .agents/work-archive.json
   ```

   This appends eligible terminal tasks to `.agents/work-archive.json` and removes them from `.agents/work-queue.json`.

5. **Atomicity:** If archiving fails, STOP. Do not remove any worktrees. Investigate the failure and re-run `cleanup`.
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

## Key Principles

- **Queue-unaware pipeline** — individual skills (aet-tdd, aet-implement, aet-qa, etc.) know nothing about the queue. The orchestrator checks results and updates the queue.
- **OS-process isolation** — `run` invokes the unified orchestrator, which spawns fresh OS processes for each pipeline stage. See `references/context-isolation.md` for details.
- **Agent-agnostic** — uses only git commands and generic session language; no tool-specific APIs.
- **Queue file is the memory** — `.agents/work-queue.json` persists state across process boundaries by design.
- **Derived status** — `aet-state derive` recomputes canonical statuses from git branches, worktrees, plan files, and `origin/main` ancestry; the queue stores the declaration.
- **Execution telemetry** — `.agents/execution.log.jsonl` is an append-only record of stage and run-summary events produced by the orchestrator. Use `aet-work report` to summarize it.
- **Worktree isolation** — each task gets its own branch; branches persist for independent review and PR.
- **Drain on failure** — running tasks finish, new spawns halt. Preserves in-progress work while stopping the pipeline.
