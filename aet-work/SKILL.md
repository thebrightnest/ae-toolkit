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

Read all `docs/plans/*.md` and produce `.agents/work-queue.json`.

**Procedure:**

1. Scan `docs/plans/` for all `*.md` files
2. For each plan.md, extract: title, task ID (from filename or frontmatter), blocking relationships
3. Build the DAG using `blocks` and `blocked_by` arrays
4. Set initial status: `unblocked` if `blocked_by` is empty, `blocked` otherwise
5. Set `merge_verified: false`, `merge_commit: null`, `completed_at: null`, and `merged_at: null` on each entry
6. Set `source_prd` to the most recent PRD in `docs/prds/` (if any)
7. Write `.agents/work-queue.json`

### `status`

Show the current state of the work queue.

**Procedure:**

1. Read `.agents/work-queue.json`
2. Report counts: unblocked, blocked, in-progress, done, failed
3. List the next 3 unblocked tasks (topological order)
4. List any failed tasks (require human attention)

### `next`

Identify and output the next unblocked task.

**Procedure:**

1. Read `.agents/work-queue.json`
2. Find tasks with `status: "unblocked"`
3. Pick the first in topological order (respecting the DAG)
4. Output: task ID, title, plan_file path
5. Update status to `in-progress` in the queue file

### `run`

AFK loop with OS-level process isolation. Generates a bash orchestrator script tailored to the detected agent CLI, spawns it as a background OS process, and waits for completion. Each task executes in a fresh agent process with its own git worktree, eliminating context leakage and branch overlap entirely.

**Procedure:**

1. **Runtime detection:**
   - Check `kimi` in `PATH` or `KIMI_CLI_VERSION` → `kimi`
   - Check `claude` in `PATH` or `CLAUDE_CODE` → `claude`
   - Check `AGENT_CLI` env var → user override
   - If none matched: emit warning and ask user to set `AGENT_CLI`

2. **Generate orchestrator script:**
   - Read `aet-work/references/orchestrator-template.sh` from this skill directory
   - Ensure the script includes merge verification: before each task, check
     `merge_verified` on all `blocked_by` entries. Warn if unverified, but continue.
   - Substitute template variables based on detected CLI:

     | CLI      | CLI_BIN      | CLI_ARGS (suggested) | CLI_PROMPT_FLAG | CLI_WORKDIR_FLAG |
     | -------- | ------------ | -------------------- | --------------- | ---------------- |
     | `kimi`   | `kimi`       | `--print` `--yolo`   | `-p`            | `--work-dir`     |
     | `claude` | `claude`     | `--print`            | (empty)         | `--add-dir`      |
     | custom   | `$AGENT_CLI` | (user-provided)      | (as needed)     | (as needed)      |

   - Write to `scripts/.aet-work-orchestrator.sh`
   - `chmod +x scripts/.aet-work-orchestrator.sh`

3. **Spawn and wait:**
   - `Shell(run_in_background=true)` to execute `scripts/.aet-work-orchestrator.sh`
   - `TaskOutput(block=true)` to wait for completion
   - If the script fails: report which task failed and preserve the branch for inspection

4. **Resume behavior:**
   - Re-running `run` regenerates the script and resumes from the current queue state
   - Already-done or in-progress tasks with existing worktrees are skipped automatically

**Context isolation mechanism:**

```
Parent agent session (clean)
  → detects runtime
  → generates scripts/.aet-work-orchestrator.sh
  → Shell(run_in_background=true) to spawn script
    → Script spawns Agent CLI process #1 (clean context, fresh process)
      → Task 1 completes, commits, exits
    → Script spawns Agent CLI process #2 (clean context, fresh process)
      → Task 2 completes, commits, exits
  → TaskOutput(block=true) returns
  → Parent session remains clean
```

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
