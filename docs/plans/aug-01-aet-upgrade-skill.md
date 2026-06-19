---
id: aug-01-aet-upgrade-skill
blocked_by: []
size: M
---

# Plan: Create aet-upgrade Skill

## Context

PRD: `docs/prds/aet-upgrade-skill-prd.md`

## Goal

Create the aet-upgrade skill for dependency and framework upgrades as a first-class work type.

## Tasks

### Task 1: Scaffold skill directory

- [ ] Create `aet-upgrade/SKILL.md` with YAML frontmatter
- [ ] Create `aet-upgrade/examples/README.md`
- [ ] Create `aet-upgrade/references/README.md`

### Task 2: Write SKILL.md core

- [ ] Document upgrade classification (critical work type)
- [ ] Document procedure: fetch changelog, enumerate breaking changes, grep codebase, risk map
- [ ] Document smoke before/after requirement
- [ ] Document plan output format (risk-mapped breaking changes checklist)
- [ ] Keep under 400 lines

### Task 3: Populate examples and references

- [ ] Example: Laravel minor version upgrade (hashed cast, storage path)
- [ ] Example: npm major version upgrade
- [ ] Reference: breaking-change analysis template
- [ ] Reference: risk classification criteria

### Task 4: Integrate with toolkit

- [ ] Add aet-upgrade to work-class routing table as critical-class
- [ ] Update README.md skill table
- [ ] Ensure make package produces aet-upgrade.skill

## Validation

- [ ] `make validate` passes
- [ ] `make package` produces `aet-upgrade.skill`
- [ ] SKILL.md under 400 lines
- [ ] Reading the skill: a user knows how to plan an upgrade before executing it

## Rollback

Delete `aet-upgrade/` directory and revert routing table updates.

---

_Stage: plan-approved_
_Work class: normal_
_Next step: aet-pipeline-implement_
