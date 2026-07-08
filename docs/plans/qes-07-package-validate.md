---
id: qes-07-package-validate
size: S
blocked_by:
  - qes-06-skill-docs
pipeline: standard
---

# Plan: Repackage Skills and Run Final Validation

## Context

Part of [PRD: Ephemeral Sprint Board for aet-work](../prds/aet-work-queue-ephemeral-sprint-board-prd.md). After all skill changes are merged, regenerate the `.skill` archives and confirm the toolkit passes its full validation suite.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [ ] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. [x] Run `make package` to regenerate `.skill` archives — S
2. [x] Run `make validate` — S
3. [x] Verify no tracked `.agents/work-queue.json` or `.agents/work-history.jsonl` remain — S
4. [ ] Merge branch to main and verify integration — S

## Files to Modify

- Generated `*.skill` files
- Possibly `.gitignore` if final check reveals gaps

## Validation Steps

- [x] `make validate` passes
- [x] `git status --short` shows no unexpected tracked files
- [x] `git ls-files | grep -E 'work-queue|work-history'` returns nothing

## Rollback Plan

1. Delete regenerated `.skill` files and restore from the previous commit.
2. Re-run `make validate`.

---

_Stage: secure_
_Next step: run `aet-sync-docs`, then `aet-ship`_
