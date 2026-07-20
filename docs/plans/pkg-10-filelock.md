---
id: pkg-10-filelock
size: M
blocked_by:
  - pkg-03-lib-extraction
pipeline: standard
status: queued
security_review: required
security_review_reason: Adds the filelock runtime dependency and changes concurrency behavior — requires review of stale-lock semantics.
docs_sync: required
docs_sync_reason: Any stale-lock behavior differences vs. the hand-rolled implementation must be recorded in the PRD divergence note.
---

# Plan: Replace Hand-Rolled Locking with `filelock` (A4)

## Context

PRD: `docs/prds/aet-package-extraction-prd.md` (R-7).
`src/aet/aet_queue.py` (queue) and `src/aet/worktree.py` do their own
lock-file handling (see `.agents/work-queue.json.lock`). Replace with the
`filelock` package, preserving timeout/stale-lock behavior observed by the
orchestrator.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. Add `filelock` to `pyproject.toml` runtime dependencies — S (traces: R-7)
2. Replace queue locking in `src/aet/aet_queue.py` with `filelock.FileLock`;
   preserve lock file location (`.agents/work-queue.json.lock`) and timeout
   semantics — M (traces: R-7)
3. Replace worktree locking in `src/aet/worktree.py` the same way — M
   (traces: R-7)
4. Run and update concurrency tests: `tests/test_concurrent_state.py`,
   `tests/test_queue_guard.py`, `tests/test_quarantined_state.py` must pass;
   add a stale-lock test if the behavior contract changes — S (traces: R-7)
5. Merge branch to main and verify integration — S

**Size definitions:**

- **S**: ≤ 2 hr human time / ≤ 3 files / ≤ 100 diff lines
- **M**: ≤ 1 day human time / ≤ 5 files / ≤ 200 diff lines
- **L**: > 1 day OR > 5 files OR > 200 lines — **must be split before implementation**

### Batching Check

- [x] Two call sites of one concern; one plan keeps the locking contract
  consistent across both.

## Rejected Alternatives

- **Keep hand-rolled locking** — rejected: PRD R-7; stale-lock and
  cross-platform edge cases are exactly what `filelock` exists for.
- **`portalocker`** — rejected: `filelock` is the smaller, more widely used
  dependency; no need for its extra API surface.

## Files to Modify

- `pyproject.toml`
- `src/aet/aet_queue.py`
- `src/aet/worktree.py`
- `tests/test_concurrent_state.py`, `tests/test_queue_guard.py`,
  `tests/test_quarantined_state.py` (updates only if contracts shift)

## Validation Steps

- [ ] Named existing tests pass: `tests/test_concurrent_state.py`,
  `tests/test_queue_guard.py`, `tests/test_quarantined_state.py`,
  `tests/test_queue.py`
- [ ] Concurrency stress: two parallel `aet sync` invocations cannot corrupt
  `.agents/work-queue.json` (existing test coverage demonstrates this)
- [ ] `make validate` green
- [ ] R-trace coverage: R-7 by tasks 1–4; no unknown R-ids cited
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

`git revert`; the lock file format on disk is unchanged (same path), so no
state migration is needed either direction.

---

*Stage: secure*
*Next step: run `aet-sync-docs`, then `aet-ship`*
