---
id: eop-07-reports-distinguish-zero-from-unscanned
size: S
work_class: normal
blocked_by: []
pipeline: standard
security_review: skipped
security_review_reason: Changes report rendering only; reads the same records with no new source or sink.
docs_sync: skipped
docs_sync_reason: No contract changes; the reports' inputs and commands are unchanged.
---

# Plan: A Count of Zero and an Unscanned Bucket Do Not Render Identically

## Context

PRD: docs/prds/evidence-over-proxy-prd.md
Decision: ADR-072 (A Proxy Is Not Evidence), decision 6 — absence and zero are
different results.

The 2026-08-28 retro stated this as a general rule after a $23.77 runaway loop
produced a retro reporting nothing. The counting half was fixed:
`mine_learnings` now derives `repeated_loops` from stage records
(`src/aet/cli/mine_learnings.py`). The rendering half was not.

`format_report` prints every bucket as a bare integer, and
the `## Ranked by Frequency` section ranks ten zero-count buckets as `1.` each.
The only signal that nothing was scanned is the three report-level counters,
which no bucket reflects. Run against an empty archive, the `Recurring Patterns`
and `Ranked by Frequency` sections are byte-identical to a fully-scanned archive
that matched nothing.

`aet retro` has the same shape: it renders `- No findings.`
(`src/aet/cli/retro.py`) both when there were no telemetry records and
when there were records that `categorize_records` dropped for
lacking usable finding text. The second case is a parsing failure reported as an
absence of findings.

A report of zeros is what an operator reads to decide nothing happened. When the
same output means "nothing occurred" and "nothing was looked at", it cannot
support that decision — and the one occasion it was read that way, it was wrong.

## Intake Triage

- [x] Demonstrable, recorded in
      `content/backlog/debt-report-cannot-distinguish-zero-from-unscanned.md`
- [x] Routed here because it is the same rule as the rest of this PRD applied to
      report output, and the retro that found it stated it as a general rule

## Task List

1. Carry a scanned/unscanned distinction per bucket rather than per report, so a
   bucket can report that it had no input separately from having found nothing —
   S (traces: R-8)
2. Render the two cases differently in `format_report`, and stop presenting a
   field of zero-count ties as a field of firsts in the frequency ranking — S
   (traces: R-8)
3. Distinguish, in `aet retro`, records that were absent from records that were
   dropped for lacking usable finding text, and report the drop count rather
   than folding it into "no findings" — S (traces: R-8)
4. Tests rendering both commands against an empty archive and against a scanned
   archive that matched nothing, asserting the outputs differ — S (traces: R-8)
5. Merge branch to main and verify integration — S

### Floor Check

- [x] The change is limited to one subsystem and maintains no architectural invariant
- [ ] Expected diff is below the calibrated floor threshold
- [ ] `Files to Modify` substantially overlaps a sibling it is ordered against
- [ ] This is docs-only and its sole consumer is a single sibling

One box checked: rendering only, no runtime invariant. It is above the floor
because it spans two commands and needs the paired fixtures to prove the
distinction.

## Rejected Alternatives

- **Print the three existing counters more prominently and stop** — rejected:
  they are per-report, so a partially-scanned archive still renders every bucket
  as though it had input.
- **Suppress zero-count buckets entirely** — rejected: a bucket that was scanned
  and matched nothing is a real result, and hiding it makes the report unable to
  say so.
- **Emit machine-readable output and leave rendering to the caller** — rejected:
  new surface, and the defect is in what a human reads.

## Files to Modify

- `src/aet/cli/mine_learnings.py`
- `src/aet/cli/retro.py`
- `tests/cli/test_mine_learnings.py`
- `tests/cli/test_retro.py`

## Validation Steps

- [ ] Lint passes
- [ ] Tests pass
- [ ] R-trace coverage: every in-scope R-id is covered by ≥ 1 task or explicitly deferred with a reason; no task cites an unknown R-id
- [ ] `aet mine-learnings` against an empty archive and against a scanned archive
      with no matches produce different output
- [ ] No ranking section presents more than one entry at the same rank number
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the commit. Both reports return to rendering a bare integer per bucket,
which is how every report read so far was produced.

## Pipeline

`standard` — rendering change to two operator-facing reports.
