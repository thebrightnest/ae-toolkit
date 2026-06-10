# Plan: Extend Validator and Fix Composition Contradictions

## Context

PRD: `docs/prds/skill-composition-integrity-prd.md`

## Goal

Extend validate-skills.sh to catch composition errors, then fix the identified contradictions.

## Tasks

### Task 1: Extend validate-skills.sh

- [x] Add check: completion-protocol "next step" pointers form a consistent graph with docs/PIPELINE.md
- [x] Add check: no two skills share a trigger phrase
- [x] Add check: preamble blocks match canonical template (from scripts/partials/)
- [x] Document new validator checks in comments

### Task 2: Fix aet-pipeline-implement contradiction

- [x] Remove "write all failing tests first, then all implementation" language
- [x] Align with aet-tdd's vertical slice approach (one test + one implementation together)
- [x] Update completion protocol

### Task 3: Fix README order contradiction

- [x] Align README canonical order with actual pipeline execution
- [x] Document the correct order: Implement → QA → Review

### Task 4: Disambiguate aet-plan vs aet-pipeline-plan triggers

- [x] aet-plan: "design this feature", "help me design", "create a PRD"
- [x] aet-pipeline-plan: "plan and validate this feature", "full planning pipeline"
- [x] Update both SKILL.md files with distinct triggers

## Validation

- [x] `make validate` passes
- [x] Validator catches a deliberately introduced trigger collision (test case)
- [x] Validator catches a deliberately introduced next-step mismatch (test case)
- [x] aet-tdd and aet-pipeline-implement agree on test-writing approach

## Rollback

Revert validate-skills.sh and affected skill files.

---

_Stage: synced_
_Work class: normal_
_Next step: run `aet-ship`, then `post-ship-verify` to reach `merged`_
