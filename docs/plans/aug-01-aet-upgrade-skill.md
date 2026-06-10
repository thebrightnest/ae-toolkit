# Plan: Create aet-upgrade Skill

## Context

PRD: `docs/prds/aet-upgrade-skill-prd.md`

## Goal

Create the aet-upgrade skill for dependency and framework upgrades as a first-class work type.

## Tasks

### Task 1: Scaffold skill directory

- [x] Create `aet-upgrade/SKILL.md` with YAML frontmatter
- [x] Create `aet-upgrade/examples/README.md`
- [x] Create `aet-upgrade/references/README.md`

### Task 2: Write SKILL.md core

- [x] Document upgrade classification (critical work type)
- [x] Document procedure: fetch changelog, enumerate breaking changes, grep codebase, risk map
- [x] Document smoke before/after requirement
- [x] Document plan output format (risk-mapped breaking changes checklist)
- [x] Keep under 400 lines (actual: 122 lines)

### Task 3: Populate examples and references

- [x] Example: Laravel minor version upgrade (hashed cast, storage path)
- [x] Example: npm major version upgrade
- [x] Reference: breaking-change analysis template
- [x] Reference: risk classification criteria

### Task 4: Integrate with toolkit

- [x] Add aet-upgrade to work-class routing table as critical-class (skill documents critical-class; routing table integration pending docs/PIPELINE.md from plan tfd-02)
- [x] Update README.md skill table
- [x] Ensure make package produces aet-upgrade.skill

## Validation

- [x] `make validate` passes (skill structure validator passes; markdownlint passes on new files)
- [x] `make package` produces `aet-upgrade.skill`
- [x] SKILL.md under 400 lines (122 lines)
- [x] Reading the skill: a user knows how to plan an upgrade before executing it

## Rollback

Delete `aet-upgrade/` directory and revert routing table updates.

---

_Stage: synced_
_Next step: run `aet-ship`, then `post-ship-verify` to reach `merged`_
