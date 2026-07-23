---
id: psr-03-size-calibration-report
size: M
blocked_by:
  - psr-02-record-delivered-size
pipeline: standard
status: queued
security_review: skipped
security_review_reason: reads local history records and reuses the git helper introduced and security-reviewed in psr-02; adds no new external surface
docs_sync: required
docs_sync_reason: adds a user-facing report surface and a backfill command that operators will need documented
---

# Plan: Backfill delivered size and report calibration

## Context

- PRD: `docs/prds/plan-sizing-recalibration-prd.md` (R-9, R-10)
- Blocked by: `psr-02-record-delivered-size` — this plan consumes the record
  schema and the `delivered_size()` helper that plan defines
- Related: ADR-015 (telemetry informs guardrails, local-first)

`psr-02` makes new closures record what they delivered. On its own that means the
loop starts empty and stays uninformative for months. This plan backfills from the
289 existing history records and exposes the aggregate, so the next threshold
argument is settled by the recorded distribution rather than re-argued.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [ ] If a reproducible defect was described, redirected to `aet-bug-report`

## Locked design

- **Backfill is idempotent and non-destructive.** Re-running it must not
  duplicate or overwrite an already-measured record. Records are matched by task
  id; a record that already carries a measurement is skipped.
- **Unresolvable records are reported, not silently dropped.** Older records may
  lack a usable `merge_commit`. The backfill prints how many records were
  measured, skipped, and unresolvable, with the reason breakdown. Silent
  under-reporting would corrupt the very distribution the loop exists to produce.
- **The expected backfill yield is known and pinned.** Measured on 2026-07-23:
  289 history records, 267 (92%) carrying a `merge_commit` and therefore
  measurable, 22 (8%) not. A backfill run that resolves materially fewer than 267
  indicates a regression in the measurement path, not a property of the data.
- **Commands are noun-scoped with nested verbs**, per ADR-039: `aet size report`
  and `aet size backfill`. `size` is a noun-scoped group, not a bare command.
- **Aggregation reuses the existing settled-task iteration.**
  `src/aet/metrics.py::iter_settled_tasks` already walks the settled history and
  `_finalize_bucket` already shapes aggregates. Extend that path rather than
  adding a second history reader.
- **The report answers one question:** for each declared label, what did plans
  actually deliver — n, median, p90 — and what share exceeded the label's band.
  That is the exact table the PRD used to justify the recalibration, so the
  recalibration becomes re-checkable against fresh data.
- **The report states its own sample size and caveats.** A distribution over a
  handful of tasks must not be presented as authoritative.

## Task List

1. Add a backfill routine that walks `.agents/work-history.jsonl`, measures each
   settled record carrying a resolvable `merge_commit` via `psr-02`'s
   `delivered_size()`, and writes the result back idempotently — M
   (traces: R-10)
2. Report backfill outcomes as measured / skipped-already-present /
   unresolvable, with a reason breakdown for the unresolvable set — S
   (traces: R-10)
3. Extend `src/aet/metrics.py` to aggregate **Delivered Size** by **Declared
   Size**, producing n, median, p90, and the share exceeding the band — M
   (traces: R-9)
4. Expose `aet size report` and `aet size backfill` as a noun-scoped command
   group per ADR-039 — S (traces: R-9, R-10)
5. Add tests for the aggregation maths, the idempotent backfill, and the
   unresolvable-record path — M (traces: R-9, R-10)
6. Document the report and backfill in the appropriate operator-facing docs — S
   (traces: R-9, R-10)
7. Merge branch to main and verify integration — S

**Size definitions (as proposed by this PRD, dogfooded here):**

- **S**: ≤ 2 hr human time / ≤ 150 expected diff lines
- **M**: ≤ 1 day human time / ≤ 600 expected diff lines
- **L**: > 600 lines — re-evaluate against the full model; justify above 1500

Expected diff ≈ 400–550 lines across the metrics module, a backfill routine, two
CLI surfaces, tests, and docs. **M** under the proposed bands.

### Floor Check

- [x] Stands alone: after this lands, the recorded data is queryable and seeded
      with history, which is what makes the loop usable rather than theoretical
- [x] Diff materially exceeds branch/PR/review overhead
- [x] Correctly separated from `psr-02`: that plan carries the closure-path risk,
      this one carries read-side aggregation over an established schema

## Rejected Alternatives

- **Skip backfill and wait for organic data** — rejected: the loop would produce
  nothing actionable for months, and 289 usable historical records already exist.
- **Recompute the distribution from commit-subject matching** — rejected: that is
  the approximate method used for the PRD evidence. Backfilling through
  `merge_commit` is exact and reuses the reviewed helper.
- **Auto-adjust the bands from the recorded distribution** — rejected: PRD Open
  Question 1 flags the drift risk, where thresholds chase whatever was last
  shipped. The report informs a human decision; it does not move the bands.
- **Add a new aggregate history reader** — rejected: `iter_settled_tasks` already
  exists; a second reader would drift from it.
- **Fold this into `psr-02`** — rejected: it would put closure-path runtime risk
  and read-side reporting in one review, and `psr-02` is independently valuable
  without it.

## Files to Modify

- `src/aet/metrics.py`
- `src/aet/cli/` — backfill and report subcommands
- `tests/` — metrics aggregation and backfill coverage (new test module)
- Operator-facing documentation for the new commands

## Validation Steps

- [ ] Lint passes
- [ ] Tests pass
- [ ] `make validate` passes
- [ ] New source coverage: the new test module names cases for (a) median and p90
      aggregation against a fixture set with a known answer, (b) the
      share-exceeding-band calculation, (c) backfill run twice producing identical
      records, (d) a record with no `merge_commit` counted as unresolvable with a
      reason, and (e) a record already measured being skipped rather than
      recomputed
- [ ] Test types: aggregation and backfill accounting are unit tests over fixture
      history records; the CLI surfaces get an integration test invoking them
      end-to-end against a temporary project. No API boundary surface is touched.
- [ ] Running backfill twice over the same history is a no-op on the second run
- [ ] The unresolvable count is printed, never silently zero
- [ ] Backfill over the current corpus resolves ~267 of 289 records; a materially
      lower yield fails the check rather than being reported as success
- [ ] The report states its sample size alongside the distribution
- [ ] Command names follow ADR-039: `aet size report` / `aet size backfill`,
      registered as a noun-scoped group
- [ ] R-trace coverage: R-9 by tasks 3,4,5,6; R-10 by tasks 1,2,4,5,6.
      R-7 and R-8 are carried by `psr-02`; R-1 … R-6 and R-11 … R-17 by `psr-01`
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the commit. Backfilled fields remain on the history records but are inert
once the readers are gone, and the records stay schema-valid because the fields
are additive. No migration is required in either direction.

## Pipeline

`standard`.

---

*Stage: plan-approved*
*Next step: run `aet-work`*
