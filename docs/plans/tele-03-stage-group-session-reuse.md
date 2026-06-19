---
id: tele-03-stage-group-session-reuse
size: M
blocked_by: []
---

# Plan: Stage-Group Session Reuse for Standard Isolation

## Context

- PRD: `docs/prds/aet-telemetry-learning-prd.md`

For `standard` isolation, the orchestrator currently spawns one agent session per pipeline stage. The project review showed this causes repeated file reads, repeated test suite runs, and repeated rediscovery of environment issues. This plan reuses a single agent session for all stages within a `session_group`, while keeping `minimal` and `full` isolation unchanged.

This is an enhancement to the toolkit's own tooling, not a reproducible defect report.

## Task List

1. Add `run_stage_group` to `aet-work/bin/orchestrator` — M
   - Build a compound prompt that lists every stage in the group, the skills to run, and the expected next stage.
   - Instruct the agent to commit and update the plan footer between stages.
2. Update `process_task` to invoke `run_stage_group` for `standard` isolation — M
3. Add verification and fallback — S
   - After the group session exits, verify the task reached the expected final stage.
   - If verification fails, fall back to the original per-stage execution for that group.
4. Update `aet-work/references/context-isolation.md` to document stage-group reuse — S
5. Run `make validate` and a manual smoke test — S

## Files to Modify

- `aet-work/bin/orchestrator`
- `aet-work/references/context-isolation.md`

## Validation Steps

- [ ] `make validate` passes.
- [ ] A test plan run with `standard` isolation spawns one session per stage group, not one per stage.
- [ ] Verification correctly falls back to per-stage execution when the group session does not advance.
- [ ] Each new source file introduced by this plan has a named test or validation step covering it.
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the orchestrator changes; the per-stage execution path remains as the fallback.

---

_Stage: plan-approved_
_Next step: run `aet-work`_
