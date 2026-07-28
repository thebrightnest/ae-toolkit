---
id: tap-05-test-run-provenance
size: M
blocked_by: []
pipeline: standard
status: queued
security_review: skipped
security_review_reason: adds one enum-valued field to a local telemetry record and filters read-side aggregates by it; no new input, auth, network, or write surface beyond the existing archive
docs_sync: required
docs_sync_reason: ADR-051 defines the provenance contract; the telemetry schema in docs/telemetry-guide.md and CONTEXT.md's Test Run term must document `source` and the observed/claimed split
---

# Plan: `test_run` Provenance and Provenance-Correct Aggregates

## Context

- PRD: `docs/prds/telemetry-adapter-parity-prd.md` (R-7, R-8)
- ADR: `docs/adr/051-test-run-provenance.md` (this plan delivers it)
- Measured motivation: `reports/2026-07-25-aet-performance-observability-review.md` — 313
  observed and 112 claimed records over the three AET projects (410 distinct after dedup on
  `(run_id, task_id, stage, scope, test_command)`). The observed pass rate is 80%; the mixed
  corpus reads 85%. 74 groups hold a claimed record with no observed twin.
- Verified current behaviour (2026-07-26): two emitters write one record type.
  `_emit_wire_test_runs` (`src/aet/cli/orchestrator.py:603`) writes real timestamps and exit
  codes and never test counts; `_emit_test_run_from_verdict` (`:711`) passes
  `start_time=None, end_time=None, exit_code=0` **literally**, so `duration_seconds` is null and
  `result` is `"success"` by construction (`telemetry.test_run_record`,
  `src/aet/telemetry.py:328-373`), and it fires only on a passing verdict.
- Verified consumer behaviour (2026-07-26): the panel's `testsAgg`
  (`src/aet/panel/index.html:292,415-417`) sums `tests_total`/`tests_passed`/`tests_failed`, so
  it already reads **claimed records only** — by accident of which records carry counts, not by
  declaration. `desk._telemetry_signals` (`src/aet/cli/desk.py:170`) takes the max `tests_failed`
  the same way. The panel's timeline and "Test runs" list (`index.html:706,883-891`) render both
  provenances interleaved with no marker. `mine_learnings` (`src/aet/cli/mine_learnings.py:239`)
  counts `full_suite_runs`/`impact_runs` over both.
- After `tap-01`, `track_record` reads no `test_run` records at all.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Locked design

- **`source` is written by the emitter, never inferred at read time** (ADR-051 decision 1).
  `"wire"` for observed, `"verdict"` for claimed. `test_run_record` takes it as a required
  argument so a new emission site cannot omit it.
- **Each aggregate declares its provenance** (ADR-051 decisions 2 and 4). Timing and pass-rate
  aggregates read `source == "wire"`. Count aggregates read `source == "verdict"` — the only
  records carrying counts — and say so in the label rather than relying on the accident that
  observed records contribute `0`.
- **Individually rendered records are labeled.** The panel's timeline and test-run list mark each
  row observed or claimed. Filtering without labeling would trade one unexplained number for
  another.
- **Claimed records are kept** (ADR-051 decision 3). They carry counts nothing else does.
- **Pre-change records are provenance-unknown and are not backfilled** (ADR-051 decision 5).
  They are excluded from both provenance-filtered aggregates and shown as unknown. Field-signature
  inference is correct on today's data by coincidence and would silently rot.
- **`_emit_test_run_from_verdict` stops hardcoding `exit_code=0`.** With `source` present the
  record is honest about being a report; the literal zero is redundant and false. It passes
  `None`, which `test_run_record` already maps to `result: "unknown"` — its documented null
  contract, consistent with ADR-031.
- **The orphan signal is not implemented here.** ADR-051 decision 6 notes that a claimed record
  without an observed twin becomes meaningful once both readers work; surfacing it is deliberately
  left out until `tap-04` lands, so this plan stays independent of the reader work.

## Rejected Alternatives

- **Stop emitting verdict-derived records** — rejected (ADR-051): they carry the only test counts
  in the archive, and deleting them hides the orphan signal with the noise.
- **Infer provenance at read time from field signatures** — rejected as the forward contract
  (ADR-051): right today by coincidence, silently wrong the first time either emitter's fields
  change. It stays the only option for legacy records, which is why those are labeled unknown.
- **A separate `test_claim` record type** — rejected (ADR-051): the two populations are joined on
  a shared identity to find orphans, and a second type makes that the awkward query.
- **Only fix `exit_code=0` without adding `source`** — rejected: it corrects the most obviously
  false field while leaving the record indistinguishable in kind.

## Task List

- [x] 1 · [x] 2 · [x] 3 · [x] 4 · [x] 5 · [x] 6 — task 7 (merge) belongs to `aet-ship`.

1. Add a required `source` argument to `telemetry.test_run_record` and set it at both emission
   sites; stop passing `exit_code=0` from the verdict emitter — S (traces: R-7)
2. Split the panel's aggregates by provenance: timing/pass-rate over observed, counts over
   claimed, with labels stating which; mark provenance on the timeline and test-run list rows —
   M (traces: R-8)
3. Declare provenance in `desk._telemetry_signals`' `tests_failed` read and its docstring —
   S (traces: R-8)
4. Filter `mine_learnings`' `full_suite_runs`/`impact_runs` counting to observed records and note
   the change in its output — S (traces: R-8)
5. Document `source` and the observed/claimed split in `docs/telemetry-guide.md`; confirm
   CONTEXT.md's **Test Run** term matches — S (traces: R-7, R-8)
6. Tests (see Validation Steps) — M (traces: R-7, R-8)
7. Merge branch to main and verify integration — S

**Size definitions:** S ≤ 2 hr / ≤ 150 lines · M ≤ 1 day / ≤ 600 lines.

### Floor Check

- [x] Stands alone: the field and its consumers ship together — a `source` field no aggregate
  reads is dead weight, and a filtered aggregate with no field to filter on is impossible. No
  dependency on the reader or detector work.

## Files to Modify

- `src/aet/telemetry.py`
- `src/aet/cli/orchestrator.py`
- `src/aet/panel/index.html`
- `src/aet/cli/desk.py`
- `src/aet/cli/mine_learnings.py`
- `tests/telemetry/test_telemetry.py`
- `tests/orchestrator/test_orchestrator.py`
- `tests/state/test_desk_view.py`
- `tests/telemetry/test_mine_learnings.py`
- `tests/panel/test_panel_test_run_aggregates.py` (new)
- `docs/telemetry-guide.md`

Also touched during implementation (beyond the planned list):

- `skills/aet-work/references/telemetry-log-schema.md` — the `test_run` schema table lives here,
  so `source` and the provenance contract are documented alongside the field list
- `CONTEXT.md` — the **Test Run** term still described the claimed record as `result: success`
  "true by construction"; corrected to the null `exit_code` / `result: "unknown"` this plan ships
- `reports/2026-07-25-aet-performance-observability-review.md` — the published 80%/85% figures
- `tests/telemetry/test_aet_retro.py`, `tests/track_record/test_track_record_metrics.py` —
  fixtures that construct `test_run` records or assert `mine-learnings` report labels

## Validation Steps

- [x] `make validate` passes (1316 passed, 2026-07-28 — re-run at QA after the `Th`
      prop-spreading fix and its regression test)
- [x] Coverage, with the panel aggregates in `tests/panel/test_panel_test_run_aggregates.py`:
  - `test_wire_emitter_writes_source_wire` (unit)
  - `test_verdict_emitter_writes_source_verdict` (unit)
  - `test_verdict_emitter_no_longer_hardcodes_exit_code_zero` (unit) — record reads
    `result: "unknown"`, not `"success"`
  - `test_test_run_record_requires_source` (unit) — omitting it is an error, not a default
  - `test_timing_aggregate_ignores_claimed_records` (unit) — adding claimed records does not move
    the figure
  - `test_count_aggregate_ignores_observed_records` (unit) — adding observed records does not move
    the figure
  - `test_legacy_record_without_source_excluded_from_both_aggregates` (unit)
  - `test_legacy_record_rendered_as_provenance_unknown` (panel)
  - `test_timeline_rows_labeled_with_provenance` (panel)
  - `test_mine_learnings_scope_counts_observed_only` (unit)
- [x] R-trace coverage: R-7 by tasks 1, 5, 6; R-8 by tasks 2, 3, 4, 5, 6; no unknown R-ids
- [x] For the new aggregate-filtering logic in `index.html`, tests above name the coverage —
      the helper block is extracted verbatim from `index.html` and executed under node, so the
      assertions run against the code the browser runs
- [x] Over the existing archive: re-measured 2026-07-28 — 495 `test_run` records, 360 observed
      (80% pass) and 135 claimed (100% pass), blending to 85%. The report's figures reproduce
      exactly and the correction is recorded in
      `reports/2026-07-25-aet-performance-observability-review.md`. **Amended:** all 495 predate
      the change and carry no `source`, so per ADR-051 decision 5 they are provenance-unknown and
      excluded — the filtered surfaces read `—` over historical data rather than 80%, and
      populate from records written after this change. The 80% is recoverable only by field
      signature, which is the inference the decision refuses to make the forward contract.
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit; aggregates return to reading the blended corpus. Records written with
`source` remain valid — the telemetry schema is additive and readers tolerate unknown keys — so
a reverted build reads them as it read pre-change records, and re-applying the change does not
need a migration.

---

*Stage: qa-complete*
*Next step: run `aet-review`*
