## Bug Report: aet-work Orchestrator Times Out on Long-Running Pipelines

## Metadata

- **Reported:** 2026-06-01T18:00:30+01:00
- **Severity:** High
- **Status:** resolved

## Symptoms

The aet-work orchestrator consistently fails when running `aet-pipeline-implement` tasks that take 30–60 minutes. It times out after 60 seconds — the default Shell tool timeout — preventing any long-running queued task from completing.

## Reproduction Steps

1. Have a work queue with plan files requiring `aet-pipeline-implement` (expected runtime 30–60 min per task)
2. Run `aet-work run`
3. The orchestrator script (`scripts/.aet-work-orchestrator.sh`) spawns `kimi` processes
4. Within ~60 seconds, the orchestrator or its child processes are killed due to timeout

## Root Cause

Two related issues in the orchestrator setup:

1. **Parent spawn timeout underspecified:** The `aet-work` skill instructed spawning the orchestrator via `Shell(run_in_background=true)` but did **not** specify an explicit `timeout`. While background mode avoids the 60s foreground default, the orchestrator may need 1–2+ hours for parallel pipeline batches.

2. **Child `kimi` processes used `--yolo`, not `--afk`:** The orchestrator template invoked `kimi --yolo`. In `--yolo` mode, `AskUserQuestion` is _not_ auto-dismissed — the user is "still reachable." In a background bash job with no terminal, an unanswered approval gate can hang or fail. `--afk` auto-dismisses questions _and_ auto-approves tools, which is the correct mode for true unattended execution.

## Fix Summary

- **Files modified:**
  - `aet-work/SKILL.md`
  - `scripts/.aet-work-orchestrator.sh`
  - `aet-work/references/afk-loop-orchestrator.sh`
- **Key change:**
  - `aet-work/SKILL.md` step 5 now specifies `Shell(run_in_background=true, timeout=7200)` (2-hour ceiling)
  - `aet-work/SKILL.md` step 3 now instructs agents to use `--afk` (or equivalent headless mode) so approval gates are auto-dismissed
  - Generated orchestrator and reference script updated from `--yolo` to `--afk`
- **Side effects:** None — only affects the unattended orchestrator path

## Regression Test

No automated regression test added (this is a skill-instruction / orchestration-level fix). Validation covered by `make validate` which passes.

## Validation

- [x] Reproduction steps no longer trigger the bug
- [x] Existing test suite passes with no new failures (`make validate` passes)
- [x] No regressions observed in related functionality

## Lessons Learned

- **Pattern:** Timeout mismatch between default tool defaults and real-world unattended pipeline durations
- **Prevention:** Any skill that spawns long-running background orchestrators must explicitly specify a `timeout` that exceeds the expected worst-case duration, not rely on defaults
- **Prevention:** Unattended orchestrators must use the most headless CLI mode available (`--afk` > `--yolo`) to prevent interactive gates from blocking or failing in background jobs
- **Reference:** Updated `aet-work/SKILL.md` step 3 and 5; updated `aet-work/references/afk-loop-orchestrator.sh`
