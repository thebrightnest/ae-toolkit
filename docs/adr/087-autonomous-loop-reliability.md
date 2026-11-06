---
subject: autonomous-loop-reliability
relates: [4, 29, 60, 78, 79, 85]
---

# Bounded Subprocess Execution, Deterministic Concurrency, and Autonomous Guard Remediation

## Status

Proposed. Amends ADR-004, ADR-029, ADR-078, and ADR-079. PRD:
`docs/prds/autonomous-loop-reliability-prd.md`.

## Context

In long-running autonomous pipelines (`aet run` and `/aet-drive`), executions
can stall or deadlock indefinitely due to three systemic defects:

1. **Unbounded Subprocess Validation & Test Sleep Races:** `_run_flush_validation`
   (`src/aet/train.py`) executes `validate_command` without an execution timeout.
   When pre-merge validation runs under heavy single-threaded CPU load,
   orchestrator concurrency tests that rely on sub-second `time.sleep` races
   deadlock or miss scheduling windows. Subprocesses hang indefinitely on lock
   contention, freezing the test runner and the entire merge train.
2. **Autonomous Deadlocks on Guard Refusal:** When a coding subagent creates a
   single monolithic commit across a multi-task plan, `is_monolithic_commit`
   (`src/aet/integrate.py`) halts integration with `guard_refused` and stages
   the task in `awaiting_merge`. Because the autonomous orchestrator has no
   remediation mechanism for guard refusals, the task remains stuck in
   `awaiting_merge` indefinitely, blocking all downstream tasks.
3. **Environment Variable Loss in Spawned Subshells:** `run_batch` spawns child
   orchestrators and worktree tools with `env = os.environ.copy()`, but does not
   explicitly inject `AET_CLI_BIN`, `AET_REPO_ROOT`, or active execution flags.
   Subshell commands and isolated test runners rely on fragile parent process
   ancestry detection that fails in non-interactive environments.

## Decision

1. **Explicit Environment Propagation:** `run_batch`, `process_task`,
   `_run_flush_validation`, and worktree execution helpers explicitly set
   `AET_CLI_BIN`, `AET_REPO_ROOT`, and active execution configuration in the
   child process environment, ensuring subshell and tool invocations never
   depend on ancestry detection.
2. **Bounded Subprocess Timeouts with Process Group Cleanup:** All merge-train
   flush validations, integration commands, and test subprocess runners enforce
   a bounded timeout (`validation_timeout`, default 600 seconds). On timeout,
   the process group (`os.killpg`) is terminated immediately and a deterministic
   `timeout` failure verdict is recorded.
3. **Deterministic Concurrency Test Synchronization:** All orchestrator and
   merge-train concurrency tests eliminate `time.sleep` race loops in favor of
   deterministic synchronization primitives (POSIX locks or marker files) and
   enforce per-test execution timeouts.
4. **Shift-Left Commit Splitting:** `skills/aet-implement/SKILL.md` and
   `skills/aet-ship/SKILL.md` instruct coding agents to create separate atomic
   commits per plan task before staging, preventing monolithic commit
   rejections at intake.
5. **Autonomous Monolithic Commit Remediation:** When `integrate` encounters
   `guard_refused` due to a monolithic commit during an autonomous run, the
   orchestrator does not leave the task parked in `awaiting_merge`. It either
   auto-splits using declared per-task file paths from the plan spec, or returns
   the task to `in_progress` with an actionable failure verdict directing the
   worker agent to run `aet ship split`.
