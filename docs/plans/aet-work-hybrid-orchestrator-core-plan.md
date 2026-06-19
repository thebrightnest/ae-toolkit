---
id: aet-work-hybrid-orchestrator-core-plan
blocked_by: []
size: S
---

# Plan: aet-work Hybrid Orchestrator — Core Implementation

## Context

PRD: `docs/prds/aet-work-hybrid-orchestrator-prd.md`

This plan covers the runtime detection, script generation, background execution, and queue-processing logic for the new `aet-work run-scripted` command.

## Tasks

1. **Runtime detection heuristics** — S

   - Inspect env vars (`KIMI_CLI_VERSION`, `CLAUDE_CODE`, `CODEX_*`, `AGENT_CLI`)
   - Return detected CLI string or emit warning with fallback instructions
   - Document detection order in skill reference

2. **Script template and generator** — M

   - Create a bash template that embeds the detected CLI
   - Template reads `.agents/work-queue.json`, manages worktrees, invokes CLI per task
   - Use inline `python3` for JSON manipulation (no `jq` dependency)
   - Output path: `scripts/.aet-work-orchestrator.sh`

3. **Background spawn and wait mechanics** — S

   - Skill procedure: `Shell(run_in_background=true)` to spawn generated script
   - Skill procedure: `TaskOutput(block=true)` to wait for completion
   - Handle the case where the script fails or is interrupted

4. **Queue processing loop in generated script** — M

   - Find next `unblocked` task
   - Mark `in-progress`, create worktree if needed
   - Invoke detected CLI with prompt to run `aet-pipeline-implement` on the task's plan
   - On success: mark `done`, promote dependents
   - On failure: mark `failed`, record stage, stop loop

5. **Resume support** — S

   - Skip tasks already `done` or `in-progress` with existing worktree
   - Idempotent worktree creation (`git worktree add` only if missing)

6. **End-to-end manual test** — M
   - Create a test queue with 2 dummy tasks
   - Run `run-scripted`, verify scripts generate, spawn, and queue updates

## Dependencies

None — this is the first slice.

## Validation Steps

- [ ] `make validate` passes (skill structure only; docs updated in Slice 2)
- [ ] Manual test: generated script contains correct detected CLI
- [ ] Manual test: queue status updates from `unblocked` → `in-progress` → `done`
- [ ] Manual test: worktrees created under `.worktrees/<task-id>/`
- [ ] Manual test: re-running skips already-done tasks

## Rollback Plan

1. Delete `scripts/.aet-work-orchestrator.sh`
2. Remove any `run-scripted` references added to `aet-work/SKILL.md` (Slice 2 handles full doc revert)
3. Delete test worktrees: `git worktree remove .worktrees/<task-id>`

---

_Stage: plan-approved_
_Next step: run `aet-pipeline-implement` or `aet-work`_
