---
id: ts-03-aet-work-queue-validation
blocked_by:
  - ts-01-aet-plan-guardrail
size: M
---

# Plan: Add Queue Size Validation to aet-work

## Context

- PRD: `docs/prds/task-size-guardrails-prd.md`
- Parent plan: `docs/plans/ts-01-aet-plan-guardrail.md`
- aet-work `sync` is the entry point where plan files become queue entries. It is the final safety net.

## Tasks

1. Update `aet-work/SKILL.md` — M

   - Add a validation step to the `sync` command: scan each incoming plan.md task list
   - Check each task against the AI-complexity limit (≤ 8 files / 300 diff lines)
   - If any task exceeds the limit, refuse to add the plan to the queue and emit a split suggestion
   - If a plan contains `⚠️ ATOMIC OVERSIZED`, add it but flag it with `oversized: true` in the queue entry

2. Run `make validate` and `make package` — S

## Dependencies

- Blocked by `ts-01-aet-plan-guardrail` — the guardrail definitions must exist before aet-work can reference them.

## Validation Steps

- [ ] `make validate` passes.
- [ ] `make package` regenerates `aet-work.skill`.
- [ ] Manual review: `sync` command includes clear validation logic.

## Rollback Plan

- Revert `aet-work/SKILL.md` from git.
- Re-run `make package`.

---

_Stage: synced_
\_Next step: run `aet-ship`, then `post-ship-verify` to reach `merged`
