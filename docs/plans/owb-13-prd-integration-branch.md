---
id: owb-13-prd-integration-branch
size: S
work_class: normal
blocked_by:
  - owb-01-spec-travels-in-task-record
pipeline: standard
security_review: required
docs_sync: required
---

# Plan: Derive the Integration Branch from the PRD

## Context

- PRD: `docs/prds/open-work-board-prd.md`
- Requirement: R-17
- ADR-045 already implements `integration_mode: single-pr`

One PR per epic, per-task branches local and ephemeral, epic-level merge verification, and a serialized integration step all exist and were rehearsed by `t2r-13`. `integration_branch` is a single static config value, so the epic is whatever was last configured.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] The PRD's one reproducible-defect item routes to `aet-bug-report`

## Task List

1. **Derive the integration branch from the task's PRD**, so concurrent PRDs each carry their own branch and PR — S (traces: R-17)
2. **Keep ADR-045's Scenario A intact**: `pr-per-task` with `integration_branch == trunk_branch` must remain the degenerate case, not a special case — S (traces: R-17)
3. **Test two PRDs in flight**: two integration branches, two PRs, no per-task branch on `origin` — S (traces: R-17)
4. Merge branch to main and verify integration — S

## Floor Check

- [x] Stands alone: a routing change on top of an implemented mode.
- [x] Diff exceeds overhead once the two-PRD test is included.
- [x] Cannot precede `owb-01`: worktrees refresh more often under `single-pr`, so the overlay must be gone first.

## Rejected Alternatives

- **A static config value per epic** — rejected: switching epics means reconfiguring, which precludes concurrent PRDs.
- **A branch per task pushed to origin** — rejected: ADR-045 §4 guarantees the opposite.

## Files to Modify

- `src/aet/backends/factory.py`
- `src/aet/cli/orchestrator.py`
- `src/aet/cli/ship.py`
- `tests/orchestrator/`

## Validation Steps

- [ ] Two PRDs in flight produce two branches and two PRs
- [ ] No per-task branch reaches `origin`
- [ ] Scenario A behaviour is unchanged
- [ ] Lint passes
- [ ] Tests pass
- [ ] R-trace coverage: every R-id cited above is covered by a task
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert to the configured static branch. No history is rewritten.

---

*Stage: plan-approved*

*Next step: run aet sprint add docs/plans/owb-13-prd-integration-branch.md*
