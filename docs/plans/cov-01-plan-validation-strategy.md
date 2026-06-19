---
id: cov-01-plan-validation-strategy
blocked_by: []
size: M
---

# Plan: aet-plan — Concrete Validation Strategy Requirement

## Context

PRD: `docs/prds/auth-infra-blind-spots-prd.md` — Story 1.

The `plan` command in `aet-plan` currently produces a validation strategy section that often contains vague statements ("add unit tests", "write tests for new behavior"). This passes through planning without catching zero-coverage modules. The fix: require the validation strategy to name at least one specific test per new file or module introduced by the plan.

Also strengthen the plan template so future plans produced from it carry the right prompt.

**ADR 001 framing note:** The changes to `aet-plan/SKILL.md` implement test coverage as a new domain in the Cross-Cutting Completeness framework (ADR `docs/adr/001-cross-cutting-completeness.md`). When editing the skill, frame the validation strategy gate as: "When a plan introduces new source files, verify each has a named test in the validation strategy." This connects the change to the established framework rather than appearing as an isolated rule.

## Tasks

1. Edit `aet-plan/SKILL.md` — in the `plan` command procedure, after the task list step, add a "Validation strategy gate": the validation strategy must list, for each new file or module, at least one named test. A strategy that only says "add tests" without naming what is flagged as incomplete and must be revised before the plan is saved as `plan-draft`. — **S**

2. Edit `aet-plan/SKILL.md` — in the `plan` command procedure, add a note that the validation strategy must distinguish: unit tests (single layer), integration tests (cross-layer within backend/frontend), and API boundary tests (frontend ↔ backend contract for vertical slices that introduce both sides). — **S**

3. Edit `.agents/templates/plan-template.md` — replace the generic "Manual verification step" placeholder in the Validation Steps section with a structured prompt: "For each new source file introduced by this plan, name the test that will cover it." — **S**

4. Merge branch to main and verify integration — **S**

## Dependencies

None — this plan is self-contained.

## Validation Steps

- [ ] `make validate` passes (lint + format + skill-structure validator)
- [ ] `aet-plan/SKILL.md` is under 400 lines after changes
- [ ] A sample plan produced using the updated `plan` command would be rejected if its validation strategy did not name per-module tests
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert edits to `aet-plan/SKILL.md` and `.agents/templates/plan-template.md`. No downstream data is affected.

---

_Stage: plan-approved_
_Next step: run `aet-pipeline-implement` or `aet-work`_
