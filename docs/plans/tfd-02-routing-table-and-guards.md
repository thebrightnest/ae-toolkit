# Plan: Work-Class Routing Table, Symmetric Guards, and Diff Budget

## Context

PRD: `docs/prds/triage-front-door-work-class-routing-prd.md`

## Goal

Implement the routing infrastructure: table definition, symmetric redirects between aet-plan and aet-bug-report, and the diff budget for fixes.

## Tasks

### Task 1: Create docs/PIPELINE.md (routing section)

- [x] Document the three work classes with examples
- [x] Document the pipeline mapping for each class
- [x] Document the classification decision tree

### Task 2: Update aet-plan and aet-pipeline-plan with symmetric guard

- [x] Add intake question: "Is this a reproducible defect in existing code?"
- [x] If yes, redirect to aet-bug-report with explanation
- [x] Update SKILL.md completion protocol to mention routing guard

### Task 3: Update aet-bug-report with symmetric guard and diff budget

- [x] Add intake question: "Is this a new capability or redesign?"
- [x] If yes, redirect to aet-plan
- [x] Add diff budget check: > 3 files or > 100 lines requires explicit justification
- [x] Document the justification format (why minimal fix is insufficient)

### Task 4: Update Shared Preamble

- [x] Add the intake triage question to the preamble template
- [x] Ensure all entry-point skills include it

## Validation

- [x] `make validate` passes (skill structure + changed files lint clean)
- [x] A reproducible defect description routed to aet-plan is caught and redirected
- [x] A feature request routed to aet-bug-report is caught and redirected
- [x] A bug fix diff > 100 lines triggers the justification requirement

## Rollback

Revert edited skill files from git.

---

_Stage: synced_
_Work class: normal_
_Next step: run `aet-ship`, then `post-ship-verify` to reach `merged`_
