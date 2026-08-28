# Bug Report: `aet mine-learnings` cannot see a requeue loop, because it reads prose

## Metadata

- **Reported:** 2026-08-28
- **Severity:** medium (the loop signal exists and is never read)
- **Status:** fixed 2026-08-28

## Symptoms

The telemetry learning report for the session containing the `pub-03`
22-attempt loop:

```
Runs scanned: 344
Reports scanned: 0
- Repeated loops: 0
```

`aet retro` then emitted "No findings" in both buckets for the most expensive
session in that project's history, while the task record counted the loop
exactly: 21 `failed → ready` transitions.

## Reproduction Steps

1. Produce a run whose task requeues repeatedly.
2. Write no narrative markdown report for that run.
3. Run `aet mine-learnings`.

Observed: `Repeated loops: 0`.

## Root Cause

`repeated_loops` has exactly one source: `mine_narrative`
(`cli/mine_learnings.py:69-76`) keyword-matching `retry`, `loop`, `attempt`
against markdown, called only from the report walk
(`cli/mine_learnings.py:262-267`). With no markdown report in the run directory,
`reports_scanned` is 0 and the bucket cannot be non-zero.

The structured records `mine_archive` does read carry the signal. Each `stage`
record has `task_id`, `stage` and `exit_code`
(`cli/mine_learnings.py:226-238`), and a loop is a repeated failure of the same
`(task_id, stage)` pair inside one run.

## Consequences

The one pattern that most warrants an automatic stop is detectable only from a
report a human wrote, and the miner's own summary reports zero rather than
unknown. A caller cannot distinguish "no loops occurred" from "no prose was
scanned".

## Fix

`repeated_loops` is now derived from the `stage` records the walk already reads,
counting repeated failures per `(run, task_id, stage)` in the same shape as the
existing `repeated_test_invocations` line. The narrative bucket is additive, not
replaced: it catches loops the telemetry does not model.

The key includes the run directory, so a stage that fails once in each of two
runs is not reported as a loop. A loop is repetition inside one attempt
sequence; a retry in the next shift is an ordinary retry.

Reading state transitions from the task records is the more direct measurement —
they count the loop exactly — but it gives the miner a second data source in the
git-refs ledger, which it does not currently touch. That remains open and is not
needed to close this defect.

The reporting concern that `Reports scanned: 0` can read as evidence of absence
is now moot for this bucket, which has an always-scanned structured source. It
still applies to the buckets that only exist in narrative form.
