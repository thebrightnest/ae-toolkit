# Plan: Create docs/PIPELINE.md and Shared-Partials Build System

## Context

PRD: `docs/prds/skill-composition-integrity-prd.md`

## Goal

Establish the canonical pipeline definition and build skills from shared partials instead of hand-maintaining 21 copies.

## Tasks

### Task 1: Create docs/PIPELINE.md

- [x] Document canonical stage state machine (all stages and transitions)
- [x] Document trigger phrases for each skill (unique, non-overlapping)
- [x] Document completion protocol graph (which skill points to which next step)
- [x] Document work-class routing table

### Task 2: Create shared partials

- [x] Create `scripts/partials/preamble.md` — canonical Shared Preamble
- [x] Create `scripts/partials/guardrails.md` — canonical guardrail block
- [x] Create `scripts/partials/stage-table.md` — canonical stage/completion table
- [x] Ensure partials are parameterizable (e.g., `{skill_name}`, `{next_step}`)

### Task 3: Update make package

- [x] Add assembly step: substitute partials into skill templates before zipping
- [x] Create `scripts/build-skills.py` (Python, standard library) for assembly
- [x] Preserve skills that need custom variants (exception list)

### Task 4: Test build

- [x] Run make package and verify all .skill files are produced correctly
- [x] Diff a built SKILL.md against the original to ensure correctness

## Validation

- [x] `make validate` passes
- [x] `make package` produces identical .skill files for unmodified skills
- [x] docs/PIPELINE.md is internally consistent
- [x] No two skills share a trigger phrase in the canonical doc

## Rollback

Revert Makefile and scripts/; keep original hand-maintained SKILL.md files.

---

_Stage: synced_
_Work class: critical_
_Next step: run `aet-ship`, then `post-ship-verify` to reach `merged`_
