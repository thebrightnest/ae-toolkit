---
id: sci-02-validator-and-contradictions
blocked_by: []
size: M
---

# Plan: Extend Validator and Fix Composition Contradictions

## Context

PRD: `docs/prds/skill-composition-integrity-prd.md`

## Goal

Extend validate-skills.sh to catch composition errors, then fix the identified contradictions.

## Tasks

### Task 1: Extend validate-skills.sh

- [ ] Add check: completion-protocol "next step" pointers form a consistent graph with docs/PIPELINE.md
- [ ] Add check: no two skills share a trigger phrase
- [ ] Add check: preamble blocks match canonical template (from scripts/partials/)
- [ ] Document new validator checks in comments

### Task 2: Fix aet-pipeline-implement contradiction

- [ ] Remove "write all failing tests first, then all implementation" language
- [ ] Align with aet-tdd's vertical slice approach (one test + one implementation together)
- [ ] Update completion protocol

### Task 3: Fix README order contradiction

- [ ] Align README canonical order with actual pipeline execution
- [ ] Document the correct order: Implement → Review → QA (or whatever the canonical order is)

### Task 4: Disambiguate aet-plan vs aet-pipeline-plan triggers

- [ ] aet-plan: "design this feature", "help me design", "create a PRD"
- [ ] aet-pipeline-plan: "plan and validate this feature", "full planning pipeline"
- [ ] Update both SKILL.md files with distinct triggers

## Validation

- [ ] `make validate` passes
- [ ] Validator catches a deliberately introduced trigger collision (test case)
- [ ] Validator catches a deliberately introduced next-step mismatch (test case)
- [ ] aet-tdd and aet-pipeline-implement agree on test-writing approach

## Rollback

Revert validate-skills.sh and affected skill files.

---

_Stage: plan-approved_
_Work class: normal_
_Next step: aet-pipeline-implement_
