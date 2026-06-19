---
id: pipeline-plan-optional-ui-plan
blocked_by: []
size: S
---

# Plan: Optional UI Validation in aet-pipeline-plan

## Context

- PRD: `docs/prds/pipeline-plan-optional-ui-prd.md`
- Target file: `aet-pipeline-plan/SKILL.md`
- The change makes `aet-validate-ui` (Step 3) conditional rather than mandatory.

## Tasks

1. Update skill description to mention optional UI validation — S
2. Update Step 3 section with trigger detection and prompt logic — S
3. Update sequence diagram and completion protocol — S
4. Update key principles (remove "UI validation is mandatory but skippable") — S
5. Run `make validate` and `make package` — S

## Dependencies

- Task 1–4 can be done in a single editing pass.
- Task 5 depends on Tasks 1–4.

## Validation Steps

- [ ] `make validate` passes (lint, format-check, skill-structure validator).
- [ ] `make package` regenerates `aet-pipeline-plan.skill`.
- [ ] Manual review: the updated `aet-pipeline-plan/SKILL.md` reads correctly.

## Rollback Plan

- Revert the single commit or restore `aet-pipeline-plan/SKILL.md` from git.
- Re-run `make package` to regenerate the `.skill` artifact.

---

_Stage: synced_
_Next step: run `aet-ship`, then `post-ship-verify` to reach `merged`_
