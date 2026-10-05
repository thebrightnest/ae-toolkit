---
id: tsr-01-task-state-reset-and-recovery
size: M
work_class: normal
blocked_by: []
pipeline: standard
security_review: skipped
security_review_reason: CLI command for local task state manipulation; touches no secrets, auth tokens, or network boundaries.
docs_sync: required
docs_sync_reason: CLI command interface changes require docs/CLI.md regeneration and documentation sync.
---

# Plan: Task State Reset and Recovery

## Context

PRD: `docs/prds/task-state-reset-and-recovery-prd.md`

When a task run fails, times out, or gets interrupted mid-execution, its queue state often remains `in_progress`, `failed`, or `quarantined`, with accumulated failure signatures or stale leases. Previously, running `aet state reset <task_id>` failed if the branch or worktree still existed because it checked whether the git-derived state was `ready` or `blocked`. If the branch had commits, derived state was `in_progress`, causing `aet state reset` to reject the command with `Cannot reset <task_id>: derived state is in_progress, not ready/blocked`. Furthermore, the command defaulted to dry-run (requiring an unintuitive `--apply` flag) and lacked the ability to differentiate between resuming work in-place versus wiping the workspace for a clean-slate re-run.

This plan refactors `aet state reset` into an intuitive recovery command that executes live by default, supports both soft reset (preserving worktree and branch for resuming in-place) and hard reset (`--hard` / `--clean` for tearing down worktree and branch), resets circuit breaker failure counts in `refs/aet/breaker`, and clears stale leases so that `aet run` can immediately proceed.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [ ] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. **Update `BreakerStore` to support single-task removal** — S (traces: R-5)
   Add a `remove_task(task_id: str) -> bool` method to `BreakerStore` in `src/aet/breaker.py` that prunes all occurrences of `task_id` from the systemic tally dict and updates `refs/aet/breaker`.

2. **Refactor `cmd_reset` and CLI parser in `src/aet/cli/aet_state.py`** — M (traces: R-1, R-2, R-3, R-4, R-5, R-6, R-7)
   - Update Typer command `reset` to make live execution the default: replace `--apply` with `--dry-run` (retaining `--apply` as an ignored legacy compatibility flag), and add `--hard` (alias `--clean`), `--stage`, and `--force`.
   - In `cmd_reset`:
     - Run `lease_guard` to verify or reclaim stale leases; allow `--force` override.
     - Determine target state based on blockers: if all blockers are in `{"merged", "abandoned"}` (or if `blocked_by` is empty), target state is `ready`; otherwise `blocked`.
     - In **Soft Reset** (default):
       - Keep `.worktrees/<task_id>` and local git branch intact.
       - If `--stage` is provided, set `task["stage"] = args.stage`.
       - Clear `task["failure_signatures"]`.
       - Prune `task_id` from `BreakerStore(repo_root)`.
       - Transition task to target state using `_apply_transition(..., repair=True)`.
     - In **Hard Reset** (`--hard` / `--clean`):
       - Remove `.worktrees/<task_id>` forcefully via `git worktree remove --force` or `teardown_worktree`.
       - Delete the local branch via `git branch -D <branch_name>`.
       - Clear runtime fields: `branch`, `worktree`, `run_id`, `stage`, and `failure_signatures`.
       - Prune `task_id` from `BreakerStore(repo_root)`.
       - Transition task to target state using `_apply_transition(..., repair=True)`.
     - Handle `--dry-run`: compute and print all planned actions (mode, worktree, branch, failure signatures, stage, target state) without mutating queue or git state.
     - Print clear, actionable operator output summarizing actions taken.

3. **Expand unit and integration tests in `tests/state/test_state_reset.py`** — M (traces: R-1, R-2, R-3, R-4, R-5, R-6, R-7)
   - Add tests for default live execution (verifying mutations occur without `--apply`).
   - Add tests for `--dry-run` (verifying no state or git changes occur).
   - Add tests for soft reset with an existing branch and worktree (verifying branch/worktree are kept, failure signatures cleared, breaker pruned, and state set to `ready`).
   - Add tests for hard reset (`--hard`) with an existing branch and worktree (verifying worktree is removed, branch is deleted, runtime fields cleared, and state set to `ready`).
   - Add tests for `--stage` parameter on soft reset and stage clearing on hard reset.
   - Add tests for `BreakerStore.remove_task`.
   - Add tests for lease handling with and without `--force`.

4. **Regenerate documentation with `aet docs generate`** — S (traces: R-1, R-7)
   Update `docs/CLI.md` from Typer definitions using `aet docs generate` to reflect the updated options on `aet state reset`.

5. **Merge branch to main and verify integration** — S (traces: R-1, R-2, R-3, R-4, R-5, R-6, R-7)
   Run `make validate` to verify all linters, skill validations, and tests pass, then rebase and integrate cleanly onto trunk.

### Floor Check

- [ ] Expected diff is below the calibrated floor threshold (≤ 50 headline lines).
- [ ] The change is limited to one subsystem and maintains no architectural invariant.
- [ ] `Files to Modify` substantially overlaps a sibling this plan is linearly ordered against.
- [ ] This is docs-only and its sole consumer is a single sibling.

*Justification: This plan touches CLI recovery commands, circuit breaker persistence, and documentation across multiple modules with comprehensive test coverage (~250-400 diff lines), well above the floor threshold.*

## Rejected Alternatives

- **Relying solely on `aet state heal`** — rejected: `heal` strictly computes state from current git refs across all tasks; it does not clear breaker signatures or unwedge tasks whose worktree still exists.
- **Requiring manual git branch deletion prior to reset** — rejected: forces the operator or agent into manual git surgery and dozens of context-wasting exploratory commands.
- **Defaulting to dry-run with `--apply`** — rejected: violates the core AE Toolkit rule against default dry-run mode and frustrates automated workflows.

## Files to Modify

- `src/aet/breaker.py`
- `src/aet/cli/aet_state.py`
- `tests/state/test_state_reset.py`
- `docs/CLI.md`

## Validation Steps

- [x] Lint passes (`make lint-py`)
- [x] Tests pass (`pytest tests/state/test_state_reset.py tests/test_breaker.py`)
- [x] R-trace coverage: every in-scope R-id (R-1 through R-7) is covered by ≥ 1 task
- [x] Named tests covering modifications:
  - `tests/test_breaker.py::test_breaker_remove_task`
  - `tests/state/test_state_reset.py::TestStateReset::test_reset_live_by_default`
  - `tests/state/test_state_reset.py::TestStateReset::test_reset_dry_run_flag`
  - `tests/state/test_state_reset.py::TestStateReset::test_soft_reset_preserves_worktree_and_resets_ready`
  - `tests/state/test_state_reset.py::TestStateReset::test_hard_reset_cleans_worktree_and_branch`
  - `tests/state/test_state_reset.py::TestStateReset::test_reset_clears_failure_signatures_and_breaker`
  - `tests/state/test_state_reset.py::TestStateReset::test_reset_stage_flag`
  - `tests/state/test_state_reset.py::TestStateReset::test_reset_lease_guard_and_force`
- [x] Unit tests (single layer in `tests/test_breaker.py`), integration tests (cross-layer in `tests/state/test_state_reset.py`)
- [x] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the commits associated with `tsr-01`. The previous `cmd_reset` implementation remains compatible with existing task records.

## Pipeline

`pipeline: standard` (default grouping: TDD -> implement -> QA -> review -> CSO).
