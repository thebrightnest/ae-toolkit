---
id: tdsh-04-qa-stage-failure-triage
size: S
blocked_by: []
pipeline: standard
---

# Plan: Add stage-failure triage checklist to aet-qa

## Context

Part of [Telemetry-Driven Skill Hardening](../prds/telemetry-driven-skill-hardening-prd.md). `mine-learnings` found 505 stage failures. This plan adds a mandatory triage checklist to `aet-qa` so failed stages are investigated systematically before retry or human escalation.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [ ] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. Update `aet-qa/SKILL.md` to include a stage-failure triage checklist — S
2. Define required evidence fields (command, output, files touched, last successful stage, environment variables, reproducibility) — S
3. Repackage skill and run `make validate` — S

## Files to Modify

- `aet-qa/SKILL.md`

## Validation Steps

- [ ] `make lint` passes
- [ ] `make format-check` passes
- [ ] `make validate` passes
- [ ] SKILL.md remains ≤ 400 lines
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

1. Revert `aet-qa/SKILL.md` changes.
2. Re-run `make validate`.

---

_Stage: qa-complete_
_Next step: run `aet-review`_
