# Plan: Remove aet-discover from aet-pipeline-plan

## Context

- PRD: `docs/prds/pipeline-plan-remove-discover-prd.md`
- Target file: `aet-pipeline-plan/SKILL.md`
- This change removes the mandatory `aet-discover` step from the planning pipeline, making it a pure `aet-plan` → `aet-validate-ui` (optional) → `aet-validate-scope` workflow.

## Tasks

1. Update `aet-pipeline-plan/SKILL.md` description and triggers to reflect "validated idea" entry point — S
2. Remove Step 1 (`aet-discover`) and its hard gate from the sequence — S
3. Renumber remaining steps (Step 2 becomes Step 1, etc.) and update sequence diagram — S
4. Update resume table to remove `brief-validated` row — S
5. Update shared preamble to remove `EXISTING_BRIEFS`, keep briefs as optional context hint — S
6. Update completion protocol and output list to stop referencing product briefs — S
7. Run `make validate` and `make package` — S

## Dependencies

- Tasks 1–6 can be done in a single editing pass.
- Task 7 depends on Tasks 1–6.

## Validation Steps

- [ ] `make validate` passes (lint, format-check, skill-structure validator).
- [ ] `make package` regenerates `aet-pipeline-plan.skill`.
- [ ] Manual review: the updated `aet-pipeline-plan/SKILL.md` reads correctly and discover is fully removed from the pipeline sequence.
- [ ] `aet-discover/SKILL.md` is confirmed untouched.

## Rollback Plan

- Revert the single commit or restore `aet-pipeline-plan/SKILL.md` from git.
- Re-run `make package` to regenerate the `.skill` artifact.

---

_Stage: synced_
_Next step: run `aet-ship`, then `post-ship-verify` to reach `merged`_
