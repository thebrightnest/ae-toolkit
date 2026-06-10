# Plan: Create aet-verify Skill

## Context
PRD: `docs/prds/conditional-live-verification-prd.md`

## Goal
Create the aet-verify skill with three modes: foundation (smoke), feature (observed evidence), and reproduction (bug report).

## Tasks

### Task 1: Scaffold skill directory
- [ ] Create `aet-verify/SKILL.md` with YAML frontmatter (name, description, trigger phrases)
- [ ] Create `aet-verify/examples/README.md`
- [ ] Create `aet-verify/references/README.md`

### Task 2: Write SKILL.md core
- [ ] Foundation mode: run smoke checks, capture results
- [ ] Feature mode: exercise changed flow, capture evidence (output/HTTP/screenshot)
- [ ] Reproduction mode: reproduce bug, capture steps and evidence
- [ ] Document when each mode triggers (work-class conditional)
- [ ] Keep under 400 lines

### Task 3: Populate examples and references
- [ ] Example: feature mode for an API endpoint (curl + response capture)
- [ ] Example: foundation mode (make smoke output)
- [ ] Reference: evidence capture formats and file naming conventions
- [ ] Reference: integration with aet-qa report format

## Validation
- [ ] `make validate` passes
- [ ] `make package` produces `aet-verify.skill`
- [ ] SKILL.md under 400 lines
- [ ] Reading the skill: a user knows which mode to invoke and what evidence to expect

## Rollback
Delete `aet-verify/` directory.

---

*Stage: plan-approved*
*Work class: normal*
*Next step: aet-pipeline-implement*
