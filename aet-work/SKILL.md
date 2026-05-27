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

### `init-queue`

Read all `docs/plans/*.md` and produce or update `.agents/work-queue.json`.

**Procedure:**

1. Scan `docs/plans/` for all `*.md` files. This directory is for atomic, implementable task plans only. Roadmaps, audits, and meta-plans must be stored in `docs/roadmaps/` or `docs/audits/` and will not be added to the queue.
2. If `.agents/work-queue.json` exists, load it as `existing_queue`
3. For each plan.md, extract: title, task ID (from filename or frontmatter), blocking relationships
4. Build the DAG using `blocks` and `blocked_by` arrays
5. For each plan:
   - If its `plan_file` already exists in `existing_queue`, preserve its `status`, `merge_verified`, `merge_commit`, `completed_at`, `merged_at`, and `branch`
   - If new, set initial status: `unblocked` if `blocked_by` is empty, `blocked` otherwise; set `merge_verified: false`, `merge_commit: null`, `completed_at: null`, `merged_at: null`
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
   - Set `merge_verified: false`, `merge_commit: null`, `completed_at: null`, `merged_at: null`
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
3. Report counts: unblocked, blocked, in-progress, done, failed
4. List the next 3 unblocked tasks (topological order)
5. List any failed tasks (require human attention)

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

AFK loop with OS-level process isolation. Generates a bash orchestrator script tailored to the detected agent CLI, spawns it as a background OS process, and waits for completion. Each task executes in a fresh agent process with its own git worktree, eliminating context leakage and branch overlap entirely.

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

5. **Spawn and wait:**

   - `Shell(run_in_background=true)` to execute `scripts/.aet-work-orchestrator.sh`
   - `TaskOutput(block=true)` to wait for completion
   - If the script fails: report which task failed and preserve the branch for inspection

6. **Resume behavior:**
   - Re-running `run` regenerates the script and resumes from the current queue state
   - Already-done or in-progress tasks with existing worktrees are skipped automatically

**Context isolation mechanism:**

```
Parent agent session (clean)
  → self-reports runtime
  → generates scripts/.aet-work-orchestrator.sh
  → Shell(run_in_background=true) to spawn script
    → Script spawns Agent CLI process #1 (clean context, fresh process)
      → Task 1 completes, commits, exits
    → Script spawns Agent CLI process #2 (clean context, fresh process)
      → Task 2 completes, commits, exits
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

### `cleanup`

Remove worktrees for tasks that are merge-verified.

**Procedure:**

1. Read `.agents/work-queue.json`
2. For each task where `merge_verified` is `true`:

   ```bash
   git worktree remove .worktrees/<task-id>
   # If it refuses due to uncommitted changes, inspect first:
   # git -C .worktrees/<task-id> status
   # Then force-remove if safe: git worktree remove --force .worktrees/<task-id>
   ```

3. Report removed and remaining worktrees

## Key Principles

- **Queue-unaware pipeline** — aet-pipeline-implement knows nothing about the queue. aet-work checks results and updates the queue.
- **OS-process isolation** — `run` generates a bash orchestrator that spawns a fresh OS process for every task. See `references/context-isolation.md` for details.
- **Agent-agnostic** — uses only git commands and generic session language; no tool-specific APIs.
- **Queue file is the memory** — `.agents/work-queue.json` persists state across process boundaries by design.
- **Worktree isolation** — each task gets its own branch; branches persist for independent review and PR.
- **Fail fast, stop clean** — one failure halts the loop for human review; the failed branch is preserved.
- **v3: parallel execution** — run independent tasks in simultaneous worktrees (future iteration).
