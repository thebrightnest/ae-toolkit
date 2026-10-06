---
id: task-state-reset-and-recovery
status: draft
---

# PRD: Task State Reset and Recovery

## Overview

When an automated pipeline execution (`aet run`, `aet run-one`, or `aet-drive`) halts due to a failure, timeout, crash, or environment disruption, tasks can become stuck in `in_progress`, `failed`, or `quarantined` states with accumulated failure signatures or stale leases. Previously, operators and AI agents struggled to recover: `aet state reset <task_id>` refused to reset whenever a branch or worktree still existed (stating `derived state is in_progress, not ready/blocked`), required an obscure `--apply` flag, and provided no single-command workflow to either resume in-progress work in-place or wipe the slate clean.

This feature overhauls `aet state reset` into an intuitive, deterministic single-command recovery mechanism. It introduces two primary reset modes:

1. **Soft Reset (Default / Resume):** Preserves existing worktrees and branches with their in-progress code changes, clears failure signatures/circuit breaker trips and stale leases, and administratively moves the task back to `ready` (or `blocked`), allowing `aet run` to pick up and resume work in-place.
2. **Hard Reset (`--hard` / `--clean`):** Tears down `.worktrees/<task_id>`, deletes the local git branch, clears runtime fields and failure signatures, and resets the task to `ready` (or `blocked`) for a clean-slate restart.

Execution runs live by default without requiring `--apply`, with `--dry-run` available for previewing changes.

## Goals

- Enable operators and agent sessions to reset any failed, stuck, or quarantined task back to `ready` with a single command (`aet state reset <task_id>`).
- Support resuming in-flight work in-place without discarding uncommitted code or branch commits (Soft Reset).
- Support wiping a task's branch, worktree, and runtime fields completely for a clean-slate re-execution (`--hard` / `--clean`).
- Execute real mutations by default, adhering to AE Toolkit's no-default-dry-run principle, while offering `--dry-run` for safe dry-run inspection.
- Clear per-task failure signatures and prune the task from the systemic breaker store (`refs/aet/breaker`), releasing circuit breaker locks.
- Release stale leases so downstream orchestrators (`aet run`, `aet-drive`) can immediately claim and execute the reset task.

## Non-Goals

- Replacing `aet state heal`: `heal` remains the whole-queue reconciliation command based strictly on git derivation. `reset` is the pointed, administrative intervention command for a specific task.
- Modifying orchestrator loop scheduling algorithms: the orchestrator already knows how to claim `ready` tasks and reuse existing worktrees.
- Arbitrary manual state transitions: this command specifically targets returning tasks to an executable unstarted/resumable state (`ready` or `blocked` based on dependency status).

## Requirements

- **R-1**: **Live by default with optional `--dry-run`**. `aet state reset <task_id>` executes mutations immediately unless `--dry-run` is explicitly provided. The obsolete `--apply` requirement is removed.
- **R-2**: **Soft Reset / Resume (Default Mode)**. When invoked without `--hard`, the command preserves the `.worktrees/<task_id>` directory and the local git branch. It transitions the task state from `in_progress`, `failed`, or `quarantined` to `ready` (if all blockers are satisfied) or `blocked` (if dependencies are incomplete) via administrative repair (`repair=True`), without being blocked by git-derived `in_progress` state.
- **R-3**: **Hard Reset / Clean Slate (`--hard` / `--clean`)**. When invoked with `--hard` or `--clean`, the command forcefully removes `.worktrees/<task_id>` (using `git worktree remove --force`), deletes the local task branch (`git branch -D <branch>`), purges runtime fields (`branch`, `worktree`, `run_id`, `failure_signatures`, `stage`), and sets the task state to `ready` (or `blocked`).
- **R-4**: **Stage Targeting (`--stage`)**. Allow an optional `--stage <stage>` flag to reset or update `task["stage"]` (e.g. `tdd`, `implement`, `review`, `qa`). On `--hard`, `task["stage"]` is cleared so the task resets to the workflow entry stage.
- **R-5**: **Failure Signature & Circuit Breaker Reset**. Clear `task["failure_signatures"]` on reset, and remove `task_id` from all signature entries in `refs/aet/breaker` (`BreakerStore`), ensuring neither per-task nor systemic circuit breakers block subsequent runs.
- **R-6**: **Stale Lease Reclamation & Lease Guard**. Check for active run leases. If a lease is stale (process dead), reclaim it automatically. If an active lease is held, refuse mutation unless `--force` is passed.
- **R-7**: **Actionable Operator Output**. Print a human-readable summary detailing the actions taken: reset mode (soft vs. hard), worktree status (preserved vs. removed), branch status (preserved vs. deleted), failure signatures cleared, stage set, and state transition (`<from_state> -> <to_state>`).

## User Stories

- As an operator or agent, I want to run `aet state reset <task_id>` after a task fails mid-execution so that its failure signatures are cleared, its state returns to `ready`, and `aet run` can resume work in the existing worktree without losing uncommitted progress. (satisfies: R-1, R-2, R-5, R-6, R-7)
- As an operator, I want to run `aet state reset <task_id> --hard` when an implementation went completely off the rails so that the branch and worktree are wiped and `aet run` starts the task completely from scratch. (satisfies: R-1, R-3, R-5, R-6, R-7)
- As an operator, I want to run `aet state reset <task_id> --stage tdd` to rewind a task to the TDD stage while keeping the worktree and branch. (satisfies: R-2, R-4, R-7)
- As an operator, I want to run `aet state reset <task_id> --dry-run` to preview what would be reset before committing changes. (satisfies: R-1, R-7)

## Acceptance Criteria

- [x] `aet state reset <task_id>` executes live mutations without requiring `--apply`. (satisfies: R-1)
- [x] `aet state reset <task_id> --dry-run` prints the planned actions without mutating the queue, git branches, worktrees, or breaker refs. (satisfies: R-1)
- [x] Soft reset retains `.worktrees/<task_id>` and the task branch, clears `failure_signatures`, updates state to `ready` (or `blocked`), and reports success even when derived status is `in_progress`. (satisfies: R-2, R-5, R-7)
- [x] Hard reset (`--hard` or `--clean`) removes `.worktrees/<task_id>`, deletes the local branch, clears `branch`, `worktree`, `run_id`, `stage`, and `failure_signatures`, and updates state to `ready` (or `blocked`). (satisfies: R-3, R-5, R-7)
- [x] Specifying `--stage <stage>` updates the stored stage in the task record during soft reset, while hard reset resets the stage to None. (satisfies: R-4)
- [x] Resetting a task removes its ID from `refs/aet/breaker` entries in `BreakerStore`. (satisfies: R-5)
- [x] If an active run lease is held by a live process, `aet state reset` halts with exit code unless `--force` is provided. Stale leases from dead processes are automatically reclaimed. (satisfies: R-6)
- [x] Console output clearly distinguishes between soft and hard reset actions and displays the resulting state. (satisfies: R-7)

## Technical Notes

- **CLI Surface (`src/aet/cli/aet_state.py`):**
  - Update `reset` Typer command arguments:
    - Deprecate `--apply` (or make it a no-op flag for backwards compatibility).
    - Add `--dry-run` (`bool = False`).
    - Add `--hard` / `--clean` (`bool = False`).
    - Add `--stage` (`Optional[str] = None`).
    - Retain `--force` (`bool = False`).
  - In `cmd_reset(args)`:
    - Remove the restriction `if derived_state not in ("ready", "blocked"): raise ... Cannot reset`.
    - Determine target state: check blocker completion. If all blockers in `task.get("blocked_by", [])` are terminal (`merged`, `abandoned`), target state is `ready`; otherwise `blocked`.
    - In soft reset:
      - Leave `worktree` and `branch` intact.
      - If `--stage` is given, validate stage against workflow and update `task["stage"] = args.stage`.
    - In hard reset:
      - Call `teardown_worktree(repo_root, task_id)` or `subprocess.run(["git", "-C", repo_root, "worktree", "remove", "--force", worktree_dir])`.
      - Delete branch: `subprocess.run(["git", "-C", repo_root, "branch", "-D", branch_name])`.
      - Clear `branch`, `worktree`, `run_id`, `stage` from task record.
    - Clear failure signatures: `task.pop("failure_signatures", None)`.
    - Update systemic breaker: instantiate `BreakerStore(repo_root)` and remove `task_id` from tracked signatures.
    - Apply transition to `target_state` with `_apply_transition(..., repair=True)` to bypass forward-only lifecycle restrictions for administrative repair.
    - Push backend and report output.

## Open Questions

- None. Both soft reset and hard reset modes were clarified and confirmed during intake triage.

---

*Stage: synced*
*Next step: run `aet-ship`*
