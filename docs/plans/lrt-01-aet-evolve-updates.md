# Plan: Update aet-evolve with Schema, Retro Debt, and Escalation Ladder

## Context

PRD: `docs/prds/learning-ratchet-prd.md`

## Goal

Enhance aet-evolve with operational retrieval, action item closure, and recurrence escalation.

## Tasks

### Task 1: Update learning schema

- [ ] Add `trigger` field to learnings.jsonl entries (string or list of keywords)
- [ ] Update aet-evolve/SKILL.md to use trigger-based matching instead of "top-3 relevant"
- [ ] Ensure backward compatibility with entries lacking the trigger field

### Task 2: Add retro debt check

- [ ] Add step 1 to aet-evolve retro procedure: check previous retro action items
- [ ] Define outcomes: verified done → mark complete; not done → convert to queue task or explicitly drop
- [ ] Document the debt check in SKILL.md

### Task 3: Document escalation ladder

- [ ] Create `aet-evolve/references/escalation-ladder.md`
- [ ] Define stages: documentation → checklist item → review lens → executable gate
- [ ] Define transition criteria (e.g., 2nd recurrence → checklist; 3rd → lens; 4th → gate)
- [ ] Reference the ladder in SKILL.md

## Validation

- [ ] `make validate` passes
- [ ] aet-evolve/SKILL.md under 400 lines
- [ ] A learning entry with trigger field is correctly matched when the trigger keyword appears in context
- [ ] Retro procedure includes debt check at step 1

## Rollback

Revert aet-evolve/SKILL.md and delete new reference file.

---

_Stage: plan-approved_
_Work class: normal_
_Next step: aet-pipeline-implement_
