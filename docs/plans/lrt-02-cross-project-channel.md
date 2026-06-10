# Plan: Cross-Project Feedback Channel and --toolkit Flag

## Context

PRD: `docs/prds/learning-ratchet-prd.md`

## Goal

Establish the reports/ convention for toolkit-relevant retros and the aet-evolve --toolkit mining procedure.

## Tasks

### Task 1: Document reports/ convention

- [x] Add standard header format to docs/CONVENTIONS.md or AGENTS.md
- [x] Define toolkit-relevant marker (e.g., `toolkit-relevant: true` in retro frontmatter)
- [x] Document required sections: problem, root cause, fix, prevents

### Task 2: Add --toolkit flag to aet-evolve

- [x] Add `aet-evolve --toolkit` procedure to SKILL.md
- [x] Define scanning logic: find all `reports/*.md` with toolkit-relevant marker
- [x] Define output: proposed toolkit changes, pattern frequency, recommended gates
- [x] Document periodicity (e.g., monthly or after every 5 retros)

### Task 3: Create example output

- [x] Add example in aet-evolve/examples/ showing --toolkit run output

## Validation

- [x] `make validate` passes
- [x] A report with `toolkit-relevant: true` is correctly identified by --toolkit scanning
- [x] --toolkit output includes actionable toolkit change proposals

## Rollback

Revert aet-evolve/SKILL.md and convention docs.

---

_Stage: synced_
_Next step: run `aet-ship`, then `post-ship-verify` to reach `merged`_
