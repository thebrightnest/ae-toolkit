---
id: autonomous-loop-reliability
status: accepted
---

# PRD: Autonomous Loop Reliability — Guard Remediation, Bounded Validation, and Environment Propagation

## Overview

In long-running autonomous pipelines (`aet run` and `/aet-drive`), executions can freeze or get stranded for days due to three interacting failure modes:
1. **Unbounded subprocess execution & sleep-based concurrency tests**: When pre-merge validation triggers the test suite under single-threaded CPU load, orchestrator concurrency tests relying on `time.sleep` races deadlock or hang indefinitely because `subprocess.run` calls in merge train flushes and test helpers have no execution timeouts.
2. **Monolithic commit guard deadlocks in autonomous runs**: When a coding agent creates a single commit for a multi-task plan, `aet ship merge` halts on its monolithic commit guard and stages the task in `awaiting_merge` (`guard_refused`). Because the autonomous runner has no remediation path for guard refusals, the task remains stuck in `awaiting_merge` indefinitely, blocking all downstream tasks.
3. **Subshell environment loss**: When child orchestrator processes, git worktrees, or validation subshells are spawned, critical execution variables—notably `AET_CLI_BIN`—are not consistently propagated in `env`. When spawned tools attempt to detect the agent from parent process trees, detection fails or picks incorrect fallbacks.

This PRD hardens the autonomous loop by enforcing deterministic environment propagation, bounding all validation and test subprocess executions with strict timeouts, eliminating flaky test concurrency races, shifting multi-task commit enforcement into skill instructions, and providing autonomous remediation for monolithic commit guard refusals. ADR-087 records the architectural decisions.

## Intake Triage

Enhancement closing systemic reliability and deadlock defects in the autonomous execution loop, merge validation, and test harness.
Work class: `critical`, because it affects merge train execution, test runner reliability, subprocess life cycles, and autonomous task transition rules.

## Evidence

From the post-mortem of the multi-day run on the `run-lifecycle` and `telemetry-correctness` epics (commits `3665c05b` through `ab4dfa97`):
- **Frozen Validation Processes:** Merge flush validations in temporary bisect directories (`/tmp/aet-train-bisect-*`) froze on child processes (`aet_state.py transition`), keeping pytest workers and `aet ship merge` deadlocked indefinitely.
- **Missing Subprocess Timeouts:** `_run_flush_validation` in `src/aet/train.py` calls `subprocess.run(cmd_list, cwd=worktree_dir, capture_output=True, text=True)` with no `timeout`, allowing stuck child processes to block forever.
- **Guard Refusal Stranding:** Multiple tasks (`rl-03`, `tlc-01`, `tlc-02`, `tlc-03`) were repeatedly halted by `is_monolithic_commit` in `src/aet/integrate.py` (`⛔ Monolithic commit detected`). Tasks sat in `awaiting_merge` with no automated remediation or actionable retry emitted to the autonomous orchestrator.
- **Missing `AET_CLI_BIN` Propagation:** In `src/aet/cli/orchestrator.py`, `env` passed to child orchestrators did not explicitly set `env["AET_CLI_BIN"] = adapter.bin`, causing child subshells to rely on ancestry detection.

## Goals

- Eliminate infinite hangs during merge train validation and test suite execution by bounding all validation and child tool subprocesses with timeouts.
- Replace fragile `time.sleep` timing races in concurrency tests with deterministic synchronization markers.
- Guarantee that `AET_CLI_BIN`, `AET_REPO_ROOT`, and critical execution flags are automatically propagated to all spawned subshells, child orchestrators, and worktree validation environments.
- Prevent multi-task monolithic commits early during implementation via skill-level enforcement.
- Provide autonomous remediation for monolithic commit guard refusals so that `aet run` / `/aet-drive` does not strand tasks in `awaiting_merge`.

## Non-Goals

- Replacing or weakening the monolithic commit safety guard itself; atomic commits per plan task remain mandatory.
- Re-architecting the git merge-train bisect algorithm.
- Modifying external agent CLI adapters (`claude`, `agy`, `opencode`, `codex`).

## Requirements

- **R-1 (Environment Propagation):** `run_batch`, `process_task`, `_run_flush_validation`, and worktree test runners must explicitly inject `AET_CLI_BIN`, `AET_REPO_ROOT`, and active execution configuration into `env` when spawning child orchestrator processes, validation commands, or subshell tools.
- **R-2 (Bounded Subprocess Timeouts):** `_run_flush_validation` in `src/aet/train.py`, `integrate` subprocess invocations in `src/aet/integrate.py`, and `aet ship` runner commands must enforce a bounded timeout (configurable via `validation_timeout`, default 600s). If a validation command exceeds the timeout, the process group must be terminated and a deterministic `timeout` failure verdict recorded.
- **R-3 (Deterministic Concurrency Tests):** Concurrency tests (`tests/orchestrator/test_concurrent_auto_merge.py`, `tests/orchestrator/test_merge_train_flush.py`, etc.) must eliminate all sub-second `time.sleep` race conditions in favor of deterministic synchronization primitives (event files, barrier markers, or explicit state polling) and must enforce per-test execution timeouts.
- **R-4 (Shift-Left Commit Splitting Enforcement):** Skill instructions in `skills/aet-implement/SKILL.md` and `skills/aet-ship/SKILL.md` must explicitly instruct agents implementing multi-task plans (`plan_task_count(spec) > 1`) to create separate atomic commits per task before staging or calling `aet ship merge`.
- **R-5 (Autonomous Monolithic Commit Remediation):** When `integrate` encounters a monolithic commit guard refusal during an autonomous batch run (`aet run` / `/aet-drive`), it must not leave the task deadlocked indefinitely in `awaiting_merge`. The orchestrator must either:
  1. Automatically execute `aet ship split` when unambiguous file-to-task mappings exist in the plan spec (`plan.tasks[].files`), or
  2. Emit a structured `guard_refused` failure verdict that requeues the task back to `in_progress` with an explicit diagnostic instruction for the worker agent to execute `aet ship split`.

## User Stories

- As an operator running `/aet-drive`, I want spawned subshells and validation commands to inherit `AET_CLI_BIN` so that agent CLI resolution never fails in background worktrees. (satisfies: R-1)
- As an operator running unattended batch runs, I want pre-merge validation commands to fail closed with a timeout if they hang, so that deadlocked tests do not freeze the entire pipeline. (satisfies: R-2)
- As an engineer running `make validate`, I want concurrency tests to be deterministic and robust under heavy CPU load, so that race conditions do not cause false test failures or deadlocks. (satisfies: R-3)
- As an autonomous worker implementing a multi-task plan, I want skill instructions that prompt me to commit per-task atomically, preventing monolithic commit rejections at the merge gate. (satisfies: R-4)
- As an autonomous orchestrator, I want automatic remediation or requeue diagnostics when a monolithic commit guard is encountered, so that tasks are not stranded indefinitely in `awaiting_merge`. (satisfies: R-5)

## Acceptance Criteria

- [ ] `AET_CLI_BIN` is present in `os.environ` of all spawned child orchestrators, worktrees, and `_run_flush_validation` executions. (satisfies: R-1)
- [ ] `_run_flush_validation` in `src/aet/train.py` terminates child processes and returns a failure status if execution exceeds the configured timeout. (satisfies: R-2)
- [ ] `tests/orchestrator/test_concurrent_auto_merge.py` and `tests/orchestrator/test_merge_train_flush.py` pass cleanly 10 times consecutively under simulated load without sleeping on timing races. (satisfies: R-3)
- [ ] `skills/aet-implement/SKILL.md` and `skills/aet-ship/SKILL.md` include explicit instructions requiring atomic per-task commits for multi-task plans. (satisfies: R-4)
- [ ] An autonomous batch run on a multi-task monolithic commit does not stall indefinitely in `awaiting_merge`; it either auto-splits via task-declared file sets or transitions back to `in_progress` with split instructions. (satisfies: R-5)

## Technical Notes

- Architecture decision recorded in `docs/adr/087-autonomous-loop-reliability.md`.
- Concurrency test synchronization should use sentinel files or POSIX file locks rather than arbitrary sleep delays.
- Subprocess timeout termination must terminate the entire process group (`start_new_session=True` / `os.killpg`) to avoid leaving orphaned child processes behind.

## Open Questions

- None; all architectural questions resolved in Step 1 clarify-goal.

*Stage: scope-validated*
*Next step: run `aet sprint add`*
