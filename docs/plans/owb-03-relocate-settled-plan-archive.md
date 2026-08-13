---
id: owb-03-relocate-settled-plan-archive
size: S
work_class: normal
blocked_by: []
pipeline: standard
security_review: required
docs_sync: required
---

# Plan: Archive Settled Plans Outside the Repository

## Context

- PRD: `docs/prds/open-work-board-prd.md`
- Requirement: R-5

`docs/plans/archive/` holds 264 tracked files, and archiving is what makes closure a commit. `metrics.py` threads `archive_dir` into `iter_settled_tasks`, so the archive is read — it cannot simply be dropped.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] The PRD's one reproducible-defect item routes to `aet-bug-report`

## Task List

1. **Archive to `~/.aet/<slug>/plans/archive/`** at closure, consistent with ADR-055 decision 4 putting reports and telemetry machine-local — S (traces: R-5)
2. **Point `aet metrics` at the new location only.** No dual-read — S (traces: R-5)
3. **One-time copy of the 264 legacy files** so historical metrics survive the cutover — S (traces: R-5)
4. **Leave the legacy directory tracked and inert.** Untracking it is a 264-file diff and the operator's call — S (traces: R-5)
5. Merge branch to main and verify integration — S

## Floor Check

- [x] Stands alone: it removes AET artifacts from the repo without depending on the render model.
- [x] Diff exceeds overhead: a destination change, a metrics input, a migration.
- [ ] Could share a branch with `owb-02` — kept separate because one is a commit-path change and the other a data relocation.

## Rejected Alternatives

- **Leave settled plans in `docs/plans/`** — rejected: `plans_lint`, `plan validate`, the R-trace lint and `gate review` all glob that directory and would degrade as settled work accumulates.
- **Delete the archive** — rejected: `aet metrics` reads it.
- **Dual-read old and new** — rejected by the operator; a one-time copy achieves the same with one read path.

## Files to Modify

- `src/aet/queue.py`
- `src/aet/metrics.py`
- `src/aet/telemetry.py`
- `tests/metrics/`, `tests/migration/`

## Validation Steps

- [ ] `aet metrics` reports identical per-class figures before and after
- [ ] Closure writes no file inside the repository
- [ ] Lint passes
- [ ] Tests pass
- [ ] R-trace coverage: every R-id cited above is covered by a task
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Point the archive destination back at `docs/plans/archive/`. Copied files are duplicates, not moves, so nothing is lost.

---

*Stage: plan-approved*

*Next step: run aet sprint add docs/plans/owb-03-relocate-settled-plan-archive.md*
