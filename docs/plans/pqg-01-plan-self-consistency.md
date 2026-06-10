# Plan: Plan Self-Consistency Lint, Implement Reconciliation, and Completeness Lens

## Context
PRD: `docs/prds/plan-quality-gates-prd.md`

## Goal
Add plan quality validation: self-consistency lint, implement reconciliation, and behavior-driven completeness checks.

## Tasks

### Task 1: Add plan self-consistency lint
- [ ] Add lint procedure to aet-plan completion or aet-validate-scope
- [ ] Check 1: every constraint in prose appears in code blocks
- [ ] Check 2: every file in "files to modify" appears in a task
- [ ] Check 3: every acceptance criterion is an observable behavior (not a task restatement)
- [ ] Document lint output format (PASS/WARN/FAIL per check)

### Task 2: Update aet-implement with reconciliation
- [ ] Add procedure: compare prose constraints against code blocks before implementation
- [ ] If disagreement found, stop and flag — do not silently follow code block
- [ ] Document the reconciliation question in SKILL.md

### Task 3: Update aet-review completeness lens
- [ ] Change from "tasks ticked" to "behavior delivered"
- [ ] Add verification question: "If I exercised this as the user, what would I see?"
- [ ] Document how this catches missing CSS, endpoints, error states

## Validation
- [ ] `make validate` passes
- [ ] A plan with a prose constraint missing from code blocks is flagged by lint
- [ ] A plan with "files to modify" not assigned to tasks is flagged
- [ ] aet-implement stops when prose and code blocks disagree
- [ ] aet-review completeness lens catches a missing error state

## Rollback
Revert affected skill files from git.

---

*Stage: plan-approved*
*Work class: normal*
*Next step: aet-pipeline-implement*
