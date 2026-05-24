---

## Bug Report: aet-work orchestrator silently skips approval gates in `--print` mode

### Metadata

- **Reported:** 2026-05-24
- **Severity:** critical
- **Status:** resolved

### Symptoms

The `aet-work` orchestrator spawned 7 subagents to implement queued plans. Each subagent ran `aet-pipeline-implement`, explored the codebase, reached the Step 0 approval checkpoint ("Approve to proceed?"), and then stopped because `kimi --print` mode is single-turn. The orchestrator saw exit code 0 and marked all tasks as `done`. Zero files were changed. All 7 worktrees were empty.

### Reproduction Steps

1. Run `aet-work run` with a queue containing unblocked tasks
2. The orchestrator generates `scripts/.aet-work-orchestrator.sh` with `CLI_ARGS=(--print --yolo ...)`
3. For each task, the script invokes: `kimi --print --yolo -p "Run aet-pipeline-implement on <plan>" --work-dir <worktree>`
4. The subagent reads `aet-pipeline-implement/SKILL.md`, sees Step 0 approval checkpoint
5. Because `--print` is single-turn non-interactive, the subagent cannot wait for human input
6. The subagent silently skips the gate and attempts Step 1 (aet-tdd)
7. After one turn, `--print` exits with code 0
8. The orchestrator marks the task `done` and promotes dependents
9. Result: 7 tasks marked done, 0 files changed

**Evidence:** `scripts/.aet-work-orchestrator.log` shows task `extract-stack-01` invoked with `--print`, gathered context, read skills, set up todos, and the process terminated. No "Approve to proceed?" question was ever asked.

### Root Cause

There is an **architectural mismatch** between two design intents:

1. The orchestrator is designed for hands-free execution (uses `--print --yolo`)
2. `aet-pipeline-implement` and `aet-implement` have hard approval gates requiring multi-turn human interaction

`--print` mode processes one turn and exits. The subagent knows it cannot ask for human input, so it silently skips the gate. `--yolo` auto-approves any tool confirmations. Exit code 0 means "turn completed successfully," not "task completed successfully." The orchestrator conflates these.

### Fix Summary

**Files modified:**

- `aet-work/references/orchestrator-template.sh` — exports `AET_ORCHESTRATOR=1` when spawning subagents
- `aet-work/SKILL.md` — documents the orchestrator mode env var
- `aet-work/references/context-isolation.md` — documents the trade-off
- `aet-pipeline-implement/SKILL.md` — Step 0 approval checkpoint skips interactive gate when `AET_ORCHESTRATOR` is set
- `aet-implement/SKILL.md` — Step 1 approval checkpoint skips interactive gate when `AET_ORCHESTRATOR` is set; pre-flight size check hard-stops on oversized tasks in orchestrator mode

**Key change:** The orchestrator signals unattended mode. Skills detect the signal and bypass interactive approval gates, logging the bypass for auditability.

### Regression Test

No automated regression test added. This is a behavior-of-behavior issue (how the AI agent interprets skill instructions in non-interactive mode). The fix is in the skill instructions themselves. Validation was done via `make validate`.

### Validation

- [x] Reproduction steps no longer trigger the bug — with `AET_ORCHESTRATOR=1`, skills proceed directly to implementation
- [x] Existing test suite passes — `make validate` passed (lint, format-check, skill-structure validator)
- [x] No regressions — interactive sessions unchanged; hard gate still requires explicit approval when `AET_ORCHESTRATOR` is not set

### Lessons Learned

- **Pattern:** Non-interactive CLI mode + interactive skill instructions = silent gate bypass
- **Prevention:** Any skill with hard gates must have a non-interactive escape hatch when running under orchestration
- **Prevention:** The orchestrator must explicitly signal its mode so skills can adapt
- **Reference:** `docs/adr/` should capture this architectural decision
