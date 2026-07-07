---
id: qes-04-status-next-run-hygiene
size: M
blocked_by:
  - qes-01-gitignore-tracked-files
pipeline: standard
---

# Plan: Update aet-work status, next, and Orchestrator Hygiene

## Context

Part of [PRD: Ephemeral Sprint Board for aet-work](../prds/aet-work-queue-ephemeral-sprint-board-prd.md). With the queue gitignored, the orchestrator must stop treating queue-file mutations as dirty-working-tree failures. `status` and `next` should also stop using plan-drift as a hard gate.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [ ] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. Update `aet-work/bin/status` to report only active queue state; keep plan-drift reporting informational — S
2. Update `aet-work/bin/next` to remove plan-drift hard gate — S
3. Update `aet-work/bin/orchestrator` main-hygiene check to ignore `.agents/work-queue.json` and `.agents/work-history.jsonl` — M
4. Update `aet-work/SKILL.md` to describe the new behavior — S
5. Merge branch to main and verify integration — S

## Files to Modify

- `aet-work/bin/status`
- `aet-work/bin/next`
- `aet-work/bin/orchestrator`
- `aet-work/SKILL.md`

## Validation Steps

- [ ] `aet-work run` no longer halts when `.agents/work-queue.json` has just been written
- [ ] `aet-work next` picks a ready task even when unqueued plans exist
- [ ] `aet-work status` still reports active tasks correctly
- [ ] `make validate` passes

## Rollback Plan

1. Revert changes to `status`, `next`, `orchestrator`, and `aet-work/SKILL.md`.
2. Re-run `make validate`.

---

_Stage: implemented_
_Next step: run `aet-qa`_
