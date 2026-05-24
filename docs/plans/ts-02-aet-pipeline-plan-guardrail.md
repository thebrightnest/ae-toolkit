# Plan: Add Task Size Guardrail Reference to aet-pipeline-plan

## Context

- PRD: `docs/prds/task-size-guardrails-prd.md`
- Parent plan: `docs/plans/ts-01-aet-plan-guardrail.md`
- aet-pipeline-plan chains aet-plan internally; it must reference the same guardrail without duplicating logic.

## Tasks

1. Update `aet-pipeline-plan/SKILL.md` — S

   - Add a note in Step 2 (aet-plan) that `create-stories` and `plan` now enforce task size guardrails
   - Add a reference to the dual-limit model in the Key Principles section
   - No logic duplication — aet-pipeline-plan delegates to aet-plan

2. Run `make validate` and `make package` — S

## Dependencies

- Blocked by `ts-01-aet-plan-guardrail` — the guardrail must exist in aet-plan before it can be referenced.

## Validation Steps

- [ ] `make validate` passes.
- [ ] `make package` regenerates `aet-pipeline-plan.skill`.
- [ ] Manual review: the reference is present and does not duplicate logic.

## Rollback Plan

- Revert `aet-pipeline-plan/SKILL.md` from git.
- Re-run `make package`.

---

_Stage: synced_
\_Next step: run `aet-ship`, then `post-ship-verify` to reach `merged`
