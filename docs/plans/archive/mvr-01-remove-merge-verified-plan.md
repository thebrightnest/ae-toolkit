---
id: mvr-01-remove-merge-verified-plan
blocked_by: []
size: M
---

# Plan: Remove `merge_verified` — Status as Single Source of Truth

## Context

PRD: `docs/prds/merge-verified-redundancy-prd.md`

The work queue and skill instructions currently use both `merge_verified: true/false` and `status: merged/done/abandoned` to communicate the same thing. This plan removes `merge_verified` entirely and makes `status` the single source of truth.

## Tasks

### 1. Update skill instructions — M

Update all skill markdown that references `merge_verified` to use `status` and `merge_commit` instead.

**Files:**

- `aet-work/SKILL.md`
  - `sync`: remove `merge_verified` from preserved fields; remove from new-task defaults
  - `cleanup`: check `status == "merged"` + `merge_commit` set + git ancestry, instead of `merge_verified: true`
  - `mark-terminal`: validate `status == "merged"` requires `merge_commit` set and git ancestry passing, instead of checking `merge_verified`
  - `post-ship-verify`: update queue update instruction to set `status: "merged"` and `merged_at`, not `merge_verified: true`
  - Orchestrator template reference: update pre-task check to look at `status` of `blocked_by` entries
- `aet-ship/SKILL.md`
  - Remove `"merge_verified": true` from merge result JSON example
- `aet-pipeline-implement/SKILL.md`
  - Remove `merge_verified: true` from post-ship queue update instruction
  - Update printed summary to say `Status: merged` instead of `Work queue: merge_verified`
- `aet-ship/examples/squash-merge-example.md`
  - Remove `"merge_verified": true` from example queue entry
- `aet-work/references/orchestrator-template.sh`
  - Rename `check_merge_verified()` to `check_dependency_verified()` (or similar)
  - Check `dep.get('status') == 'merged'` instead of `dep.get('merge_verified')`
- `aet-work/references/afk-loop-orchestrator.sh`
  - Same change as orchestrator-template.sh

**Size justification:** 6 files, ~80–100 diff lines. Within M limits.

### 2. Clean up `.agents/work-queue.json` — S

Remove the `"merge_verified"` field from every task entry in `.agents/work-queue.json`.

**Files:**

- `.agents/work-queue.json` (60 occurrences)

**Size justification:** 1 file, ~60 lines removed. Within S limits.

### 3. Validate and package — S

- Run `make validate` to ensure no markdown lint/format issues and skill structure is valid
- Run `make package` to regenerate `.skill` files with updated instructions

**Files:**

- Potentially regenerated `*.skill` files (build artifacts, not manually edited)

## Dependencies

- Task 1 and Task 2 are independent; both must complete before Task 3.
- Task 3 depends on Task 1 and Task 2.

## Validation Steps

- [ ] `make validate` passes (lint, format-check, skill-structure validator)
- [ ] `make package` succeeds and `.skill` files are updated
- [ ] `grep -r "merge_verified" aet-work/ aet-ship/ aet-pipeline-implement/ .agents/work-queue.json` returns zero matches
- [ ] PRD and plan footers updated to correct stage markers

## Rollback Plan

If issues arise:

1. Revert the skill markdown files via git checkout
2. Revert `.agents/work-queue.json` via git checkout
3. Regenerate `.skill` files with `make package`

---

_Stage: merged_
_Next step: none — pipeline complete_
