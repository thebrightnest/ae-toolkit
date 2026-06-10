# Plan: Cross-Project Feedback Channel and --toolkit Flag

## Context

PRD: `docs/prds/learning-ratchet-prd.md`

## Goal

Establish the reports/ convention for toolkit-relevant retros and the aet-evolve --toolkit mining procedure.

## Tasks

### Task 1: Document reports/ convention

- [ ] Add standard header format to docs/CONVENTIONS.md or AGENTS.md
- [ ] Define toolkit-relevant marker (e.g., `toolkit-relevant: true` in retro frontmatter)
- [ ] Document required sections: problem, root cause, fix, prevents

### Task 2: Add --toolkit flag to aet-evolve

- [ ] Add `aet-evolve --toolkit` procedure to SKILL.md
- [ ] Define scanning logic: find all `reports/*.md` with toolkit-relevant marker
- [ ] Define output: proposed toolkit changes, pattern frequency, recommended gates
- [ ] Document periodicity (e.g., monthly or after every 5 retros)

### Task 3: Create example output

- [ ] Add example in aet-evolve/examples/ showing --toolkit run output

## Validation

- [ ] `make validate` passes
- [ ] A report with `toolkit-relevant: true` is correctly identified by --toolkit scanning
- [ ] --toolkit output includes actionable toolkit change proposals

## Rollback

Revert aet-evolve/SKILL.md and convention docs.

---

_Stage: plan-approved_
_Work class: normal_
_Next step: aet-pipeline-implement_
