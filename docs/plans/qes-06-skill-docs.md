---
id: qes-06-skill-docs
size: M
blocked_by:
  - qes-03-work-add-review
  - qes-04-status-next-run-hygiene
  - qes-05-ship-closure
pipeline: standard
---

# Plan: Update Skill Documentation for the Ephemeral Sprint Board Model

## Context

Part of [PRD: Ephemeral Sprint Board for aet-work](../prds/aet-work-queue-ephemeral-sprint-board-prd.md). After the implementation commands change, the skill instructions must describe the new mental model: plans as source of truth, queue as gitignored sprint board, explicit add/review, and aet-ship closure.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [ ] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. Rewrite `aet-work/SKILL.md` commands section to describe `add`, `review`, ephemeral queue, and removed drift gate — M
2. Update `aet-ship/SKILL.md` closure section to describe plan-file update and queue removal — S
3. Update `aet-plan/SKILL.md` so `create-stories` no longer instructs auto-running `aet-work sync`; document explicit add instead — S
4. Update `aet-setup/SKILL.md` if it references tracked queue files or drift checks — S
5. Merge branch to main and verify integration — S

## Files to Modify

- `aet-work/SKILL.md`
- `aet-ship/SKILL.md`
- `aet-plan/SKILL.md`
- `aet-setup/SKILL.md`

## Validation Steps

- [ ] `make lint` passes
- [ ] `make format-check` passes
- [ ] Skill-structure validator passes
- [ ] Each modified skill file is under 400 lines or has deep detail moved to `references/`
- [ ] `make package` produces byte-identical `.skill` archives across consecutive runs

## Rollback Plan

1. Revert all four `SKILL.md` files.
2. Re-run `make validate`.

---

_Stage: plan-approved_
_Next step: run `aet-work`_
