---
name: aet-work
description: Work queue management and AFK task orchestration. Use when you have multiple plan.md files and want to run them sequentially or check queue status. Enables the "night shift" mode: pick next unblocked task, implement, validate, mark done, repeat. Triggers on requests like "run the queue," "pick next task," "what's unblocked," or "AFK mode."
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

Use this context to ground all recommendations. Do not ask the user to provide it manually.

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

**Critical constraint:** Context must be cleared between tasks. An AFK loop running 5–10 tasks in one session will accumulate context until the agent degrades. The loop will work for 3 tasks and silently degrade on the 4th.

**Procedure:**

```
while true:
  1. Read .agents/work-queue.json
  2. Find next unblocked task
  3. If no unblocked tasks remain:
     - Report completion
     - Break loop
  4. Mark task as in-progress in queue
  5. **CLEAR CONTEXT** — mandatory. Use /clear, restart agent, or start new session.
  6. **RE-PRIME** — load minimal fresh context (AGENTS.md, last 5 commits, current branch)
  7. Read the task's plan.md
  8. Implement the task (follow aet-implement procedure)
  9. Run validation (lint, type-check, tests from plan.md)
  10. Run aet-review on the diff
  11. If validation or review fails:
      - Mark task as failed in queue
      - Stop loop, report failure to human
  12. Commit the work
  13. Mark task as done in queue
  14. Update dependent tasks: if all blocked_by are done, set to unblocked
  15. **CLEAR CONTEXT** again before next iteration
```

**Human-in-the-loop gates:**

- Loop stops on validation failure
- Loop stops on review failure
- Loop stops on merge conflicts
- Loop can be run with `--dry-run` to preview only (no implementation)
- Loop never auto-ships; aet-ship is a separate human-triggered step

**Context isolation details:**

- Each task starts with a clean context (like a fresh session)
- aet-prime reloads only minimal context (5–15k tokens)
- The queue file itself is tiny (<5k tokens)
- Context growth is bounded per task, not cumulative across the loop

## Key Principles

- **Queue-unaware implement** — aet-implement knows nothing about the queue. aet-work checks results and updates the queue.
- **Context isolation is mandatory** — without it, the loop degrades silently after 3–4 tasks
- **Sequential v1, parallel v2** — this skill runs one task at a time. Parallel worktrees are deferred to a future iteration.
- **Fail fast, stop clean** — one failure halts the loop for human review
