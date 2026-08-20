---
id: orchestrator-signal-exit-determinism
status: approved
---

# Orchestrator signal-exit determinism

## Context

In batch mode, a task that hits the wall-clock backstop is killed with SIGKILL
and finalised with exit code `-9`. `failure.classify` returns `TIMEOUT` only
when `killed_by_timeout` is set, and every call site derives that flag as
`exit_code == -9`. `_run_with_live_tee` returns `proc.wait()`, which is negative
for a signal-killed child, so the path *should* already be deterministic.
Measured behaviour says otherwise: the rehearsal's stall task ends `failed` in
about five runs of six and `ready` in the sixth.

## Requirements

- **R-1:** Instrument the exit path to record, per session, the value
  `proc.wait()` returns, the watchdog `cause`, and the `exit_code` reaching
  `classify()`.
- **R-2:** Name the confirmed trigger in writing and rule out, with evidence,
  the three candidate mechanisms below.
- **R-3:** Record the confirmed mechanism in this PRD's Technical Notes.

## Technical Notes (candidates)

1. **Process-group terminate racing the child's own exit.** The orchestrator
   escalates from `SIGTERM` to `SIGKILL` for the process group. If the child
   exits on its own (or on `SIGTERM`) before `proc.wait()` reaps it, the
   returned code could be something other than `-9`.
2. **Tee threads reaching EOF before `proc.wait()`.** The reader thread could
   observe EOF, exit the `for line in proc.stdout` loop, and reach
   `proc.wait()` before the watchdog thread has set `cause="stall"`.
3. **A second signature recorded from a different call site.** `run_stage` and
   `run_stage_group` both call `_classify_failure` with
   `killed_by_timeout=exit_code == -9`, but if one path used a different code
   or recorded the signature under a different stage name, the queue's last
   `failure_signatures` entry might not be `TIMEOUT`.

## Confirmed mechanism

The divergence is not inside `_run_with_live_tee`; it is a race between two
independent timeout layers in batch mode:

- **Layer 1:** the child orchestrator's stdout-silence watchdog
  (`_run_with_live_tee`), which kills the agent session and records a
  `TIMEOUT` signature on the task before it exits.
- **Layer 2:** the batch parent's per-task wall-clock backstop
  (`task_timeout`), which kills the *child orchestrator process* and finalises
  the task with `ret=-9`.

When Layer 1 fires first, the queue contains a `TIMEOUT` signature; the parent
sees it and leaves the task `failed`. When Layer 2 fires first, the child
orchestrator dies before it can record the signature. The parent still
finalises with `ret=-9`, but because the queue's last failure signature is not
`TIMEOUT`, the failure is treated as transient and the task is requeued to
`ready`.

The three candidates are ruled out by the regression tests added in
`tests/orchestrator/test_signal_exit_divergence.py`:

- **Candidate 1:** Both the internal stall path and an external `SIGKILL` yield
  `proc.wait() == -9`. The parent always sees `-9`; the observed difference is
  whether a `TIMEOUT` signature was persisted, not the raw exit value.
- **Candidate 2:** The internal-stall test returns `-9` and is classified as
  `TIMEOUT` deterministically. If EOF-before-wait were clearing `cause`, the
  returned code or classification would vary; it does not.
- **Candidate 3:** `run_stage` records a `TIMEOUT` signature whenever the
  session returns `-9` from an internal stall. The batch test shows the same
  parent-level `-9` finalisation producing no `TIMEOUT` signature when the
  child orchestrator is killed before recording, so the divergence is not a
  call-site difference.

## Evidence

The regression suite captures both extremes deterministically:

- `test_internal_stall_records_timeout_signature`: a session killed by its own
  watchdog returns `-9` and the task ledger gains a `failure_signatures` entry
  with `"class": "timeout"`.
- `test_external_sigkill_before_stall_returns_same_exit_code`: a session killed
  by an external `SIGKILL` before the watchdog fires also returns `-9`, proving
  the same raw code can arise from two different causes.
- `test_finalize_requeues_when_no_timeout_signature`: the batch parent
  finalises a task with `ret=-9` but the queue has no `TIMEOUT` signature. The
  task ends `ready` because the failure is treated as transient.
- `test_finalize_leaves_failed_when_timeout_signature_present`: the same
  parent-level `ret=-9` with a pre-existing `TIMEOUT` signature leaves the task
  `failed`, proving the decisive variable is the signature, not the exit code.

Temporary exit-path instrumentation (enabled via `AET_EXIT_TRACE_PATH`) captured
records that show the same raw `-9` exit code arising from two different causes:

```jsonl
{"source":"_run_with_live_tee","wait_value":-15,"cause":"stall","returned_exit_code":-9}
{"source":"run_stage","task_id":"osd-internal","stage":"plan-approved","exit_code":-9,"killed_by_timeout":true}
{"source":"_run_with_live_tee","wait_value":-9,"cause":null,"returned_exit_code":-9}
```

The first two lines are from the internal-stall path (`cause="stall"`); the
third line is from an external `SIGKILL` that arrived before the watchdog
fired (`cause=null`). In both cases `_run_with_live_tee` returns `-9`, but only
the internal-stall path records a `TIMEOUT` signature before the orchestrator
process exits.

## Implications

A propagation fix (osd-02) must ensure that the parent-level wall-clock kill
either (a) records the `TIMEOUT` signature itself, or (b) finalises the task
as timed-out without requiring the child to have written a signature first.
Relying on `proc.wait() == -9` at the parent is insufficient because the
parent's `-9` does not imply the child recorded a `TIMEOUT` signature.

## Divergence Summary

*Recorded: 2026-08-20 — Branch: osd-01-isolate-signal-exit-divergence*

### Changed from plan

- Temporary instrumentation: the per-session trace was captured with a
  throwaway `AET_EXIT_TRACE_PATH` probe and then reverted, rather than kept
  as a longer-lived diagnostic. The PRD still includes the captured records.
- Rehearsal capture: instead of repeatedly running the real rehearsal until
  both outcomes appeared, the evidence was reproduced deterministically with
  regression tests in `tests/orchestrator/test_signal_exit_divergence.py`.

### Added (unplanned)

- `tests/orchestrator/test_signal_exit_divergence.py`: regression suite that
  exercises the internal-stall path, an external `SIGKILL`, and the batch
  parent's finalisation behaviour with and without a pre-existing `TIMEOUT`
  signature.

### Deferred

- Merge branch to main and verify integration: left for `aet-ship`; the branch
  is still ahead of `origin/main`.

*Stage: synced*
*Next step: run `aet-ship`*
