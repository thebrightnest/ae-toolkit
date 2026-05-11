---
name: aet-work
description: Work queue management and sequential task execution. Use when you have plan.md files to run in order, want hands-free task execution, or need to check what's ready. Triggers on: "run the queue", "pick next task", "what's next", "what's unblocked", "run all tasks", "keep working", "run tasks", "execute plans", "night shift", "AFK mode", "queue status", "init queue", "what can I work on", "run unblocked tasks".
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
5. Set `source_prd` to the most recent PRD in `docs/prds/` (if any)
6. Write `.agents/work-queue.json`

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

AFK loop: implement tasks until none remain or a failure occurs.

**Procedure:**

```
while true:
  1. Read .agents/work-queue.json
  2. Find next unblocked task
  3. If no unblocked tasks remain:
     - Report completion; list all task branches created
     - Break loop
  4. Mark task as in-progress in queue
  5. Create a worktree for the task (ensure .worktrees/ is in .gitignore):
       git worktree add .worktrees/<task-id> -b <task-id>
     Resume case: if the task is already in-progress and .worktrees/<task-id> exists,
     skip this step — the worktree from the interrupted session is still valid.
  6. CLEAR CONTEXT — start a new session or use your agent's context reset.
     The queue file persists state; resume by running aet-work run again.
  7. Load minimal context: AGENTS.md + last 5 commits + current branch
  8. cd into .worktrees/<task-id>; read the task's plan.md
  9. Run `aet-pipeline-implement` on the task's plan.md (this handles the full quality
     pipeline: tdd → implement → qa → review → cso → sync-docs; worktree is already
     created, so skip the worktree setup step inside the pipeline)
  10. If `aet-pipeline-implement` stops at any gate (validation failure, architecture
      issue, security finding, or any hard-stop condition):
      - cd back to repo root
      - Mark task as failed in queue; record which stage it stopped at
      - Stop loop, report failure (branch preserved at .worktrees/<task-id>)
  11. cd back to repo root (aet-pipeline-implement commits atomically per step;
      all changes are already committed by the time the pipeline finishes)
  12. Mark task as done; record branch name (<task-id>) in queue entry
  13. Update dependent tasks: if all blocked_by are done, set to unblocked
  14. CLEAR CONTEXT again (start a new session) before the next iteration
```

**Human-in-the-loop gates:**

- Loop stops on validation failure
- Loop stops on review failure
- Loop stops on merge conflicts
- Loop can be run with `--dry-run` to preview only (no implementation)
- Loop never auto-ships; aet-ship is a separate human-triggered step

**Context isolation details:**

- Context window: cleared between tasks by starting a new session (works in every agent)
- Branch isolation: each task gets its own branch at `.worktrees/<task-id>/`
- State persistence: `.agents/work-queue.json` survives context resets — it is the
  handoff between sessions, not memory
- After the loop: N branches ready for independent review; `git worktree list` shows all

### `cleanup`

Remove worktrees whose branches have been merged.

**Procedure:**

1. Run `git worktree list` to see all active worktrees
2. For each `.worktrees/<task-id>` whose branch is merged into the default branch:

   ```bash
   git worktree remove .worktrees/<task-id>
   # If it refuses due to uncommitted changes, inspect first:
   # git -C .worktrees/<task-id> status
   # Then force-remove if safe: git worktree remove --force .worktrees/<task-id>
   ```

3. Report removed and remaining worktrees

## Key Principles

- **Queue-unaware pipeline** — aet-pipeline-implement knows nothing about the queue. aet-work checks results and updates the queue.
- **Context isolation via new sessions** — every agent supports starting fresh; the queue file bridges sessions so no state is lost.
- **Agent-agnostic** — uses only git commands and generic session language; no tool-specific APIs.
- **Queue file is the memory** — `.agents/work-queue.json` persists state across context resets by design.
- **Worktree isolation** — each task gets its own branch; branches persist for independent review and PR.
- **Fail fast, stop clean** — one failure halts the loop for human review; the failed branch is preserved.
- **v3: parallel execution** — run independent tasks in simultaneous worktrees (future iteration).
