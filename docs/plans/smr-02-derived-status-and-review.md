# Plan: Integrate Derived Status with aet-work and Reviewer Independence

## Context

PRD: `docs/prds/state-mechanization-review-independence-prd.md`

## Goal

Wire aet-state into aet-work and enforce reviewer independence in aet-pipeline-implement.

## Tasks

### Task 1: Update aet-work/SKILL.md

- [ ] Replace direct JSON mutation with aet-state calls
- [ ] Update `status`, `next`, `run` commands to call `aet-state derive` before reading
- [ ] Update queue initialization to use aet-state for consistent status

### Task 2: Update aet-pipeline-implement review step

- [ ] Document reviewer independence requirement: review from disk artifacts only
- [ ] Add instruction to clear context or spawn fresh subagent before review
- [ ] Ensure review works from diff + plan files, not conversation memory

### Task 3: Add aet-state to aet-setup scaffold

- [ ] Add aet-state.py to the list of scripts scaffolded for new projects
- [ ] Document integration in aet-setup references

### Task 4: Migration guide

- [ ] Document how existing queues with stale statuses are repaired (run `aet-state derive`)

## Validation

- [ ] `make validate` passes
- [ ] `aet-work status` shows derived (not stored) status for a sample task
- [ ] A task marked merge-verified in JSON but not in git is shown as in-progress
- [ ] aet-pipeline-implement review step explicitly references disk artifacts

## Rollback

Revert aet-work/SKILL.md and aet-pipeline-implement/SKILL.md.

---

_Stage: plan-approved_
_Work class: normal_
_Next step: aet-pipeline-implement_
