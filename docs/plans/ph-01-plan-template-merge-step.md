# Plan: Add Merge-to-Main Step to Plan Template

## Context

The P3-REM retro identified that plan files ended with implementation and QA steps but had no explicit merge-to-main checklist item. The work queue marked tasks as "merge-verified" based on branch existence, not actual integration. This plan updates the canonical plan template so every future plan includes merge verification as a mandatory final task.

## Tasks

1. Update `.agents/templates/plan-template.md` — add merge verification as final task (S)
2. Verify `make validate` passes with updated template (S)
3. Run `make package` to regenerate `.skill` files (S)

## Dependencies

- None — can start immediately
- Blocks: ph-02-work-queue-drift-detection (semantic dependency: template and drift detection are complementary)

## Validation Steps

- [ ] `.agents/templates/plan-template.md` contains a merge verification task
- [ ] `make validate` passes
- [ ] `make package` succeeds

## Rollback Plan

Restore `.agents/templates/plan-template.md` from git.

---

_Stage: plan-approved_
_Next step: run `aet-pipeline-implement` or `aet-work`_
