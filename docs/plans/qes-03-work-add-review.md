---
id: qes-03-work-add-review
size: M
blocked_by:
  - qes-02-plan-status-frontmatter
pipeline: standard
---

# Plan: Implement aet-work add and aet-work review Commands

## Context

Part of [PRD: Ephemeral Sprint Board for aet-work](../prds/aet-work-queue-ephemeral-sprint-board-prd.md). The queue is no longer auto-populated from all plans. Users need explicit commands to curate the sprint board and inspect the backlog.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [ ] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. Create `aet-work/bin/add` that accepts a plan file path or task ID and inserts a task into `.agents/work-queue.json` as `planned` — M
2. Create `aet-work/bin/review` that scans `docs/plans/*.md`, reads `status`, and prints approved / queued / in-progress / awaiting-merge / closed — M
3. Update `aet-work/SKILL.md` command reference — S
4. Merge branch to main and verify integration — S

## Files to Modify

- `aet-work/bin/add` (create)
- `aet-work/bin/review` (create)
- `aet-work/SKILL.md`
- `aet-work/bin/status` (minor, ensure it handles empty queue gracefully)

## Validation Steps

- [ ] `aet-work add docs/plans/qes-02-plan-status-frontmatter.md` adds the task to the queue
- [ ] `aet-work review` correctly categorizes plans by status
- [ ] `make validate` passes
- [ ] `aet-work add` rejects plans with `status: merged` or `status: abandoned`

## Rollback Plan

1. Delete `aet-work/bin/add` and `aet-work/bin/review`.
2. Revert `aet-work/SKILL.md`.
3. Re-run `make validate`.

---

_Stage: plan-approved_
_Next step: run `aet-work`_
