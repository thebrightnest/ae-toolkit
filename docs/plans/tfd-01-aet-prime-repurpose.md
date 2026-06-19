---
id: tfd-01-aet-prime-repurpose
blocked_by: []
size: M
---

# Plan: Repurpose aet-prime as Triage Front Door

## Context

PRD: `docs/prds/triage-front-door-work-class-routing-prd.md`

## Goal

Transform `aet-prime` from a context-loading preamble into an active triage front door that classifies incoming requests and routes them to the correct work class and skill.

## Tasks

### Task 1: Rewrite aet-prime/SKILL.md core

- [ ] Add intake classification questions as the first procedure step
- [ ] Define classification rules: auth/data/infra/upgrade → critical; reproducible defect → bug; else → normal/trivial based on estimated scope
- [ ] Add routing table reference (trivial → direct edit; normal → quick plan; critical → full PRD)
- [ ] Keep context-loading (git status, recent commits, AGENTS.md) as step 0
- [ ] Ensure SKILL.md stays under 400 lines

### Task 2: Update examples and references

- [ ] Add triage example: "fix typo" → trivial path
- [ ] Add triage example: "add OAuth" → critical path
- [ ] Move deep classification logic to `references/routing-rules.md`

## Validation

- [ ] `make validate` passes
- [ ] `aet-prime/SKILL.md` under 400 lines
- [ ] Reading the skill: a new user can follow the intake questions and arrive at the correct work class

## Rollback

Revert `aet-prime/SKILL.md` to previous version from git.

---

_Stage: plan-approved_
_Work class: normal_
_Next step: aet-pipeline-implement_
