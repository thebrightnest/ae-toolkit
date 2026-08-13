---
id: owb-04-plan-tooling-and-board-review
size: M
work_class: normal
blocked_by:
  - owb-01-spec-travels-in-task-record
pipeline: standard
security_review: required
docs_sync: required
---

# Plan: Plan Tooling Reads Live Work; `gate review` Reads the Board

## Context

- PRD: `docs/prds/open-work-board-prd.md`
- Requirement: R-6
- Decision: `aet gate review` is kept as the shadow-mode board

After `owb-01` a project may have task records and no plan files at all, so every tool that globs `docs/plans/*.md` needs its input reconsidered.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] The PRD's one reproducible-defect item routes to `aet-bug-report`

## Task List

1. **Re-point `aet gate review` at the board** rather than a directory glob, so it works in shadow posture where no plan file need exist — M (traces: R-6)
2. **Keep `plan validate`, `plans lint` and the R-trace lint on live work only**, so they do not degrade as settled plans accumulate — M (traces: R-6)
3. **Keep ADR-046 delivered-size measurement working** against the rendered spec — S (traces: R-6)
4. **Assert stability**: tool runtime and output unchanged after 50 simulated closures — S (traces: R-6)
5. Merge branch to main and verify integration — S

## Floor Check

- [x] Stands alone: the tooling contract is separately reviewable from the record change.
- [x] Diff exceeds overhead: four consumers and a scale test.
- [x] Cannot precede `owb-01`.

## Rejected Alternatives

- **Delete `gate review`** — rejected by the operator: it is the shadow-mode board, where GitHub renders nothing.
- **Leave the globs and accept drift** — rejected: the degradation is unbounded.

## Files to Modify

- `src/aet/cli/gate.py`
- `src/aet/plans_lint.py`
- `src/aet/plan_validate.py`
- `src/aet/plan_size.py`
- `tests/plan/`, `tests/gate/`

## Validation Steps

- [ ] `gate review` renders a board with no plan files present
- [ ] Lint output is unchanged after 50 simulated closures
- [ ] Lint passes
- [ ] Tests pass
- [ ] R-trace coverage: every R-id cited above is covered by a task
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Restore the directory globs. No stored data changes.

---

*Stage: plan-approved*

*Next step: run aet sprint add docs/plans/owb-04-plan-tooling-and-board-review.md*
