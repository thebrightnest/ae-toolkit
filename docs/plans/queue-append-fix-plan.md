# Plan: Fix work-queue.json Overwrite in aet-plan

## Context

- PRD: `docs/prds/queue-append-prd.md`
- Brief: `docs/product-briefs/queue-append-brief.md`
- Two skill files need editing. No new directories or skills.

## Tasks

1. **Edit `aet-plan/SKILL.md`**

   - Line ~95: Replace "Generate `.agents/work-queue.json`" with "Merge into `.agents/work-queue.json`"
   - Lines ~102–108: Add "Read first → Merge → Validate" steps to the Work queue generation subsection

2. **Edit `aet-pipeline-plan/SKILL.md`**

   - In the `plan` command, Step 2 (`aet-plan`): Add guardrail note about queue preservation

3. **Validate and package**
   - Run `make validate`
   - Run `make package`

## Dependencies

None — single task.

## Validation Steps

- [ ] `aet-plan/SKILL.md` uses merge language, not generate
- [ ] `aet-pipeline-plan/SKILL.md` reinforces preservation
- [ ] Both skills under 400 lines
- [ ] `make validate` passes
- [ ] `make package` produces updated `.skill` files

## Rollback Plan

Revert the two SKILL.md files and re-run `make package`.

---

_Stage: plan-approved_
_Next step: run `aet-pipeline-implement` or `aet-work`_
