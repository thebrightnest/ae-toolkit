---
blocked_by:
  - owb-05-board-is-open-work
docs_sync: required
id: owb-07-git-refs-only-store
pipeline: full
security_review: required
size: M
work_class: critical
---

# Plan: git-refs Is the Only Task Store

## Context

- PRD: `docs/prds/open-work-board-prd.md`
- Requirement: R-11

The operator has no non-git projects, so the json backend's stated purpose — non-git contexts — no longer applies. Removing the choice removes the defect class: this audit found three backend-specific bugs, each from shared logic reaching around the abstraction.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] The PRD's one reproducible-defect item routes to `aet-bug-report`

## Task List

1. ✓ **Remove the json backend** and the `task_backend` selection axis — M (traces: R-11) [Changed: blast radius reached 80 files, not only the listed six]
2. ✓ **Collapse the backend abstraction** to what one store needs — M (traces: R-11) [Changed: `TaskBackend.seal` default implementation removed; `GitRefsBackend` already overrides it]
3. ✓ **Fail a surviving `task_backend` key** with a migration message rather than ignoring it — S (traces: R-11)
4. ✓ **Correct `CONVENTIONS.md:350`**, which presents json as the non-git-context backend — S (traces: R-11)
5. [Deferred: owned by `aet-ship`] Merge branch to main and verify integration — S

## Floor Check

- [x] Stands alone: a store removal, separately revertable.
- [x] Diff exceeds overhead: a backend, a factory, a config axis, docs.
- [x] Cannot precede `owb-05`, which removes the shared settled-ness logic first.

## Rejected Alternatives

- **Keep json for non-git contexts** — rejected by the operator: there are none.
- **Keep the abstraction for a future forge store** — rejected: multi-user is a non-goal, and a forge store buys only multi-user.

## Files to Modify

- `src/aet/backends/json_backend.py` (deleted)
- `src/aet/backends/factory.py`
- `src/aet/backends/base.py`
- `src/aet/cli/configure_backend.py`
- `docs/CONVENTIONS.md`
- `tests/backends/`

## Validation Steps

- [x] `grep -rn "work-queue.json\|task_backend" src/` returns nothing
- [x] A config carrying `task_backend` fails with a migration message
- [x] Lint passes
- [x] Tests pass
- [x] R-trace coverage: every R-id cited above is covered by a task
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main` [Deferred: owned by `aet-ship`]

## Rollback Plan

Revert. Queue data lives in refs either way; no migration is undone.

---

*Stage: synced*
*Next step: run `aet-ship`*
