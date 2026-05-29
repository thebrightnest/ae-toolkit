---
name: aet-work-parallel-execution-prd
description: PRD for upgrading aet-work run to execute independent tasks in parallel worktrees with configurable concurrency caps and graceful drain-on-failure behavior.
---

# PRD: aet-work Parallel Execution

## Overview

Upgrade `aet-work run` from sequential task execution to parallel execution of independent tasks. The orchestrator script will spawn multiple agent CLI processes simultaneously—each in its own git worktree—up to a configurable concurrency cap. When a task fails, the orchestrator drains currently running tasks (lets them finish) but stops spawning new ones. This dramatically reduces wall-clock time for queues with many independent tasks.

## Goals

1. Independent tasks execute simultaneously instead of sequentially
2. Concurrency is capped by default (fallback to number of CPU cores) with user override
3. Queue file updates remain race-condition-free under parallel execution
4. Failure behavior is predictable: drain running tasks, preserve failed branch, halt
5. Resume behavior works correctly after interruption or partial failure
6. Existing sequential semantics are preserved as a special case (cap = 1)

## Non-Goals

- Dynamic resizing of the concurrency cap mid-execution
- Cross-task communication or shared state between parallel tasks
- Priority scheduling or weighted queues
- Real-time progress dashboard or TUI
- Automatic rebalancing when one task finishes early
- Windows PowerShell / CMD support

## User Stories

- As a developer with a queue of 8 independent tasks, I want them to run in parallel so that a full queue finishes in hours instead of days.
- As a developer running `aet-work run`, I want my machine to stay responsive so that parallel execution does not starve my OS or other applications.
- As a developer whose queue contains a failing task, I want other running tasks to finish so that I don't lose work already in progress.
- As a maintainer, I want the parallel logic to be contained entirely in the generated bash script so that no Python dependencies or external tools are required.

## Acceptance Criteria

- [ ] `aet-work run` generates an orchestrator script that processes tasks in parallel
- [ ] Default concurrency cap is derived from `$(sysctl -n hw.ncpu)` (macOS) / `$(nproc)` (Linux)
- [ ] User can override via `AET_WORK_JOBS` env var or `--jobs` flag if the agent CLI supports it
- [ ] Queue file is updated only by the main orchestrator loop; child processes do not write to it
- [ ] On task failure: running tasks continue, new tasks are not started, orchestrator exits with failure after drain
- [ ] On task success: dependents are promoted to `unblocked` and become eligible for spawning immediately
- [ ] Resume works: re-running `aet-work run` skips `done`/`in-progress` tasks and spawns newly unblocked ones
- [ ] `make validate` passes and `make package` regenerates `.skill` files
- [ ] `aet-work/SKILL.md` documents the parallel behavior, cap mechanism, and failure semantics

## Technical Notes

### Parallelism Model

The orchestrator uses bash job control:

```
Main loop:
  while tasks remain:
    if slots available and unblocked tasks exist:
      spawn task as background job
      increment slot counter
    if any job finished:
      collect exit code
      update queue (done / failed)
      promote dependents
      decrement slot counter
    if failure occurred and no new spawns allowed:
      wait for all remaining jobs
      exit 1
    if no tasks remain and no jobs running:
      exit 0
```

Key invariants:

- Only the main loop reads/writes `.agents/work-queue.json`
- Child processes are pure agent CLI invocations; they exit when the agent finishes
- `wait -n` (bash 4.3+) or polling loop is used to detect job completion
- Every spawned subagent receives `AET_EXECUTION_MODE=unattended` per ADR-005

### Concurrency Cap

Detection order:

1. `AET_WORK_JOBS` environment variable
2. `$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)`
3. Minimum of detected value and `8` (hard upper bound to prevent accidental fork bombs)

### Queue State Machine Under Parallelism

| Status transition           | Trigger                                          |
| --------------------------- | ------------------------------------------------ |
| `unblocked` → `in-progress` | Task picked up by orchestrator, worktree created |
| `in-progress` → `done`      | Agent CLI exits 0                                |
| `in-progress` → `failed`    | Agent CLI exits non-zero                         |
| `blocked` → `unblocked`     | All `blocked_by` entries are `done`              |

Race condition avoidance: since only the main loop mutates the queue file and bash job control guarantees only one `wait` returns at a time, no file-locking mechanism is required.

### Context Isolation (Updated)

```
Parent agent session (clean)
  → generates scripts/.aet-work-orchestrator.sh
  → Shell(run_in_background=true) to spawn script
    → Script spawns Agent CLI process #1 (clean context, worktree A)
    → Script spawns Agent CLI process #2 (clean context, worktree B)
    → Script spawns Agent CLI process #3 (clean context, worktree C)
    → … up to cap
    → As each process exits, queue updates, new tasks spawn
  → TaskOutput(block=true) returns
  → Parent session remains clean
```

### Resume Behavior

The existing resume semantics are preserved:

- `done` tasks are skipped
- `in-progress` tasks with existing worktrees are treated as already running (the orchestrator does not respawn them; instead it marks them `failed` on startup if they are orphaned, or waits for the user to handle them)
- To keep this simple: on startup, any `in-progress` task without a detectable running PID is treated as unknown state. The orchestrator prints a warning and marks it `failed` so the user can inspect.

## Open Questions

1. Should the orchestrator emit a summary at the end (tasks completed, failed, wall-clock time)?
2. Should we add a `--sequential` flag to force cap=1 without editing env vars?
3. How should we handle `in-progress` tasks that were left behind by a crashed previous orchestrator run?

---

_Stage: synced_
\_Next step: run `aet-ship`
