# Bug Report: fods-03-read-path-zero-git review fix-now issues

## Metadata

- **Reported:** 2026-06-18T23:14:38Z
- **Severity:** high
- **Status:** resolved

## Symptoms

The `aet-review` report for branch `fods-03-read-path-zero-git` flagged three fix-now issues:

1. **Orchestrator failures do not update canonical state.** When a pipeline task fails, `aet-work/bin/orchestrator` called `mark_status(..., "failed", "pipeline")`, which only writes the legacy `status` field. Because `current_state()` prefers `task["state"]`, failed tasks retained their previous effective state (`ready` or `in_progress`). A failed `ready` task could therefore be selected again on the next spawn pass.
2. **`status` summary omits `awaiting_merge`.** `aet-work/bin/status` counted `planned`, `unblocked`, `blocked`, `in-progress`, `failed`, and `done`, but `_STATE_TO_STATUS` has no reverse mapping for `awaiting_merge`. Completed-but-unmerged tasks disappeared from the summary counts.
3. **Reference doc still documents removed `aet-state derive`.** `aet-plan/references/work-queue-format.md` described status as computed on read by `aet-state derive`, but that command was removed in this branch and repurposed as `audit`.

## Reproduction Steps

Confirmed with inline diagnostics on the worktree:

```python
from queue import current_state, state_to_status, mark_status, LEGAL_TRANSITIONS

queue = [{'id': 'T1', 'state': 'ready', 'status': 'unblocked'}]
mark_status(queue, 'T1', 'failed', 'pipeline')
assert current_state(queue[0]) == 'ready'  # Bug: still ready

assert state_to_status('awaiting_merge') == 'awaiting_merge'
assert 'awaiting_merge' not in {"planned", "unblocked", "blocked", "in-progress", "failed", "done"}
```

## Root Cause

- `mark_status()` was written for the legacy `status`-only model. After ADR-011 introduced `state` as the canonical field, failure paths in the orchestrator were not migrated to use the sole-state-writer transition.
- `_STATE_TO_STATUS` was incomplete: it mapped `ready`, `in_progress`, and some legacy strings, but not `awaiting_merge`.
- The shipped reference doc was not updated when `derive` was renamed/repurposed to `audit`.

## Fix Summary

- Added `ready -> failed` to `LEGAL_TRANSITIONS` in `aet-work/lib/queue.py` so a task can be marked failed during the `ready -> in_progress` pickup attempt.
- Introduced `_mark_failed()` in `aet-work/bin/orchestrator` that routes failure marking through `aet-state transition <task_id> <from_state> failed <queue_file>`, with a `mark_status` fallback if the transition fails.
- Replaced the three `mark_status(..., "failed", "pipeline")` calls in the orchestrator with `_mark_failed()`.
- Added `"awaiting_merge"` to the summary counts in `aet-work/bin/status`.
- Rewrote the derived-status section of `aet-plan/references/work-queue-format.md` to describe stored-state reads and the `aet-state audit` reconciliation command.

**Files modified:**

- `aet-work/lib/queue.py`
- `aet-work/bin/orchestrator`
- `aet-work/bin/status`
- `aet-plan/references/work-queue-format.md`
- `tests/test_aet_work_read_side.py`
- `tests/test_orchestrator_derived.py`

**Key change:** Orchestrator failure paths now mutate canonical `state` through `aet-state transition`, keeping stored state consistent with observed pipeline outcomes.

**Side effects:** None beyond the bug fixes. Legacy `status` remains in sync during the fods-02..fods-05 coexistence window.

## Regression Test

- `tests/test_aet_work_read_side.py::TestStatusStoredState::test_counts_include_awaiting_merge` verifies `awaiting_merge` appears in `status` counts.
- `tests/test_orchestrator_derived.py::TestMarkFailed::test_mark_failed_updates_canonical_state` verifies `_mark_failed` updates `state` for an `in_progress` task.
- `tests/test_orchestrator_derived.py::TestMarkFailed::test_mark_failed_ready_to_failed_is_legal` verifies the new `ready -> failed` transition path.

## Validation

- [x] Reproduction steps no longer trigger the bug
- [x] Existing test suite passes with no new failures (`97 passed`)
- [x] `make validate` passes (lint, format, skill structure, reproducible packaging)
- [x] No regressions observed in related functionality

## Lessons Learned

- **Pattern:** State-model migrations require auditing every legacy write path, not just the read paths. A helper that writes only the legacy field silently becomes a consistency bug when reads prefer a new canonical field.
- **Prevention:** When introducing a canonical field that shadows a legacy field, grep for all assignments to the legacy field and migrate them in the same change set.
- **Reference:** ADR-011 (forward-only deterministic state model).
