---
subject: telemetry-correctness
relates: [12, 35, 50, 52, 84, 85]
---

# Telemetry Records What Happened

## Status

Proposed. Amends ADR-012 (run directory and run summary) and the input data of
ADR-035 and ADR-052. PRD: `docs/prds/telemetry-correctness-prd.md`.

## Context

The telemetry archive (ADR-012) holds one stage record per agent session and
one run summary per run in `last-run.json`. `aet metrics`, `aet status`,
`aet panel`, `aet performance-report` and `aet mine-learnings` read these
records. ADR-035 and ADR-052 make the stage record's `result` and `exit_code`
the only failure signal of First-Pass Merge.

Run telemetry from three client projects showed that the records report
success for failed work. About 180 review and 23 verify stage records showed
success although their gate failed, because `result` follows the session exit
code and the gate runs after the record is written. A run of only requeues
ended with `outcome: success` and exit code 0. One run listed 94 copies of one
task id. Settlement summaries showed `Succeeded: 0` for completed work. 259 of
567 stage records in one project held a `stage` absent from their own
`actual_stages`, because the group path mixes target and entry states. A run
that crossed midnight wrote two run directories. Seven runs exited in under a
second with no reason recorded. The test suite wrote 265 rehearsal folders into
the operator's archive.

## Decision

1. **A stage record's `result` follows the gate.** When a stage has a gate and
   the gate fails, the record has `result: failure` and the failure class of
   the gate failure (ADR-084). `exit_code` keeps the session's exit code. A
   stage without a gate, or with a passing gate, keeps `result` from the exit
   code. The record is written once, after the gate check.
2. **A stage label is the target state.** `actual_stages` lists the state each
   workflow stage produces, and `stage` is its last element. Failure entries
   on the task use the same label. Workflow stages keep their entry-state
   names in `software.json`; the label convention applies to records only.
3. **A run summary counts each task once by its end state.** Each spawned task
   counts in exactly one of `tasks_succeeded`, `tasks_failed` and
   `tasks_requeued`; a task that ends the run in `ready`, also after an
   operator stop (ADR-085), counts as requeued. `attempts_failed` counts
   failed attempts and excludes `throttled` and `canceled`, as the ADR-084
   attempt cap does. A task that
   integrates, is staged with a conflict, or merges through a flush counts as
   succeeded. A run exits non-zero when any spawned task ends not succeeded.
   `outcome` is derived from `exit_code` inside the record builder.
   `cost_complete` is false when any stage cost of the run is unknown.
4. **Every run exit writes one summary with a reason.** A run that exits
   before its task loop writes a summary with nothing spawned, nothing failed
   and a fixed `reason` key. This includes lease refusals, queue-integrity
   refusals and preflight refusals in the CLI.
5. **One run, one run directory.** Child processes inherit the parent's run
   directory through `AET_RUN_DIR`. The date segment is the parent's start
   date.
6. **One resolver for user-level paths.** Every `~/.aet/` path comes from one
   module, with an environment override per path and `AET_HOME` for the root.
   The test suite redirects `AET_HOME`, and a test fails when code builds a
   `~/.aet/` path elsewhere.

## Consequences

- First-Pass Merge and pass rates fall for tasks whose gate failed. The
  ADR-035 definitions do not change; their input becomes correct. Dashboards
  show a step change at the upgrade.
- A run that leaves a requeued task exits 1. Scripts and the `aet-drive` loop
  treat it like a run with a skipped task.
- Failure signatures include the stage label, so a task that spans the
  upgrade restarts its signature count once.
- Group-session records before and after the upgrade carry different
  `actual_stages` conventions. **Rework** counts across the boundary can
  differ for one task.
- Old records stay as they are. Consumers accept records with and without the
  new fields.
- A refused run creates its own run directory. The panel shows it as a
  finished run with its reason.
- Recovery of tokens and cost from a killed session stays open. The run total
  states that it is incomplete.

## Alternatives Considered

- **Add a `gate_result` field and keep `result` on the exit code.** Rejected:
  every consumer reads `result`, so each would need a change to stay correct.
- **Rewrite the stage record after the gate.** Rejected: the archive is
  append-only, and a second record for one session counts as **Rework**.
- **Label stages by entry state.** Rejected: per-stage records already use
  target states, and history stays comparable with the target convention.
- **Count every requeue as a failed task.** Rejected: a task that is requeued
  and then succeeds would count twice.
- **Guard the test suite with a snapshot of `~/.aet/`.** Rejected: a live run
  on the same machine changes the archive and fails the guard falsely.
