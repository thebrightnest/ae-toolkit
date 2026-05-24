# Plan: Package and Validate All Updated Skills

## Context

- PRD: `docs/prds/task-size-guardrails-prd.md`
- Final integration step — ensure all skill changes are packaged, validated, and ready.

## Tasks

1. Run `make validate` — S

   - Lint, format-check, and skill-structure validator across the entire repo
   - Verify all updated SKILL.md files are under 400 lines
   - Verify all skills have valid YAML frontmatter

2. Run `make package` — S

   - Regenerate `.skill` files for all updated skills:
     - `aet-plan.skill`
     - `aet-pipeline-plan.skill`
     - `aet-work.skill`
     - `aet-implement.skill`

3. Verify `.skill` artifacts — S
   - Confirm each `.skill` file exists and has a recent timestamp
   - Spot-check one `.skill` zip contents

## Dependencies

- Blocked by `ts-01-aet-plan-guardrail`
- Blocked by `ts-02-aet-pipeline-plan-guardrail`
- Blocked by `ts-03-aet-work-queue-validation`
- Blocked by `ts-04-aet-implement-runtime-enforcement`
- Blocked by `ts-05-conventions-docs`

## Validation Steps

- [ ] `make validate` passes with zero errors.
- [ ] All 4 updated `.skill` files are regenerated.
- [ ] Git status shows only expected changes.

## Rollback Plan

- Revert any offending commits.
- Re-run `make package`.

---

_Stage: synced_
\_Next step: run `aet-ship`, then `post-ship-verify` to reach `merged`
