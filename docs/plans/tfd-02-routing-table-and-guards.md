# Plan: Work-Class Routing Table, Symmetric Guards, and Diff Budget

## Context
PRD: `docs/prds/triage-front-door-work-class-routing-prd.md`

## Goal
Implement the routing infrastructure: table definition, symmetric redirects between aet-plan and aet-bug-report, and the diff budget for fixes.

## Tasks

### Task 1: Create docs/PIPELINE.md (routing section)
- [ ] Document the three work classes with examples
- [ ] Document the pipeline mapping for each class
- [ ] Document the classification decision tree

### Task 2: Update aet-plan and aet-pipeline-plan with symmetric guard
- [ ] Add intake question: "Is this a reproducible defect in existing code?"
- [ ] If yes, redirect to aet-bug-report with explanation
- [ ] Update SKILL.md completion protocol to mention routing guard

### Task 3: Update aet-bug-report with symmetric guard and diff budget
- [ ] Add intake question: "Is this a new capability or redesign?"
- [ ] If yes, redirect to aet-plan
- [ ] Add diff budget check: > 3 files or > 100 lines requires explicit justification
- [ ] Document the justification format (why minimal fix is insufficient)

### Task 4: Update Shared Preamble
- [ ] Add the intake triage question to the preamble template
- [ ] Ensure all entry-point skills include it

## Validation
- [ ] `make validate` passes
- [ ] A reproducible defect description routed to aet-plan is caught and redirected
- [ ] A feature request routed to aet-bug-report is caught and redirected
- [ ] A bug fix diff > 100 lines triggers the justification requirement

## Rollback
Revert edited skill files from git.

---

*Stage: plan-approved*
*Work class: normal*
*Next step: aet-pipeline-implement*
