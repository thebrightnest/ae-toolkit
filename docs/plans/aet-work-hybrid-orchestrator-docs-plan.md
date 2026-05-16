# Plan: aet-work Hybrid Orchestrator — Documentation & Validation

## Context

PRD: `docs/prds/aet-work-hybrid-orchestrator-prd.md`
Parent plan: `docs/plans/aet-work-hybrid-orchestrator-core-plan.md`

This plan covers the honest documentation updates, skill instruction changes, and packaging required to ship the hybrid orchestrator.

## Tasks

1. **Update `aet-work/SKILL.md`** — M
   - Add `run-scripted` command with full procedure
   - Update the existing `run` command steps 6 and 14 to acknowledge the context-clearing limitation
   - Update key principles to reference the hybrid pattern
   - Add cross-reference to `references/afk-loop-orchestrator.sh`

2. **Rewrite `references/context-isolation.md`** — S
   - Remove false claim that "the agent follows this instruction"
   - Add runtime capability table (Claude, Kimi, Cursor, etc.)
   - Document cooperative vs. guaranteed isolation
   - Reference the new orchestrator script

3. **Create `references/afk-loop-orchestrator.sh`** — M
   - Standalone reference script demonstrating the ralph-loop pattern
   - Heavily commented, with `agent_invoke()` stub for adaptation
   - Uses `python3` for JSON, `git worktree` for isolation

4. **Run quality gates** — S
   - `make lint`
   - `make format-check`
   - `make validate` (skill structure checks)
   - Fix any issues surfaced

5. **Package skills** — S
   - `make package` to regenerate `.skill` files
   - Verify `aet-work.skill` contains the new references

## Dependencies

Blocked by `aet-work-hybrid-orchestrator-core-plan.md` — the core command must exist before documentation claims it works.

## Validation Steps

- [ ] `make lint` passes with 0 errors
- [ ] `make format-check` passes with 0 warnings
- [ ] `make validate` passes (skill structure, link checks)
- [ ] `make package` succeeds and `aet-work.skill` contains new files
- [ ] `aet-work/SKILL.md` line count ≤ 400 (warn only if exceeded)

## Rollback Plan

1. Revert `aet-work/SKILL.md` to pre-change state
2. Revert `aet-work/references/context-isolation.md` to pre-change state
3. Delete `aet-work/references/afk-loop-orchestrator.sh`
4. Re-run `make package` to regenerate clean `.skill` files

---

_Stage: plan-approved_
_Next step: run `aet-pipeline-implement` or `aet-work`_
