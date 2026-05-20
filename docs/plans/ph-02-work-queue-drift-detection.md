# Plan: Add Branch Drift Detection and Timestamps to aet-work

## Context

The P3-REM retro found that "done" tasks in the work queue were not actually merged to `main`. Branch-safety work (bs-01..03) added reactive merge verification, but there is no proactive way to detect drift. This plan adds:

1. `completed_at` and `merged_at` timestamp fields to the work-queue schema
2. A `drift-check` command that surfaces tasks marked `done` whose commits are not on `origin/main`

## Tasks

1. Update `aet-work/SKILL.md` — add timestamp fields to `init-queue` schema documentation (S)
2. Update `aet-work/SKILL.md` — add `drift-check` command procedure (M)
3. Create `aet-work/references/branch-drift-detection.md` if detail exceeds line budget (S)
4. Update `aet-pipeline-implement/SKILL.md` — set `completed_at` and `merged_at` during `post-ship-verify` (S)
5. Verify `make validate` passes (S)
6. Run `make package` to regenerate `.skill` files (S)

## Dependencies

- None — can start immediately
- Blocks: ph-03-aet-review-removal-safety (optional ordering)

## Validation Steps

- [ ] `aet-work/SKILL.md` documents `completed_at` and `merged_at` fields
- [ ] `aet-work/SKILL.md` defines `drift-check` command with clear output format
- [ ] `aet-pipeline-implement/SKILL.md` sets timestamps during `post-ship-verify`
- [ ] All updated SKILL.md files remain under 400 lines
- [ ] `make validate` passes
- [ ] `make package` succeeds

## Rollback Plan

Restore `aet-work/SKILL.md` and `aet-pipeline-implement/SKILL.md` from git.

---

_Stage: plan-approved_
_Next step: run `aet-pipeline-implement` or `aet-work`_
