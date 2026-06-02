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

| Status      | Meaning                                                                                                   | Set by                                |
| ----------- | --------------------------------------------------------------------------------------------------------- | ------------------------------------- |
| `merged`    | Code is verified on `origin/main` (`merge_verified: true`)                                                | `post-ship-verify` or `mark-terminal` |
| `done`      | **Deprecated.** Pipeline completed but not yet verified on main. Treated as `merged` for promotion logic. | Orchestrator (legacy)                 |
| `abandoned` | Task explicitly cancelled with a documented reason                                                        | `mark-terminal`                       |
| `failed`    | Pipeline failed; requires human inspection                                                                | Orchestrator                          |

New tasks should reach `merged` or `abandoned`. `done` is retained for backwards compatibility.

### `init-queue`

Read all `docs/plans/*.md` and produce or update `.agents/work-queue.json`.

**Procedure:**

1. Scan `docs/plans/` for all `*.md` files. This directory is for atomic, implementable task plans only. Roadmaps, audits, and meta-plans must be stored in `docs/roadmaps/` or `docs/audits/` and will not be added to the queue.
2. If `.agents/work-queue.json` exists, load it as `existing_queue`
3. For each plan.md, extract: title, task ID (from filename or frontmatter), blocking relationships
4. Build the DAG using `blocks` and `blocked_by` arrays
5. For each plan:
   - If its `plan_file` already exists in `existing_queue`, preserve its `status`, `merge_verified`, `merge_commit`, `completed_at`, `merged_at`, and `branch`
   - If new, set initial status: `unblocked` if `blocked_by` is empty, `blocked` otherwise; set `merge_verified: false`, `merge_commit: null`, `completed_at: null`, `merged_at: null`, `worktree: null`, `branch: null`
   - **Branch naming:** the orchestrator uses the task ID as the branch name. If a task requires a prefixed branch (e.g., `feat/`), store the actual branch name in the `branch` field during `init-queue` or via `mark-terminal`.
6. Set `source_prd` to the most recent PRD in `docs/prds/` (if any)
7. Set `queue_updated_at` to the current ISO-8601 timestamp
8. Write `.agents/work-queue.json`
9. Report: `N existing tasks preserved, M new tasks added`

### `sync`

Incrementally sync `docs/plans/*.md` into the existing work queue without losing statuses.

**Procedure:**

1. Read `.agents/work-queue.json` if it exists; otherwise treat as empty array
2. Scan `docs/plans/` for all `*.md` files
3. For each plan whose `plan_file` is not already in the queue:
   - Extract title, task ID, blocking relationships
   - Determine `blocked_by` and `blocks` from the DAG
   - **Validate task sizes:** Scan the plan's task list. If any task exceeds the AI-complexity limit (> 8 files OR > 300 diff lines), refuse to add the plan and emit a split suggestion. If the plan contains `⚠️ ATOMIC OVERSIZED`, add it but set `oversized: true` on the queue entry.
   - **Validate atomicity:** If the plan references other plan files or contains multiple "Phase" sections, emit a warning and skip it. Non-atomic documents belong in `docs/roadmaps/` or `docs/audits/`.
   - Set status: `unblocked` if `blocked_by` is empty, `blocked` otherwise
   - Set `merge_verified: false`, `merge_commit: null`, `completed_at: null`, `merged_at: null`, `worktree: null`, `branch: null`
   - Append to queue array
4. For any queue entry whose `plan_file` no longer exists on disk:
   - Set `status: "orphaned"` and print a warning
5. Update `queue_updated_at` to current ISO-8601 timestamp
6. Write `.agents/work-queue.json`
7. Report: `N new tasks added, M existing tasks preserved, K orphaned tasks flagged`

**When to use:** After any session that creates or modifies plan files (e.g., after `aet-plan` or `aet-pipeline-plan`). This is the standard maintenance command; `init-queue` is for first-time setup.

### `status`

Show the current state of the work queue.

**Procedure:**

1. Run the `plan-drift` check (see below). If drift is detected:
   - Print `⚠️ Plan drift detected: N plan file(s) not in queue`
   - List the orphaned plan filenames
   - Print `Run init-queue to sync, or acknowledge each plan manually.`
   - **Do not report "all clear" even if all tracked tasks are done**
2. Read `.agents/work-queue.json`
3. Report counts: unblocked, blocked, in-progress, done, merged, abandoned, failed
4. List the next 3 unblocked tasks (topological order)
5. List any failed tasks (require human attention)
6. **Worktree validation:** For each task with a `worktree` field, check if the directory exists. If missing, print `⚠️ Stale worktree: {task_id} → {path} does not exist. Run cleanup to repair.`

### `next`

Identify and output the next unblocked task.

**Procedure:**

1. Run the `plan-drift` check. If drift is detected, refuse to pick a task and instruct the user to run `init-queue` first
2. Read `.agents/work-queue.json`
3. Find tasks with `status: "unblocked"`
4. Pick the first in topological order (respecting the DAG)
5. Output: task ID, title, plan_file path
6. Update status to `in-progress` in the queue file

### `run`

AFK loop with OS-level process isolation and parallel execution. Generates a bash orchestrator script tailored to the detected agent CLI, spawns it as a background OS process, and waits for completion. Independent tasks execute simultaneously—each in its own git worktree and agent process—up to a configurable concurrency cap. Context leakage and branch overlap are eliminated entirely.

**Procedure:**

1. **Plan-drift guard:** Run the `plan-drift` check. If drift is detected, refuse to start the AFK loop and instruct the user to run `init-queue` first

2. **Pre-branch git hygiene:**

   Before spawning the first task, the orchestrator ensures `main` is clean and synchronized with `origin/main`. If `main` is dirty, ahead, or behind, the orchestrator prints actionable warnings and halts before creating any worktrees. In unattended mode, warnings are logged but the loop continues.

3. **Runtime self-identification:**

   - You are the AI coding agent currently executing this skill. Determine the CLI
     command that should be used to spawn a fresh process of yourself (e.g. `kimi`,
     `claude`, `cursor`).
   - Determine the flags your CLI accepts for: (a) passing a prompt/message,
     (b) setting the working directory, and (c) any recommended non-interactive flags.
     For unattended execution use the most headless mode available (e.g. Kimi: `--afk`,
     Claude: `--dangerously-skip-permissions`, Cursor: non-interactive flags) so that
     approval gates are auto-dismissed and the agent never blocks for human input.
   - Use these self-reported values for the template variables `CLI_BIN`, `CLI_ARGS`,
     `CLI_PROMPT_FLAG`, and `CLI_WORKDIR_FLAG`.

4. **Generate orchestrator script:**

   - Read `aet-work/references/orchestrator-template.sh` from this skill directory
   - Ensure the script includes merge verification: before each task, check
     `merge_verified` on all `blocked_by` entries. Warn if unverified, but continue.
   - Substitute template variables using the self-reported CLI configuration from
     Step 3.
   - Write to `scripts/.aet-work-orchestrator.sh`
   - `chmod +x scripts/.aet-work-orchestrator.sh`

5. **Spawn and wait (parallel):**

   - The orchestrator maintains a slot pool up to the concurrency cap
   - While slots are available and unblocked tasks exist:
     - Spawn the next unblocked task as a background job in its worktree
     - Increment active slot counter
   - When a job finishes:
     - Collect exit code
     - Update queue status (`done` or `failed`)
     - Promote dependents to `unblocked`
     - Decrement slot counter
   - On task failure:
     - Allow currently running tasks to finish (drain)
     - Do not start new tasks
     - Exit with failure after drain completes
   - `Shell(run_in_background=true, timeout=7200)` to execute `scripts/.aet-work-orchestrator.sh`
     (2-hour ceiling; aet-pipeline-implement tasks can run 30–60 min each, and 4 parallel
     slots may need >1 hour for the first batch to finish)
   - `TaskOutput(block=true)` to wait for completion

6. **Concurrency cap:**

   - Default: `4` jobs (override with `AET_WORK_JOBS` env var), hard cap at 8
   - Override: set `AET_WORK_JOBS` environment variable
   - The orchestrator never exceeds the cap to prevent resource exhaustion

7. **Resume behavior:**
   - Re-running `run` regenerates the script and resumes from the current queue state
   - Already-done or in-progress tasks with existing worktrees are skipped automatically

**Context isolation mechanism:**

```
Parent agent session (clean)
  → self-reports runtime
  → generates scripts/.aet-work-orchestrator.sh
  → Shell(run_in_background=true) to spawn script
    → Script spawns Agent CLI process #1 (clean context, worktree A)
    → Script spawns Agent CLI process #2 (clean context, worktree B)
    → Script spawns Agent CLI process #3 (clean context, worktree C)
    → … up to concurrency cap
    → As each process exits, queue updates, new tasks spawn
  → TaskOutput(block=true) returns
  → Parent session remains clean
```

**Unattended mode:** The generated script sets `AET_EXECUTION_MODE=unattended` in the environment of every spawned subagent. Skills that have interactive approval gates (e.g., `aet-implement`, `aet-pipeline-implement`) detect this variable and skip gates that require human input, logging the bypass for auditability. See `references/context-isolation.md` for details.

### `plan-drift`

Detect plan files that exist on disk but are not represented in the work queue.

**Procedure:**

1. Read `.agents/work-queue.json` and collect all `plan_file` paths
2. List all `docs/plans/*.md` files. Only atomic plans in this directory are considered; roadmaps and audits stored elsewhere are ignored.
3. Identify any plan files whose path is not found in the queue's `plan_file` set
4. Compare the most recent modification time of any `docs/plans/*.md` against the `queue_updated_at` field (or the queue file's mtime as fallback)
5. Report findings:
   - Orphaned plans: print each filename and `⚠️ Plan drift detected: N plan file(s) not in queue. Run init-queue to sync.`
   - Stale queue: if plans are newer than the queue, print `⚠️ Queue is stale (plans modified after last init-queue). Run init-queue to sync.`
   - If none: print `✅ No plan drift detected. All plans are tracked in the queue.`

### `drift-check`

Detect tasks marked `done` or `merged` whose commits are not on `origin/main`.

**Procedure:**

1. Read `.agents/work-queue.json`
2. Run `git fetch origin`
3. For each task with status `done` or `merged`:
   a. If `merge_commit` is set and `git merge-base --is-ancestor <merge_commit> origin/main` passes, skip (verified)
   b. If `branch` is set, run `git merge-base --is-ancestor <branch> origin/main`. If it fails, record as drifted
   c. If neither `merge_commit` nor `branch` is available, record as unverifiable
4. Report findings:
   - Drifted tasks: print task ID, title, and branch name
   - Unverifiable tasks: print task ID and note missing metadata
   - If none: print `✅ No drift detected. All done/merged tasks are on origin/main.`

### `mark-terminal`

Mark a task as `merged` or `abandoned`. This is the only supported way to set a terminal status manually.

**Procedure:**

1. Read `.agents/work-queue.json`
2. Find the task by ID
3. If setting to `merged`:
   - Verify `merge_verified: true` and `merge_commit` is set
   - If not verified, STOP and print: `⛔ Cannot mark as merged: merge_verified is false. Run aet-ship and post-ship-verify first.`
4. If setting to `abandoned`:
   - Require a `reason` argument (non-empty string)
   - Set `abandoned_at` to current ISO-8601 timestamp
   - Print: `⚠️ Task {id} marked abandoned. Reason: {reason}`
5. Write `.agents/work-queue.json`

**Rules:**

- Never mark a task `merged` without `merge_verified: true`
- Never mark a task `done` manually; use `merged` (if on main) or `abandoned` (if cancelled)

### `cleanup`

Remove worktrees for tasks that are merge-verified, and repair stale queue entries.

**Procedure:**

1. Read `.agents/work-queue.json`
2. For each task where `merge_verified` is `true`:

   ```bash
   git worktree remove .worktrees/<task-id>
   # If it refuses due to uncommitted changes, inspect first:
   # git -C .worktrees/<task-id> status
   # Then force-remove if safe: git worktree remove --force .worktrees/<task-id>
   ```

3. **Stale worktree repair:** For each task with a `worktree` field:
   - If the directory does not exist, clear `worktree: null` and print `Repaired stale worktree field for {task_id}`
   - If the directory exists but has 0 commits ahead of main (`git rev-list --count main..HEAD` in the worktree returns 0), remove the worktree and clear `worktree: null`
4. Report removed, repaired, and remaining worktrees

## Key Principles

- **Queue-unaware pipeline** — aet-pipeline-implement knows nothing about the queue. aet-work checks results and updates the queue.
- **OS-process isolation** — `run` generates a bash orchestrator that spawns fresh OS processes for tasks. See `references/context-isolation.md` for details.
- **Agent-agnostic** — uses only git commands and generic session language; no tool-specific APIs.
- **Queue file is the memory** — `.agents/work-queue.json` persists state across process boundaries by design.
- **Worktree isolation** — each task gets its own branch; branches persist for independent review and PR.
- **Drain on failure** — running tasks finish, new spawns halt. Preserves in-progress work while stopping the pipeline.
