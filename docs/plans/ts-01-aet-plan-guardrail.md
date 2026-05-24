# Plan: Add Task Size Guardrail to aet-plan

## Context

- PRD: `docs/prds/task-size-guardrails-prd.md`
- Foundation story — all other guardrail stories depend on this one.
- The aet-plan skill produces stories and plan.md files. It is the natural place to insert the dual-limit guardrail.

## Tasks

1. Add dual-limit definitions to `aet-plan/SKILL.md` — S

   - Human-time limit (≤ 2 days for stories, ≤ 4 agent-hours for tasks)
   - AI-complexity limit (≤ 10 files / 500 diff lines for stories; ≤ 8 files / 300 diff lines for tasks)
   - Rule: a task fails if **either** limit is exceeded

2. Update `create-stories` command with auto-split logic — M

   - Evaluate each story against both limits
   - Auto-split along vertical-slice boundaries (behavior, entity, layer)
   - Max split depth = 3
   - Mark `⚠️ ATOMIC OVERSIZED` if unsplittable
   - Document split parent/child relationships

3. Update `plan` command with task-level guardrail — M

   - Evaluate each task in `plan.md` against both limits
   - Auto-split into subtasks with explicit dependencies
   - Add `Task Size` field (S/M/L) with documented thresholds
   - Mark `⚠️ ATOMIC OVERSIZED` if unsplittable

4. Update `.agents/templates/plan-template.md` — S

   - Add `Task Size` field (S/M/L) with threshold definitions
   - Add note that L tasks must be split
   - Add split annotation format (`Split from: parent-task-id`)

5. Run `make validate` and `make package` — S

## Dependencies

- Task 1–4 can be done in a single editing pass.
- Task 5 depends on Tasks 1–4.
- No blockers — this is the root story.

## Validation Steps

- [ ] `make validate` passes.
- [ ] `make package` regenerates `aet-plan.skill`.
- [ ] Manual review: `aet-plan/SKILL.md` includes clear guardrail rules and split logic.
- [ ] Manual review: `.agents/templates/plan-template.md` has size field and split annotations.

## Rollback Plan

- Revert `aet-plan/SKILL.md` and `.agents/templates/plan-template.md` from git.
- Re-run `make package`.

---

_Stage: synced_
_Next step: run `aet-ship`, then `post-ship-verify` to reach `merged`_
