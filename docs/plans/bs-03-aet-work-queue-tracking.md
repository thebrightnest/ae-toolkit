# Plan: aet-work Queue-Level Branch Tracking

## Context

PRD: `docs/prds/branch-safety-prd.md`
Parent issue: GitHub #3
Blocked by: `bs-02-pipeline-implement-merged-stage`

`aet-work` does not track whether a task's branch was properly merged to `origin/main` before starting the next task. In sequential queues, downstream tasks often depend on upstream tasks being on `main`. This plan adds `merge_verified` tracking and a pre-task check.

## Tasks

1. ✅ Update `init-queue` schema in `aet-work/SKILL.md` to include `merge_verified` and `merge_commit` fields — S
2. ✅ Add pre-task merge verification check to `run` procedure — S
3. ✅ Add pre-task merge verification check to `run-scripted` procedure — S
4. ✅ Update `cleanup` to use merge verification instead of naive merge check — S
5. ✅ Run `make validate` and `make package` — S

## Dependencies

- `bs-02-pipeline-implement-merged-stage` — this plan consumes the `merged` stage and `merge_verified` semantics defined in the pipeline implement skill

## Validation Steps

- [x] `aet-work/SKILL.md` line count ≤ 400 (warn only if exceeded)
- [x] `make validate` passes (lint, format-check, skill structure)
- [x] `make package` regenerates `aet-work.skill` without errors
- [x] `init-queue` schema documents `merge_verified` and `merge_commit`
- [x] `run` checks previous task's `merge_verified` before starting next task
- [x] Missing `merge_verified` is treated as unverified (not broken)

## Rollback Plan

Revert `aet-work/SKILL.md` to pre-change state and re-run `make package`.

---
*Stage: synced*
*Next step: run `aet-ship`*
