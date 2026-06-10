# Plan: Create docs/PIPELINE.md and Shared-Partials Build System

## Context
PRD: `docs/prds/skill-composition-integrity-prd.md`

## Goal
Establish the canonical pipeline definition and build skills from shared partials instead of hand-maintaining 21 copies.

## Tasks

### Task 1: Create docs/PIPELINE.md
- [ ] Document canonical stage state machine (all stages and transitions)
- [ ] Document trigger phrases for each skill (unique, non-overlapping)
- [ ] Document completion protocol graph (which skill points to which next step)
- [ ] Document work-class routing table

### Task 2: Create shared partials
- [ ] Create `scripts/partials/preamble.md` — canonical Shared Preamble
- [ ] Create `scripts/partials/guardrails.md` — canonical guardrail block
- [ ] Create `scripts/partials/stage-table.md` — canonical stage/completion table
- [ ] Ensure partials are parameterizable (e.g., `{skill_name}`, `{next_step}`)

### Task 3: Update make package
- [ ] Add assembly step: substitute partials into skill templates before zipping
- [ ] Create `scripts/build-skills.py` (Python, standard library) for assembly
- [ ] Preserve skills that need custom variants (exception list)

### Task 4: Test build
- [ ] Run make package and verify all .skill files are produced correctly
- [ ] Diff a built SKILL.md against the original to ensure correctness

## Validation
- [ ] `make validate` passes
- [ ] `make package` produces identical .skill files for unmodified skills
- [ ] docs/PIPELINE.md is internally consistent
- [ ] No two skills share a trigger phrase in the canonical doc

## Rollback
Revert Makefile and scripts/; keep original hand-maintained SKILL.md files.

---

*Stage: plan-approved*
*Work class: critical*
*Next step: aet-pipeline-implement*
