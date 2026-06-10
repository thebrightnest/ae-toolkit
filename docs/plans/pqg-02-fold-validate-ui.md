# Plan: Fold aet-validate-ui into aet-validate-scope

## Context
PRD: `docs/prds/plan-quality-gates-prd.md`

## Goal
Merge aet-validate-ui's checklist into aet-validate-scope as a lens, then remove the standalone skill.

## Tasks

### Task 1: Migrate checklist content
- [ ] Copy aet-validate-ui's seven-category checklist into aet-validate-scope/references/ui-coverage-lens.md
- [ ] Adapt checklist items as review lens prompts (not keyword matching)
- [ ] Ensure no content is lost

### Task 2: Update aet-validate-scope/SKILL.md
- [ ] Add UI coverage as a lens within the scope validation procedure
- [ ] Document when to apply it (PRDs with UI components)
- [ ] Keep SKILL.md under 400 lines after addition

### Task 3: Remove aet-validate-ui skill
- [ ] Delete aet-validate-ui/ directory
- [ ] Update README.md skill table
- [ ] Update any references to aet-validate-ui in other skills

### Task 4: Update build system
- [ ] Remove aet-validate-ui from make package targets
- [ ] Validate no broken links

## Validation
- [ ] `make validate` passes
- [ ] `make package` no longer produces aet-validate-ui.skill
- [ ] aet-validate-scope/SKILL.md under 400 lines
- [ ] All aet-validate-ui references updated or removed

## Rollback
Restore aet-validate-ui/ from git; revert aet-validate-scope changes.

---

*Stage: plan-approved*
*Work class: normal*
*Next step: aet-pipeline-implement*
