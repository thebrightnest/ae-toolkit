---
id: telemetry-correctness
status: accepted
---

# PRD: Telemetry Records What Happened

## Overview

Stage records and run summaries report success for failed work. A stage whose
gate failed is recorded as a success. A run of only requeues ends with
`outcome: success` and exit code 0. Early refusals leave no reason, a group
session records a stage label that its own `actual_stages` does not hold, and
a run that crosses midnight writes two run directories. `aet metrics`,
`aet status`, `aet panel`, `aet performance-report` and `aet mine-learnings`
read these records, so their failure counts are too low. The test suite also
writes into the real `~/.aet/` directory, which pollutes the archive that these
tools read. This PRD makes the records state the real outcome and isolates the
test suite from the operator's home directory. ADR-086 records the decision.

## Intake Triage

Enhancement that closes defects shown in v1.23.0 code. The fix changes the
telemetry contract: the meaning of stage `result`, the run-summary fields, the
stage naming convention and the derivation of `outcome`. These changes move
the factory metrics of ADR-035, so they need a PRD and an ADR rather than a
targeted bug fix. Work class: `normal`. The change alters records and exit
codes, not queue state or merge decisions.

## Evidence

From `content/backlog/client-run-mining-report-2026-10-28.md`, problems 2, 5,
13 and 15, checked against v1.23.0 (`3d626d11`):

- **Stage result follows the exit code.** In one client project, about 180
  `reviewed` and 23 `verified` stage records show success although their gate
  failed. `_emit_stage_session` (`src/aet/cli/orchestrator.py`) runs before
  `_require_passing_verdict` on both stage paths of `process_task`, and
  `telemetry.stage_record` sets `result` from the exit code.
- **Requeues count as nothing.** `_finalize_task` returns `failures: 0` after
  a requeue, and `run_batch` sets the exit code from `failures`. A run of only
  requeues exits 0.
- **Duplicate task ids.** `_spawn_pass` appends to `task_ids` on every spawn.
  One run recorded `tasks_spawned=94` with 94 copies of one id.
- **Lost successes.** `_cleanup_task` counts neither `staged_conflict` results
  nor merge-train flushes. 8 of 9 settlement summaries in one project show
  `Succeeded: 0`.
- **Outcome and exit code disagree.** The "no commits" branch of `run_single`
  sets exit code 1 and keeps `success=True`. Three runs in one project record
  `outcome: success` with exit code 1. The leftover snapshot is taken before
  the `finally` cleanup, so `in_progress` counts persist in the summary.
- **Stage attribution.** A standard group session records `stage` as the
  target state and `actual_stages` as the entry states. 259 of 567 stage
  records in one project hold a `stage` absent from `actual_stages`.
  `_record_failure_on_task` stores entry states, and the timeout path stores
  `in_progress` when the task record has no `stage`.
- **Midnight split.** `RunLogger` takes the date at construction, and each
  child process builds its own. A run that crosses midnight writes two run
  directories and two `last-run.json` files. `_usage_aggregates` reads only
  the parent's directory, so the run totals miss the children's records.
- **Conflict counter.** No caller passes `parallel_conflicts_detected`. One
  run recorded 0 while its merges needed 10 conflict resolutions.
- **Unknown cost reads as absent.** A killed session records `None` for tokens
  and cost. 34 of 126 run summaries in one project have no `total_cost_usd`,
  and nothing marks the total as incomplete.
- **No reason.** `run_summary_record` has no `reason` field. Seven runs in one
  project exited 1 in under 0.6 s with no task spawned. Early exits in
  `run_single` write `tasks_failed=1` with nothing spawned. The lease refusals,
  the batch queue-integrity refusal and every `_validate_preflight` exit in
  `src/aet/cli/main.py` write no summary.
- **Test suite writes to the real home.** `~/.aet/telemetry/` holds 265
  `nsr-07-rehearsal-*` folders. `tests/conftest.py` isolates the telemetry
  archive, but not `evidence.DEFAULT_REPORTS_DIR`, the archive constants in
  `cli/mine_learnings.py`, `cli/retro.py` and `panel/serve.py`, or the config
  paths in `backends/factory.py` and `cli/configure_backend.py`.

## Goals

- A stage record shows failure when its gate fails.
- A run summary counts every task once by its end state, and its `outcome`
  agrees with its exit code.
- Every run that exits writes one summary in one run directory, with a reason
  when it ends early.
- A stage label means the same thing in every stage record and failure entry.
- A test run never reads or writes the real `~/.aet/`.

## Non-Goals

- Recovery of tokens and cost from a killed session's log. Filed as backlog
  item `killed-session-usage-recovery.md`.
- Per-task progress in `aet status` and the run log
  (`run-progress-not-visible-per-task.md`).
- An operator stop recorded as a timeout (run-lifecycle PRD, ADR-085), and a
  positive exit 143 not read as a kill.
- Rewrite or migration of existing archive records.
- Cleanup of the 265 rehearsal folders in the operator's archive. This is a
  one-off manual step.
- New factory metric definitions. ADR-035 definitions stay; their input data
  becomes correct.

## Requirements

- **R-1**: A stage record whose session exits 0 and whose gate then fails has
  `result: failure` and a `failure_class` that matches the class recorded on
  the task for that gate failure. `exit_code` keeps the session's real exit
  code.
- **R-2**: A stage record whose gate passes, and a stage with no gate, keep
  the current rule: `result` follows the exit code.
- **R-3**: The verdict-recovery session writes its stage record with the same
  rule as R-1 and R-2.
- **R-4**: A stage record's `actual_stages` lists the target state of each
  workflow stage that the session ran, in run order. The record's `stage` is
  the last element of `actual_stages`.
- **R-5**: A failure entry on the task records the target state of the stage
  that failed. It never records `in_progress` or another queue state that no
  workflow stage produces.
- **R-6**: A run summary holds `tasks_spawned` as the count of distinct task
  ids spawned, and `task_ids` as those ids without duplicates, in first-spawn
  order.
- **R-7**: A run summary counts each spawned task once in exactly one of
  `tasks_succeeded`, `tasks_failed` and `tasks_requeued`, by the task's end
  state in that run. `tasks_requeued` counts every spawned task that ends the
  run in `ready`, also a task canceled by an operator stop (ADR-085). A task
  that is requeued and then succeeds in the same run counts as succeeded.
- **R-8**: A run summary holds `attempts_failed`: the count of task attempts
  in that run that ended in failure, requeue or quarantine, whatever the
  task's end state. Attempts that end `throttled` or `canceled` do not count,
  as for the attempt cap of ADR-084.
- **R-9**: A task that integrates through `staged_conflict`, a direct merge or
  a merge-train flush counts as succeeded. A task staged for a human merge
  counts as succeeded once.
- **R-10**: A run exits non-zero when any spawned task ends the run not
  succeeded. A run summary's `outcome` is `success` when `exit_code` is 0 and
  `failure` otherwise, on every write path.
- **R-11**: The `leftover` counts in a run summary are read after the final
  cleanup of every task, so no task that the run reaped shows as
  `in_progress`.
- **R-12**: The "no commits" branch of `run_single` records the task as
  failed: `tasks_failed=1`, `tasks_succeeded=0`, `outcome: failure`.
- **R-13**: `parallel_conflicts_detected` counts the tasks in the run whose
  integration returned `staged_conflict` or whose merge-train flush returned a
  restack conflict.
- **R-14**: A run summary holds `cost_complete`: `false` when any stage record
  of the run has a `null` `cost_estimate`, `true` otherwise. A `null` stage
  cost is never summed as 0 without that flag.
- **R-15**: A run summary holds `reason`: `null` for a run that reached its
  task loop, and a fixed reason key for every early exit. The keys are
  `lease_refused`, `queue_integrity`, `base_hygiene`, `intake_refused`,
  `workflow_error`, `epic_mismatch`, `worktree_blocked`, `breaker_tripped`,
  `cli_unresolvable` and `plan_missing`.
- **R-16**: A run that exits before it spawns a task writes a summary with
  `tasks_spawned=0`, `tasks_failed=0` and its `reason`. This holds for the
  lease refusals, the queue-integrity refusal and every exit of
  `_validate_preflight`.
- **R-17**: All processes of one run write into the run directory that the
  parent created. A child process takes that directory from the parent and
  does not derive its own date.
- **R-18**: `aet run`'s usage totals include every stage record of the run,
  also when the run crosses midnight UTC.
- **R-19**: The consumers of run summaries and stage records accept records
  with and without the new fields: `aet status`, `aet panel`,
  `aet telemetry report`, `aet performance-report`, `aet metrics` and
  `aet mine-learnings`. `aet telemetry report` sums `tasks_requeued`.
- **R-20**: During a test session, every path under the real `~/.aet/` that
  aet code reads or writes resolves to a temporary directory. This holds for
  function-scoped tests and for `setUpClass` code.
- **R-21**: A test fails when any module under `src/aet/` builds a path under
  `~/.aet/` outside the one resolver module, and when any resolver function
  returns a path under the real home directory during a test session.
- **R-22**: Every `~/.aet/` path in aet code comes from one resolver module.
  `panel/serve.py`, `cli/mine_learnings.py`, `cli/retro.py`,
  `backends/factory.py` and `cli/configure_backend.py` use it and keep no
  constant of their own. Each resolver honors an environment override.
- **R-23**: ADR-086 records the stage-result rule, the stage naming
  convention and the run-summary accounting, and amends ADR-012, ADR-035 and
  ADR-052. `CONTEXT.md` defines **Run Summary** and **Stage Record** with the
  new fields.
- **R-24**: Existing telemetry, orchestrator and metrics tests pass, except
  where they assert the old behavior. Each changed assertion names the
  requirement that changes it.

## User Stories

- As an operator, I want a stage that failed its gate to show as failed, so
  that metrics and the panel show the real failure rate. (satisfies: R-1, R-2,
  R-3)
- As an operator, I want a run summary that counts each task once by its end
  state, so that a run of requeues does not report success. (satisfies: R-6,
  R-7, R-8, R-9, R-10, R-11, R-12)
- As an analyst who mines run telemetry, I want one stage naming convention,
  so that stage records and failure entries join on stage. (satisfies: R-4,
  R-5)
- As an analyst, I want conflict counts and an incomplete-cost flag, so that
  run totals do not hide merges and killed sessions. (satisfies: R-13, R-14)
- As an operator, I want a reason in `last-run.json` for every early exit, so
  that a run that spawned nothing explains itself. (satisfies: R-15, R-16)
- As an operator, I want one run directory per run, so that a run past
  midnight has one summary and full totals. (satisfies: R-17, R-18)
- As a maintainer, I want the test suite to leave my `~/.aet/` untouched, so
  that the archive holds only real runs. (satisfies: R-20, R-21, R-22)

## Acceptance Criteria

- [ ] A task whose review session exits 0 and whose review verdict is `fail`
  produces a stage record with `exit_code: 0` and `result: failure`.
  (satisfies: R-1)
- [ ] A passing gate and a stage with no gate still produce
  `result: success` on exit 0. (satisfies: R-2)
- [ ] A verdict-recovery session that leaves a failing verdict produces a
  stage record with `result: failure`. (satisfies: R-3)
- [ ] A standard group session over `plan-approved` and `implemented`
  produces `actual_stages: [implemented, qa-complete]` and
  `stage: qa-complete`. (satisfies: R-4)
- [ ] A timeout on a task record without `stage` records a failure entry whose
  stage is a workflow target state. (satisfies: R-5)
- [ ] A batch run in which one task is requeued twice and then succeeds writes
  `tasks_spawned: 1`, `task_ids` with one id, `tasks_succeeded: 1`,
  `attempts_failed: 2`, exit code 0. (satisfies: R-6, R-7, R-8, R-10)
- [ ] A batch run whose only task is requeued and left `ready` writes
  `tasks_requeued: 1`, `outcome: failure` and a non-zero exit code.
  (satisfies: R-7, R-10)
- [ ] A batch run whose task ends `staged_conflict` writes
  `tasks_succeeded: 1` and `parallel_conflicts_detected: 1`. (satisfies: R-9,
  R-13)
- [ ] A batch run whose task merges through a merge-train flush writes
  `tasks_succeeded: 1`, and the settlement summary shows `Succeeded: 1`.
  (satisfies: R-9)
- [ ] A batch run stopped by a signal writes no `in_progress` count for a
  task it reaped. (satisfies: R-11)
- [ ] `aet run-one` on a task that produces no commits writes
  `outcome: failure`, `tasks_failed: 1` and exit code 1. (satisfies: R-10,
  R-12)
- [ ] A run with one stage record whose `cost_estimate` is `null` writes
  `cost_complete: false`. (satisfies: R-14)
- [ ] `aet run` refused by a live lease writes `last-run.json` with
  `reason: lease_refused` and `tasks_failed: 0`. (satisfies: R-15, R-16)
- [ ] `aet run-one` on a plan without a frontmatter id writes
  `reason: intake_refused` or `plan_missing`, and `tasks_spawned: 0`.
  (satisfies: R-15, R-16)
- [ ] A run whose parent starts before midnight UTC and whose child stage
  ends after it writes all records into one run directory, and the run totals
  include the child's tokens. (satisfies: R-17, R-18)
- [ ] `aet status`, `aet panel`, `aet telemetry report`,
  `aet performance-report`, `aet metrics` and `aet mine-learnings` read an
  archive that mixes v1.23.0 records and new records without error.
  (satisfies: R-19)
- [ ] `make test` on a machine with a populated `~/.aet/` leaves every file
  under it unchanged, and no new folder appears. (satisfies: R-20, R-21)
- [ ] A module that adds `Path.home() / ".aet"` outside the resolver module
  makes the guard test fail with the module name. (satisfies: R-21)
- [ ] A resolver that ignores its override makes the guard test fail with
  the resolver name. (satisfies: R-21)
- [ ] `grep` finds no `.aet` home path outside the resolver module.
  (satisfies: R-22)
- [ ] `aet docs lint` passes, ADR-086 exists, and `CONTEXT.md` defines
  **Run Summary** and **Stage Record**. (satisfies: R-23)
- [ ] `make validate` passes. (satisfies: R-24)

## Technical Notes

- Dependency: `gfe-01-gate-failure-is-evidence` and `gfe-02-bounded-retries`
  change `_require_passing_verdict`, `_finalize_task` and the requeue path.
  This PRD's tasks that touch those functions are blocked by them. gfe-01
  gives every gate failure a failure class, which R-1 reuses.
- Dependency: the run-lifecycle PRD (`docs/prds/run-lifecycle-prd.md`,
  ADR-085) changes the same paths. `rl-01-operator-stop-is-canceled` records
  a signal shutdown as `canceled` in `_finalize_task`, the `finally` cleanup
  of `run_batch` and `run_single`, and adds `canceled` to the stage record and
  run summary of a stopped run. `rl-04-shared-run-lease` moves the run lease
  and its refusal. `tlc-01` and `tlc-02` are blocked by `rl-01`; `tlc-03` is
  blocked by `rl-04`. The run-lifecycle PRD leaves the `reason` field (CR-13)
  to this PRD.
- R-1 needs the verdict before the stage record is written. Either
  `_emit_stage_session` moves after `_require_passing_verdict`, or the gate
  result is passed into it. The stage record is appended once per session; it
  is not rewritten.
- `track_record._has_failed_stage` reads `result == "failure"` or a non-zero
  `exit_code`, so R-1 lowers First-Pass Merge for tasks whose gate failed.
  This is the intended correction; ADR-086 states it.
- R-4 changes `tests/orchestrator/test_orchestrator.py::test_emit_stage_session_populates_actual_stages_for_group`,
  which asserts the current entry-state span. `_implement_targeted_commands`
  checks `"implemented" in actual_stages` and stays correct under R-4.
  `track_record` rework counts by `actual_stages`; older group records keep
  entry states, so rework counts across the version boundary can differ.
- R-5: the target state of a stage is `workflow.next_stage(stage.name)`.
  Callers of `_record_failure_on_task` in `run_stage`, `run_stage_group` and
  the finalize timeout path pass the entry state today. A changed stage label
  changes the failure signature string, so signatures recorded before and
  after the change do not match. The per-task breaker counts within one task;
  a task that spans the upgrade can need one more failure to trip.
- R-7 and R-8: `_finalize_task` returns per-attempt counts. The run summary
  needs a per-task end-state map in `run_batch`, set by `_cleanup_task` and by
  the merge-train flush paths.
- R-11: the leftover snapshot moves after the `finally` cleanup in
  `run_batch`.
- R-15 and R-16: the `_validate_preflight` exits in `src/aet/cli/main.py`
  raise `typer.Exit` before a `RunLogger` exists. They need a small summary
  writer that creates the run directory. The lease refusal must not write into
  the live run's directory; it writes its own.
- R-17: the parent exports its run directory, for example as
  `AET_RUN_DIR`, next to `AET_RUN_ID`. `RunLogger` uses it when set.
  `orchestrator.py` builds `RunLogger` at six places.
- R-20: `evidence.reports_dir()` honors `AET_REPORTS_DIR`. The fixtures in
  `tests/conftest.py` must set the variable and patch the module constants,
  because tests that use `patch.dict(os.environ, clear=True)` drop the
  variable. `_isolate_class_scoped_setup` re-applies the redirections for
  `setUpClass`. `cli/configure_backend.py` writes `~/.aet/<slug>/config.json`
  with no override and needs one. `conftest.py` sets `AET_PLANS_ARCHIVE_DIR`,
  which no code under `src/` reads.
- R-21: the guard is static and resolver-based, not a filesystem snapshot. A
  snapshot of the real `~/.aet/` fails falsely when a live `aet run` on the
  same machine writes to the archive during a test session. The static part
  scans `src/aet/` for `.aet` home paths; the resolver part calls each
  resolver under the test fixtures and checks the result.

## Risks

- **Metrics drop.** First-Pass Merge and pass rates fall for tasks whose gate
  failed. Dashboards show a step change at the upgrade. Accepted: the old
  values were wrong.
- **Exit-code change.** A run of only requeues now exits non-zero. A wrapper
  script that treats a non-zero exit as a crash reacts differently. ADR-086
  and the changelog state the change.
- **Signature break across the upgrade.** R-5 changes stage labels in failure
  entries, so a task that spans the upgrade restarts its signature count.
- **Guard gaps.** The guard catches paths that aet code builds. A test that
  writes to `Path.home()` by itself is not caught.

## Open Questions

- None.

*Stage: synced*
*Next step: run `aet-ship`*
