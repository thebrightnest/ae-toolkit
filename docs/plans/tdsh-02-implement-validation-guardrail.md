---
id: tdsh-02-implement-validation-guardrail
size: S
blocked_by: []
pipeline: standard
---

# Plan: Verify validation-after-every-task guardrail in aet-implement

## Context

Part of [Telemetry-Driven Skill Hardening](../prds/telemetry-driven-skill-hardening-prd.md). `mine-learnings` found 143 repeated loops, many from format-fix or test-retry cycles that could have been caught earlier.

The `aet-implement/SKILL.md` `implement` procedure already states in step 7 that the agent should "run the relevant validation from the plan's self-validation strategy" after each task. This plan verifies that language is explicit enough and tightens it if needed.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [ ] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. Verify `aet-implement/SKILL.md` already requires validation after each task — S
2. Tighten language so the procedure explicitly stops and reports on validation failure before the next task — S
3. Repackage skill and run `make validate` — S

## Files to Modify

- `aet-implement/SKILL.md`

## Validation Steps

- [ ] `make lint` passes
- [ ] `make format-check` passes
- [ ] `make validate` passes
- [ ] SKILL.md remains ≤ 400 lines
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

1. Revert `aet-implement/SKILL.md` changes.
2. Re-run `make validate`.

---

_Stage: plan-approved_
\_Next step: run `aet-work`
