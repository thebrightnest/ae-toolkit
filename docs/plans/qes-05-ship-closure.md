---
id: qes-05-ship-closure
size: M
blocked_by:
  - qes-01-gitignore-tracked-files
  - qes-02-plan-status-frontmatter
pipeline: standard
---

# Plan: Make aet-ship Own Task Closure After Merge Verification

## Context

Part of [PRD: Ephemeral Sprint Board for aet-work](../prds/aet-work-queue-ephemeral-sprint-board-prd.md). Currently `aet-ship` records the merge in the queue via `aet-state record-merge`. In the new model, terminal truth lives in the plan file, and the execution log is optional. `aet-ship` must update the plan, append to the log, and remove the task from the queue.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [ ] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. Extend `aet-ship/bin/ship` merge-verification step to update the plan file frontmatter `status` to `merged` and footer `*Stage:*` to `merged` — M
2. Append a closure event to `.agents/work-history.jsonl` with merge commit and timestamp — S
3. Remove the task from `.agents/work-queue.json` after successful verification — S
4. Remove `.agents/work-queue.json` from the scope-audit out-of-scope list — S
5. Update `aet-ship/SKILL.md` closure procedure — S
6. Merge branch to main and verify integration — S

## Files to Modify

- `aet-ship/bin/ship`
- `aet-ship/SKILL.md`
- `aet-work/bin/aet-state` (if needed for queue removal helper)

## Validation Steps

- [ ] After `aet-ship` verifies a merge, the plan file shows `status: merged`
- [ ] The task no longer appears in `aet-work status`
- [ ] `.agents/work-history.jsonl` contains a closure event
- [ ] `make validate` passes

## Rollback Plan

1. Revert `aet-ship/bin/ship` and `aet-ship/SKILL.md`.
2. Re-run `make validate`.

---

_Stage: plan-approved_
_Next step: run `aet-work`_
