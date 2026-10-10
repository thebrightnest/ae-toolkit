---
id: concurrent-auto-merge-orchestration
status: draft
branch: feat/concurrent-auto-merge-orchestration
pr_title: "feat(orchestrator): continuous auto-merge, non-blocking conflict staging, and dynamic concurrency replenishment"
---

# PRD: Continuous Auto-Merge Orchestration, Dynamic Concurrency Replenishment & aet-drive Integration

## Overview

In the current Agentic Engineering Toolkit execution pipeline, `aet run` runs tasks in parallel worktrees up to `--max-jobs`. However, the execution loop exhibits two major throughput bottlenecks:

1. **Batch Completion Barrier (Head-of-Line Blocking)**: Finished tasks do not dynamically integrate into the target branch to unblock downstream dependencies while other sibling tasks remain in flight. Under `/aet-drive`, the execution loop is strictly coarse-grained: `aet run` runs the entire batch until all tasks settle, then `aet-drive` inspects the sprint board and sequentially runs `aet ship merge <task_id>` on all `awaiting_merge` tasks before re-launching `aet run` for newly unblocked tasks. If Task A finishes in 3 minutes while independent Task B takes 25 minutes, Task A sits idle in `awaiting_merge` for 22 minutes. Downstream tasks dependent on Task A cannot start until Task B finishes and `aet-drive` executes post-batch merges.
2. **Worker Concurrency Starvation (Idle Ready Tasks)**: During execution, the orchestrator frequently throttles down to holding only 1 task `in_progress` while multiple `ready` tasks sit waiting in the queue, under-utilizing the configured parallel worker budget (`--max-jobs`). Furthermore, when an in-flight task completes or merges, the orchestrator does not eagerly backfill the newly freed slot with available ready tasks, causing artificial serialization.

This feature upgrades the orchestrator (`src/aet/cli/orchestrator.py`) and `aet-drive` to enable **continuous, lazy-rebased auto-merging and dynamic worker slot replenishment**:

1. When a task completes its stage pipeline, the batch orchestrator immediately initiates clean integration under `integration_lock`.
2. The task worktree is rebased onto the live integration tip (`origin/{target_branch}`), re-validated against the updated tip, merged, pushed, and marked `merged`.
3. Downstream dependent tasks are unblocked immediately in the same running batch (`blocked` -> `ready`).
4. **Dynamic Concurrency Slot Replenishment**: Whenever an active worker slot becomes free (a task finishes or merges), the orchestrator immediately evaluates remaining capacity (`max_jobs - len(running)`), inspects the queue for `ready` tasks (both newly unblocked and pre-existing ready tasks), and eagerly spawns new workers up to `--max-jobs`.
5. If a rebase conflict or post-rebase validation failure occurs, the orchestrator isolates the failure: it stages the task in `awaiting_merge` with structured conflict diagnostics, releases the lock, and continues executing all remaining independent tasks in parallel without crashing or stopping the batch.
6. When `aet run` settles (no more runnable tasks remain because remaining tasks are either conflicted or blocked), `aet-drive` steps in to resolve conflicts using agent intelligence and re-invokes `aet run`.

**Intake Triage Guard**: Confirmed feature and workflow optimization. Not a reproducible defect in existing code.

---

## Goals

- **G-1**: As soon as any individual task completes its pipeline stages in `aet run`, attempt clean auto-merge immediately without waiting for sibling tasks in the batch to complete.
- **G-2**: Unblock downstream DAG tasks dynamically within the active batch as soon as their blocking task integrates, allowing them to be spawned immediately in newly freed concurrency slots.
- **G-3**: Dynamically backfill worker slots up to `--max-jobs`: whenever a running task finishes and/or merges, immediately dispatch available `ready` tasks into freed worker slots without waiting for other batch tasks to settle.
- **G-4**: Eliminate single-worker starvation: ensure the batch spawn loop fully utilizes the parallel budget (spawning up to `--max-jobs` concurrent tasks when multiple `ready` tasks exist) and never artificially serializes execution.
- **G-5**: Guarantee integration soundness per ADR-045 and ADR-029: integration is serialized under `integration_lock`, rebased onto the live tip, re-validated with full project gates, and verified before recording terminal closure.
- **G-6**: Provide non-blocking conflict isolation: tasks encountering rebase conflicts or validation failures do not abort or crash the orchestrator; they are staged in `awaiting_merge` with diagnostic metadata while independent tasks continue executing.
- **G-7**: Streamline `aet-drive` (`skills/aet-drive/SKILL.md` and `.agents/commands/aet-drive.md`) so that clean tasks are already merged during `aet run`, focusing `aet-drive`'s post-batch phase strictly on resolving any staged conflicts.
- **G-8**: Support both `single-pr` mode (integrating into the declared epic branch) and standalone / `pr-per-task` auto-merge (integrating into the resolved target/trunk branch).

---

## Non-Goals

- **Concurrent Integration Branch Writes**: Merging into the target branch remains strictly serialized via `integration_lock`. Two tasks will never rebase or merge into the target branch simultaneously.
- **Out-of-band Interactive Conflict Resolution during `aet run`**: An interactive agent session will not attempt to resolve conflicts in the live integration branch while `aet run` is actively spawning tasks and managing worker processes. Conflict staging isolates the failure so resolution occurs cleanly when `aet run` yields.
- **Bypassing Post-Rebase Re-Validation**: Merging a task that passed tests on an older commit without re-validating against the live integration tip is strictly forbidden.

---

## Architecture & Design Principles

### 1. Lazy Rebase at Gate

Concurrent tasks are spawned against the base commit at the time of their launch. When Task A finishes and merges into `target_branch`, the branch tip advances. In-flight Task B continues executing in its own worktree undisturbed. When Task B finishes its stages, the orchestrator acquires `integration_lock`, rebases Task B onto the updated `origin/{target_branch}`, and re-validates Task B in its worktree.

### 2. Serialized Integration Lock

All operations that advance the target branch (`fetch`, `rebase`, `_validate_after_rebase`, `merge`, `push`, and queue transition) run under `integration_lock(repo_root)`. Worker tasks implement concurrently up to `--max-jobs`, but integrations proceed one at a time.

### 3. Dynamic Worker Slot Replenishment (Reactive Dispatch Loop)

The batch orchestrator's event loop manages worker processes reactively:

1. **Capacity Evaluation**: Whenever a running task finishes (exit code detected) or completes integration, its process handle is removed from `running`, immediately opening a worker slot (`available_slots = max_jobs - len(running)`).
2. **Immediate Frontier Refresh**: Marking a task `merged` updates the queue and triggers dependent promotion (`blocked` -> `ready`).
3. **Eager Refill**: If `available_slots > 0`, the orchestrator immediately queries for all eligible `ready` tasks and spawns them concurrently up to the available capacity without waiting for next poll timeouts or for other siblings to finish.
4. **Starvation Elimination**: The spawn loop iterates through all available `ready` tasks up to `max_jobs` on startup and on every replenishment cycle, ensuring no artificial loop termination or single-worker throttling occurs when multiple independent tasks are queued.

### 4. Non-Blocking Conflict Staging

If Task B's rebase encounters conflicts or post-rebase validation fails:

1. The rebase in Task B's worktree is cleanly aborted (`git rebase --abort`).
2. The orchestrator records conflict metadata (`conflicting_files`, failure reason) on Task B's record.
3. Task B is transitioned to `awaiting_merge`.
4. `integration_lock` is released immediately.
5. The orchestrator continues its main loop: other in-progress tasks continue running, and any independent ready tasks can be spawned into open worker slots.
6. The orchestrator does NOT exit with an unhandled exception or stop-spawn condition.

### 5. Dynamic DAG Progression

In each iteration of the batch loop, whenever a task transitions to `merged`, the orchestrator refreshes queue state (`backend.load()`). Any task whose blockers are all `merged` transitions from `blocked` to `ready` and is eligible for immediate spawning into available worker slots.

---

## Requirements

- **R-1 (Continuous Integration Trigger)**: When a child task process exits with code 0 and passes evidence verification, `run_batch` initiates integration immediately in that loop iteration rather than deferring all merges to post-batch.
- **R-2 (Serialized Lazy Rebase & Gate Validation)**: Integration is gated behind `integration_lock`. Under the lock, the task branch is rebased onto `origin/{target_branch}` and re-validated using `_validate_after_rebase` (`AET_INTEGRATION_VALIDATE_CMD` or `make validate`).
- **R-3 (Clean Merge & Terminal Closure)**: Upon successful re-validation, the task branch is merged into the integration branch, pushed to origin, recorded in the provenance ledger, and transitioned to `merged` via `aet-state transition`.
- **R-4 (Immediate DAG Unblocking)**: Marking a task `merged` immediately unblocks dependent tasks in the queue; the orchestrator discovers newly `ready` tasks and dispatches them in available concurrency slots without restarting the batch.
- **R-5 (Dynamic Concurrency Slot Replenishment)**: Whenever any running task finishes or merges, the orchestrator immediately checks the parallel worker budget (`max_jobs - len(running)`) and dispatches waiting `ready` tasks immediately into the open slots, maintaining maximum parallelism up to `--max-jobs`.
- **R-6 (Elimination of Single-Worker Throttling)**: The orchestrator's spawn loop must eagerly launch all available `ready` tasks up to `--max-jobs` concurrently at batch start and during slot replenishment, preventing any condition where multiple tasks are `ready` but only 1 is placed in `in_progress`.
- **R-7 (Non-Blocking Conflict Staging)**: If a rebase produces merge conflicts or re-validation fails, the orchestrator aborts the rebase, transitions the task to `awaiting_merge`, writes conflict diagnostics (conflicting files and output tail) into task metadata, releases the lock, and continues running the rest of the batch.
- **R-8 (Idle Batch Settle)**: When all running tasks have finished and all remaining tasks in the queue are either `awaiting_merge` (conflicted) or `blocked` (by conflicted tasks), `aet run` terminates cleanly with an informative report.
- **R-9 (`aet-drive` Skill Harmonization)**: Update `skills/aet-drive/SKILL.md` and `.agents/commands/aet-drive.md` to reflect that clean tasks auto-merge during `aet run`. `aet-drive`'s merge step only operates on tasks remaining in `awaiting_merge`, running the Conflict Resolution Runbook when conflicts exist.
- **R-10 (Dual Mode Parity)**: Continuous auto-merge and dynamic slot replenishment function identically in `single-pr` mode (targeting the active epic branch) and in standalone mode when auto-merge is configured/invoked (targeting the resolved integration/trunk branch).

---

## User Stories

- **US-1**: As an engineer running multi-task sprints with dependencies, I want finished tasks to integrate immediately so that dependent tasks start running without waiting for long-running sibling tasks. (satisfies: R-1, R-3, R-4)
- **US-2**: As an engineer, I want the orchestrator to immediately backfill freed concurrency slots with waiting ready tasks whenever a task completes, so that parallel worker capacity is fully utilized up to `--max-jobs`. (satisfies: R-5, R-6)
- **US-3**: As an engineer, I want all background integrations to be re-validated against the live integration tip under a lock so that no broken combinations or regressions land on the integration branch. (satisfies: R-2, R-10)
- **US-4**: As an autonomous execution loop (`aet-drive`), I want merge conflicts in background tasks to be staged non-destructively so that independent tasks finish uninterrupted and I only need to resolve the specific conflicting tasks. (satisfies: R-7, R-8, R-9)

---

## Acceptance Criteria

- [ ] Completed tasks trigger immediate integration under `integration_lock` while other tasks remain in flight. (satisfies: R-1, R-2)
- [ ] Tasks rebase onto `origin/{target_branch}` and pass `_validate_after_rebase` before the merge commit is created and pushed. (satisfies: R-2, R-3)
- [ ] Tasks that successfully integrate transition to `merged` and record terminal closure in the provenance ledger. (satisfies: R-3)
- [ ] Transitioning a task to `merged` immediately frees dependencies, allowing downstream tasks to be spawned in the same batch session. (satisfies: R-4)
- [ ] As soon as a worker task finishes or merges, open slots are immediately replenished with waiting `ready` tasks up to `--max-jobs`. (satisfies: R-5)
- [ ] When multiple `ready` tasks exist and `--max-jobs` allows it, the orchestrator spawns multiple tasks concurrently rather than throttling down to 1 task in `in_progress`. (satisfies: R-6)
- [ ] A rebase conflict or validation failure on one task aborts cleanly, records conflict details in `awaiting_merge`, and does NOT terminate or block other running tasks. (satisfies: R-7)
- [ ] `aet run` exits cleanly when no further progress can be made, reporting the list of auto-merged tasks and any tasks left in `awaiting_merge`. (satisfies: R-8)
- [ ] `skills/aet-drive/SKILL.md` and `.agents/commands/aet-drive.md` document the streamlined flow where `aet-drive` resolves only remaining conflicted `awaiting_merge` tasks. (satisfies: R-9)
- [ ] Both `single-pr` mode and standalone auto-merge correctly target their respective integration branches and maintain dynamic slot replenishment. (satisfies: R-10)

---

## Technical Notes

1. **Orchestrator Parent vs. Child Responsibilities**:
   Currently, in `single-pr` mode, `_integrate_single_pr_task` is called from inside the child `run_single` process. When called in the child, if it fails or checks out `repo_root`, it can disrupt the batch parent or race with other children.
   Moving integration into the batch parent `run_batch` (or delegating it under the top-level `integration_lock` using a dedicated temporary worktree) ensures that only one integration runs at any moment, and child processes strictly perform stage execution.
2. **Worktree Isolation for Integration**:
   Rather than checking out `integration_branch` in `repo_root`, integration should rebase inside the task's worktree or a dedicated temporary integration worktree. This preserves `repo_root` cleanliness and prevents index locking issues.
3. **Queue Lease Continuity**:
   Because `run_batch` owns the queue lease (`AET_RUN_ID`), running the integration in the parent loop eliminates any lease contention or out-of-band mutation errors.
4. **Eager Slot Replenishment Mechanics**:
   In `run_batch`, the process polling block should immediately follow with slot refilling:
   `if len(running) < max_jobs and not stop_spawn:` trigger spawn pass immediately before evaluating loop termination or sleeping.
5. **Diagnosing Single-Worker Throttling**:
   Ensure `get_next_ready_task(queue)` and `backend.load()` within the spawn loop do not short-circuit or hit stale cache blocks that break out of the while loop after 1 iteration when more ready tasks exist.

---

## Open Questions & Risks

- **Q-1**: What happens if three tasks finish almost simultaneously?
  - *Answer*: They queue for `integration_lock`. Task 1 acquires the lock, rebases onto tip $T_0$, validates, and merges to produce tip $T_1$. Task 2 then acquires the lock, rebases onto $T_1$, validates, and merges to produce $T_2$. Task 3 acquires the lock, rebases onto $T_2$, validates, and merges. Re-validation ensures full serial correctness. Meanwhile, any task that finished stage work frees its slot for another task to begin executing stages immediately.
- **Risk**: If `_validate_after_rebase` (`make validate`) takes 60 seconds, holding `integration_lock` for 60 seconds serializes the integration tail.
  - *Mitigation*: Stage implementation remains fully parallel. The lock is held only during the final rebase + validation gate, which is required to prevent broken commits from reaching the shared integration branch (ADR-045).

---

*Stage: scope-validated*
*Next step: run `aet-work` (single-plan or multi-task queue)*
