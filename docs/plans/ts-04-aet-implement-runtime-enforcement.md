# Plan: Add Runtime Size Enforcement to aet-implement

## Context

- PRD: `docs/prds/task-size-guardrails-prd.md`
- Parent plan: `docs/plans/ts-01-aet-plan-guardrail.md`
- aet-implement is the execution skill. It is the last line of defense against starting an oversized task.

## Tasks

1. Update `aet-implement/SKILL.md` — M

   - Add a pre-flight check at the start of the `implement` command
   - Read the target `plan.md`
   - If any task contains `⚠️ ATOMIC OVERSIZED`, refuse to start
   - Print the oversized task(s) and ask for explicit user confirmation (`--force` flag or interactive approval)
   - If confirmed, proceed with a warning logged to `.agents/learnings.jsonl`

2. Run `make validate` and `make package` — S

## Dependencies

- Blocked by `ts-01-aet-plan-guardrail` — the `ATOMIC OVERSIZED` marker must be defined before aet-implement can check for it.

## Validation Steps

- [ ] `make validate` passes.
- [ ] `make package` regenerates `aet-implement.skill`.
- [ ] Manual review: the pre-flight check is present and the refusal logic is clear.

## Rollback Plan

- Revert `aet-implement/SKILL.md` from git.
- Re-run `make package`.

---

_Stage: synced_
\_Next step: run `aet-ship`, then `post-ship-verify` to reach `merged`
