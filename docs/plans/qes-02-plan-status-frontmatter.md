---
id: qes-02-plan-status-frontmatter
size: S
blocked_by: []
pipeline: standard
---

# Plan: Add Status Field to Plan Frontmatter

## Context

Part of [PRD: Ephemeral Sprint Board for aet-work](../prds/aet-work-queue-ephemeral-sprint-board-prd.md). Plan files become the source of truth for whether a task is open or closed. The frontmatter needs a `status` field so `aet-work review` and `aet-ship` can read it deterministically.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [ ] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. Update `.agents/templates/plan-template.md` to include `status: approved` in frontmatter — S
2. Update the skill-structure validator to accept and validate the `status` field — S
3. Update `docs/CONVENTIONS.md` if it documents plan frontmatter — S
4. Merge branch to main and verify integration — S

## Files to Modify

- `.agents/templates/plan-template.md`
- `scripts/validate-skills.sh` (or the validator it invokes)
- `docs/CONVENTIONS.md`

## Validation Steps

- [ ] `make validate` passes
- [ ] New plan files generated from the template include `status`
- [ ] Invalid `status` values are rejected by the validator

## Rollback Plan

1. Revert changes to the template, validator, and conventions.
2. Re-run `make validate`.

---

_Stage: plan-approved_
_Next step: run `aet-work`_
