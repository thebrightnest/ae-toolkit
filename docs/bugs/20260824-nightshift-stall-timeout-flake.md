# `test_stall_killed_and_classified_timeout` — filed, not reproduced

**Date:** 2026-08-24
**Status:** open — not currently reproducible
**Source:** `docs/audits/2026-08-24-open-items.md` item OI-17

## Symptom

`tests/orchestrator/test_nightshift_rehearsal.py::TestNightShiftExitGateRehearsal::test_stall_killed_and_classified_timeout`
was measured failing at roughly **13–27%** across two arms of a 30-run
comparison in August 2026. The assertion that failed is the failure class: the
test requires the last signature on `nightshift-stall` to read `timeout`.

No bug document existed for it, so the measurement lived only in a review and
the test stayed in the suite unexplained. That is what this record fixes; the
flake itself is unresolved.

## What the current measurement says

On 2026-08-24, on the machine that produced the original figure:

| Arm | Runs | Failures |
|---|---|---|
| Single test, isolation | 25 | 0 |
| Single test, 4-way parallel | 12 | 0 |
| Full `make validate` (xdist `-n auto`) | 8 | 0 |

The test also passed in the 2026-08-24 full-suite run recorded in the register.
Nothing here contradicts the August figure — a 13–27% rate would very likely
have shown in 37 runs, so either the cause was removed by a change since, or it
depends on a condition none of these arms reproduce.

`6bc5367f` (osd-02) is the last commit to touch the test. It made a signal exit
classify as a timeout, which is the assertion's own subject, so it is the
strongest candidate for having fixed the flake as a side effect without the
measurement being repeated.

## How the assertion is supposed to hold

The chain has three processes and the class is decided in the middle one.

1. The fake `claude` stub self-SIGKILLs for the stall fixture
   (`tests/orchestrator/test_nightshift_rehearsal.py:154-156`), after emitting
   its usage envelope.
2. The `run-one` child classifies that stage session. `killed_by_timeout` is
   `exit_code < 0` (`src/aet/cli/orchestrator.py:809`, `:1468`, `:1602`), so a
   signal exit becomes `FailureClass.TIMEOUT` and the signature is written to
   the task record.
3. The batch parent reads the record. `_finalize_task` treats the task as timed
   out when the last signature says `timeout` **or** the child's own return code
   is negative (`:2873`), and appends the authoritative timeout signature when
   only the second holds (`:2876`).

## Candidate mechanisms, none confirmed

- **A signal exit surfacing as `128 + n`.** Every branch above tests
  `exit_code < 0`. A shell anywhere between the orchestrator and the stub turns
  `-9` into `137`, and `137 < 0` is false: the class would fall through to
  `flaky`, which is exactly the observed failure. This is the mechanism osd-02
  addressed, and the one to re-examine first if it recurs.
- **The record read racing the child's write.** `_cleanup_task` calls
  `backend.load()` immediately after `proc.poll()` returns
  (`:3157-3165`). The signature is written by the child to `refs/aet/*` before
  it exits, so a reaped child should be fully visible — but the two are separate
  processes and the ordering is not asserted anywhere.
- **`shutdown` winning over `timeout`.** `classify` returns `CANCELED` before it
  considers a timeout (`src/aet/failure.py`). `_shutdown_requested` is a
  per-process global set only by a signal handler, and the batch parent does not
  signal its children at `task_timeout=999`, so this should not reach the stall
  task. It is listed because it is the only other way the assertion's class can
  change.

## If it recurs

Reproduce with the class-scoped rehearsal, not the single test: the fixture's
three tasks run concurrently at `max_jobs=3`, and the contention between them is
part of the condition. Capture the *whole* signature list rather than the last
entry, plus the `run-one` child's exit code, which no current assertion records.

## Why it is not being fixed here

The assertion is correct as written and the behaviour it asserts is the one the
code intends. With no reproduction there is nothing to fix without guessing, and
a speculative change to the classification path would be untestable against the
failure it claims to address. The measurement above is the deliverable.
