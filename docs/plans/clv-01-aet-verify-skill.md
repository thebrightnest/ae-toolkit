# Plan: Create aet-verify Skill

## Context
PRD: `docs/prds/conditional-live-verification-prd.md`

## Goal
Create the aet-verify skill with three modes: foundation (smoke), feature (observed evidence), and reproduction (bug report).

## Tasks

### Task 1: Scaffold skill directory
- [x] Create `aet-verify/SKILL.md` with YAML frontmatter (name, description, trigger phrases)
- [x] Create `aet-verify/examples/README.md`
- [x] Create `aet-verify/references/README.md`

### Task 2: Write SKILL.md core
- [x] Foundation mode: run smoke checks, capture results
- [x] Feature mode: exercise changed flow, capture evidence (output/HTTP/screenshot)
- [x] Reproduction mode: reproduce bug, capture steps and evidence
- [x] Document when each mode triggers (work-class conditional)
- [x] Keep under 400 lines (186 lines)

### Task 3: Populate examples and references
- [x] Example: feature mode for an API endpoint (curl + response capture)
- [x] Example: foundation mode (make smoke output)
- [x] Reference: evidence capture formats and file naming conventions
- [x] Reference: integration with aet-qa report format

## Validation
- [x] `make validate` passes (aet-verify-specific; repo-wide fails on pre-existing untracked docs/plans/ + docs/prds/)
- [x] `make package` produces `aet-verify.skill`
- [x] SKILL.md under 400 lines
- [x] Reading the skill: a user knows which mode to invoke and what evidence to expect

## Rollback
Delete `aet-verify/` directory.

---

*Stage: synced*
*Work class: normal*
*Next step: run `aet-ship`, then `post-ship-verify` to reach `merged`*
