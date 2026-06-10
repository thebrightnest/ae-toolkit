# Plan: Update aet-evolve with Schema, Retro Debt, and Escalation Ladder

## Context

PRD: `docs/prds/learning-ratchet-prd.md`

## Goal

Enhance aet-evolve with operational retrieval, action item closure, and recurrence escalation.

## Tasks

### Task 1: Update learning schema

- [x] Add `trigger` field to learnings.jsonl entries (string or list of keywords)
- [x] Update aet-evolve/SKILL.md to use trigger-based matching instead of "top-3 relevant"
- [x] Ensure backward compatibility with entries lacking the trigger field

### Task 2: Add retro debt check

- [x] Add step 1 to aet-evolve retro procedure: check previous retro action items
- [x] Define outcomes: verified done → mark complete; not done → convert to queue task or explicitly drop
- [x] Document the debt check in SKILL.md

### Task 3: Document escalation ladder

- [x] Create `aet-evolve/references/escalation-ladder.md`
- [x] Define stages: documentation → checklist item → review lens → executable gate
- [x] Define transition criteria (e.g., 2nd recurrence → checklist; 3rd → lens; 4th → gate)
- [x] Reference the ladder in SKILL.md

## Validation

- [x] `make validate` passes
- [x] aet-evolve/SKILL.md under 400 lines
- [x] A learning entry with trigger field is correctly matched when the trigger keyword appears in context
- [x] Retro procedure includes debt check at step 1

## Rollback

Revert aet-evolve/SKILL.md and delete new reference file.

---

_Stage: synced_
_Work class: normal_
_Next step: run `aet-ship`, then `post-ship-verify` to reach `merged`_
