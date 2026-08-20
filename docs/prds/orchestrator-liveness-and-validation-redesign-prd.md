# PRD: Orchestrator Liveness and Validation Redesign

## Overview

Redesign the orchestrator's session supervision and validation workflow to eliminate false timeout kills and redundant full-suite test runs. The current stall watchdog measures stdout silence, which misclassifies alive-but-quiet sessions (background tasks, subagents, long validations) as stalled. The current prompt instructs agents to run validations in the foreground, which conflicts with the Bash tool's 300-second foreground cap and forces silent background waits. This PRD replaces stdout-silence detection with hybrid process-tree + run-log liveness, splits validation by stage, introduces single-run file-hash caching for incremental validation, and removes the conflicting foreground-validation instruction.

## Goals

- Eliminate false timeout kills of healthy agent sessions (measured by zero `timeout` failure classifications on sessions that were actively working)
- Ensure `aet-qa` remains the sole owner of full-suite validation, always running fresh and unconditionally
- Reduce redundant full-suite test runs within a single orchestration run
- Maintain a hard wall-clock backstop as a last-resort ceiling for truly stuck sessions

## Non-Goals

- Changing the CLI adapter interface or adding new adapters
- Changing the pipeline stage model (plan-approved → implemented → reviewed → secure → synced)
- Parallel validation (running the full suite concurrently with agent work)
- Cross-run validation caching (cache persists only within a single `aet run`)
- Changing the Bash tool's foreground timeout cap (external constraint)

## Requirements

- **R-1**: The orchestrator must detect session liveness using hybrid signals: process-tree activity and run-log/file writes. Stdout silence alone must not trigger a kill.
- **R-2**: All CLI adapters must use the same supervision model with parity.
- **R-3**: A hard wall-clock backstop (default 7200 s) must remain as a ceiling even when hybrid liveness indicates activity.
- **R-4**: `aet-implement` must run targeted tests only, using path-based selection as a floor (same directory or matching name) plus agent-driven additions.
- **R-5**: `aet-qa` must run the full test suite unconditionally, with no caching or skipping.
- **R-6**: Validation results may be cached within a single run using file-hash invalidation on source, test, and dependency files. The cache must not persist across runs.
- **R-7**: The orchestrator prompt must not instruct agents to run validations in the foreground or forbid background validations.
- **R-8**: When `aet-qa` fails on a test that `aet-implement` should have caught, the failure record must include gap analysis (which test was missed and why).

## User Stories

- As an orchestrator operator, I want healthy agent sessions to survive long background tasks so that tasks complete instead of being killed by false timeouts (satisfies: R-1, R-2, R-3)
- As an agent implementing a task, I want to run only relevant tests during iteration so that I get fast feedback without redundant full-suite runs (satisfies: R-4, R-6)
- As a reviewer, I want `aet-qa` to always run the full suite fresh so that no bug slips through because of stale validation state (satisfies: R-5)
- As an orchestrator operator, I want to understand why a task failed validation so that I can improve test selection guidance (satisfies: R-8)

## Acceptance Criteria

- [ ] A session running a 60-minute background task with active process-tree descendants is not killed by the stall watchdog (satisfies: R-1)
- [ ] A session with no process-tree activity and no run-log writes for the stall interval is killed and classified as `timeout` (satisfies: R-1)
- [ ] Both kimi and claude adapters use identical liveness detection logic (satisfies: R-2)
- [ ] A session exceeding 7200 s wall-clock is killed even if process-tree activity is present (satisfies: R-3)
- [ ] `aet-implement` on a plan that modifies `src/aet/foo.py` runs at minimum `tests/**/test_foo.py` and any test importing `foo` (satisfies: R-4)
- [ ] `aet-qa` always executes the full pytest suite regardless of prior validation results (satisfies: R-5)
- [ ] Within a single run, re-running validation after changing only docs/plans files skips re-running tests (satisfies: R-6)
- [ ] A fresh `aet run` never reuses validation results from a previous run (satisfies: R-6)
- [ ] The orchestrator prompt no longer contains the string "never background validations" (satisfies: R-7)
- [ ] A QA failure record includes the name of the missed test and the reason it was not run during implementation (satisfies: R-8)

## Technical Notes

- The hybrid liveness detector should poll the process tree (e.g. via `ps` or `/proc`) and monitor run-log file mtime at a fixed interval (e.g. 10 s). Either signal resets the stall timer.
- File-hash caching should hash `src/`, `tests/`, `pyproject.toml`, and lockfiles. Hash computation should be fast (e.g. SHA-256 of file contents, not git objects).
- The cache key should include the file hash and the validation command. Cache storage should be in the run-scoped telemetry directory.
- The path-based test selection floor should be implemented as a helper in `aet-implement` or a shared validation module, not as a hard gate in the orchestrator.
- Gap analysis on QA failure should compare the tests run during implementation against the failed tests and record the delta.

## Open Questions

- Should the hybrid liveness detector have a per-adapter configuration for polling interval, or is a global default sufficient?
- Should the validation cache be stored in the worktree or in the run telemetry directory?
- Should the agent be required to output its test-selection rationale as structured data (JSON) or is free text in the output sufficient for gap analysis?

## Divergence Summary

_Recorded: 2026-08-20 — Branch: validation-02-single-run-caching (cumulative since validation-01-stage-based-split)_

### Changed from plan

- None for `docs/plans/validation-01-stage-based-split.md`.
- `docs/plans/validation-02-single-run-caching.md` Task 2: cache integration was implemented through `skills/aet-implement/SKILL.md` instruction updates plus helper functions in `src/aet/validation.py`, rather than through `src/aet/validation.py` alone.

### Added (unplanned)

- `scripts/validate-skills.sh`: Updated the link checker to strip inline code before matching links. Required because the revised `skills/aet-qa/SKILL.md` contains backtick-wrapped phrases that the previous regex misidentified as markdown links. (validation-01)
- `.agents/doc-rules.yaml`: Updated `must_contain` assertions to match the new `aet-qa` skill contract (full suite unconditionally, no caching, gap analysis). Required to keep skill-structure validation green after the skill text changed. (validation-01)
- `skills/aet-implement/SKILL.md`: Added single-run validation cache instructions so `aet-implement` agents use the new `aet.validation.cached_result` / `aet.validation.record_result` helpers. Required because the cache is consumed through skill behavior, not only through library code. (validation-02)

### Deferred

- PRD requirements **R-1**, **R-2**, and **R-3** (hybrid process-tree + run-log liveness detection with a hard wall-clock backstop) remain unimplemented.

_Stage: synced_
_Next step: run `aet-ship`_
