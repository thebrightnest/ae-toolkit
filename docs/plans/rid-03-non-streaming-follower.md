---
id: rid-03-non-streaming-follower
size: M
work_class: critical
blocked_by:
  - rid-01-detached-only-execution
pipeline: standard
status: queued
security_review: required
security_review_reason: Changes process-wait and exit-code propagation, including a non-terminating loop fix.
docs_sync: required
docs_sync_reason: Changes the observable behavior of aet run, aet run-one, and --follow.
---

# Plan: Non-Streaming Terminal Follower

## Context

PRD: `docs/prds/run-invocation-determinism-prd.md` (R-2, R-2b, R-2c, R-5).
Glossary: **Follower**, **Detached Run**, **Run Id** in CONTEXT.md.

`_follow_run` (`main.py:152-196`) already waits correctly — it terminates on both pid death
and the `returncode` file. Its defect is that it echoes: it replays the whole log from byte
zero (`main.py:163-166`) and then relays every subsequent line (`main.py:184`). This plan
makes the waiter silent and fixes its one non-terminating path. The report *content* is
rid-04; this plan lands the waiter with a minimal placeholder summary.

`run` and `run-one` deliberately differ: `run-one` blocks, batch `run` returns immediately and
is observed later via `--follow`. That difference is carried by which command the operator
invoked, not by a flag an agent selects.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. Extract the wait loop of `_follow_run` into a follower that waits on the two terminal
   conditions and returns the run's exit code **without writing any run output to stdout** —
   remove the byte-zero replay and the per-line echo — M (traces: R-2c)
2. Fix the non-terminating path: when the pid file is absent or unparseable and no
   `returncode` file exists, exit non-zero with a diagnostic instead of looping forever
   (`main.py:181-196`) — S (traces: R-5)
3. Make `aet run-one` spawn detached and then attach the follower, exiting with the run's exit
   code — S (traces: R-2)
4. Keep `aet run` (batch) returning immediately after spawn, printing run id and log path — S
   (traces: R-2b)
5. Add tests covering: `run-one` returns only at terminal state with the run's exit code and
   emits no run output lines; batch `run` returns before completion; `--follow` against both a
   live and an already-completed run; and the missing-pid case terminating non-zero — M
   (traces: R-2, R-2b, R-2c, R-5)
6. Merge branch to main and verify integration — S

## Validation

- `aet run-one <id>` on a run producing thousands of log lines prints no run output lines and
  exits with the run's exit code.
- `aet run` prints a run id and returns while the orchestrator is still alive.
- `aet run --follow <run-id>` on a completed run exits immediately with its stored returncode.
- With `.agents/runs/<id>/pid` deleted and no `returncode`, `aet run --follow <id>` exits
  non-zero within seconds rather than hanging.
- Named tests: `tests/test_orchestrator_daemonize.py` (follower against live and completed
  runs, missing-pid termination), `tests/test_aet_run_dispatch.py` (`run-one` blocks, `run`
  does not).

---

*Stage: implemented*
*Next step: run `aet-qa`*
