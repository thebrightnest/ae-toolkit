# Bug Report: `aet report` never reads run summaries, so every run figure is zero

## Metadata

- **Reported:** 2026-08-27
- **Severity:** medium
- **Status:** open

## Symptoms

After two runs, seven merged tasks and roughly $92 of model spend, an
archive-wide report:

```
Runs: 0
Runs observed: 4
Tasks spawned: 0
Succeeded: 0
Failed: 0
Wall-clock time: 0.0s
```

`Runs observed: 4` alongside `Runs: 0` is the tell: one number is derived from
records the scan found, the others from records it never saw.

## Reproduction Steps

1. Complete any orchestrator run so the archive holds a run directory.
2. Run `aet report` with no `--task-log` argument.

Observed: every summary-derived figure is zero while `Runs observed` counts the
run. Expected: the run's spawned/succeeded/failed counts and wall-clock time.

Passing `--task-log <file>.jsonl` does not reproduce it — that path reads the
named file directly.

## Root Cause

The archive holds two record shapes, and the archive-wide reader knows one.

- Stage records are appended per task to `{task-id}.jsonl`
  (`TelemetryLogger.append_record`, `src/aet/telemetry.py:213`).
- The run summary is written once per run to `last-run.json`
  (`TelemetryLogger.write_last_run`, `src/aet/telemetry.py:221-229`).

`report()` assembles its records through `_scan_records`, which globs
`root.rglob("*.jsonl")` (`src/aet/telemetry.py:704`). `last-run.json` is not
matched, so `summaries` is empty for every archive-wide report and
`_format_report` sums an empty list into `Runs`, `Tasks spawned`, `Succeeded`,
`Failed`, and `Wall-clock time`. `runs_observed` is non-zero because it counts
distinct `run_id` values on the stage records, which are `.jsonl`.

The writer matches the documented archive shape:
`skills/aet-work/references/telemetry-log-schema.md:59` states that the run
summary is stored as `last-run.json`. Two other readers honour it —
`src/aet/panel/serve.py:39` and `src/aet/cli/mine_learnings.py:258`. `report()`
is the single non-conforming reader.

## Consequences

- No batch's cost or duration is recoverable from the summary, though
  `run_summary_record` carries `total_tokens` and `total_cost_usd`
  (`src/aet/telemetry.py:325-364`).
- Per-stage cost survives only in stage records and in transient notification
  output, so any statement about what a run cost is reconstructed by hand.

## Why It Survived

No test builds an archive through `TelemetryLogger` and asserts `report()` over
it. The existing coverage exercises the single-file path, which reads the file it
is handed and therefore cannot observe the glob.

## Fix Direction

Include `last-run.json` in the archive scan alongside the `.jsonl` glob.

Rejected: also appending the run summary to a `.jsonl`. That duplicates the
record, lets two copies diverge, and complicates the panel's existing handling of
`run_summary`-only runs (`src/aet/panel/index.html:427`).

The regression test is the durable half of the fix: build a run directory with
`TelemetryLogger`, write a summary, and assert `report()` returns non-zero
counts.
