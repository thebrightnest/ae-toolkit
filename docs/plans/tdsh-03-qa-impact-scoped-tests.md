---
id: tdsh-03-qa-impact-scoped-tests
size: S
blocked_by: []
pipeline: standard
---

# Plan: Verify impact-scoped test defaults in aet-qa

## Context

Part of [Telemetry-Driven Skill Hardening](../prds/telemetry-driven-skill-hardening-prd.md). `mine-learnings` found 97 full-suite runs.

The `aet-qa/SKILL.md` `qa` procedure already defaults to impact-scoped tests and defines a "Full suite gate." This plan verifies the language matches the PRD acceptance criteria and tightens the fallback conditions if needed.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [ ] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. Verify `aet-qa/SKILL.md` defaults to impact-scoped tests and defines full-suite fallback conditions — S
2. Ensure the fallback conditions exactly match the PRD (test harness, config, shared fixtures, dependency lockfiles, files imported by many tests) — S
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
