---
id: tap-01-factory-metrics-stage-records-only
size: S
blocked_by: []
pipeline: standard
status: queued
security_review: skipped
security_review_reason: read-side analytics only; changes which telemetry record types a retroactive metric reads, adds no input, auth, data, or write surface, and no code path gates on the output (ADR-031, ADR-035 item 4)
docs_sync: required
docs_sync_reason: ADR-035's First-Pass Merge and Rework definitions are refined by ADR-052; CONTEXT.md's Factory Metrics entries must match the counting core
---

# Plan: Factory Metrics Read Stage Records Only

## Context

- PRD: `docs/prds/telemetry-adapter-parity-prd.md` (R-12)
- ADR: `docs/adr/052-first-pass-merge-excludes-test-run-failures.md` (this plan delivers it),
  refining `docs/adr/035-canonical-factory-metric-definitions.md`
- Measured motivation: `reports/2026-07-25-aet-performance-observability-review.md`
- Verified current behaviour (2026-07-26): `track_record.iter_telemetry_task_records`
  (`src/aet/track_record.py:74`) yields `type in ("stage", "test_run")`. Both
  `_has_failed_stage` (`:78`) and `_repeated_stage_count` (`:103`) consume that set;
  `_repeated_stage_count` groups by `_stage_names(record)`, and `test_run` records carry a
  `stage` field (`telemetry.test_run_record`, `src/aet/telemetry.py:363`). Measured over the
  127 tasks with telemetry across `aiskills`/`blueocean`/`manager`: 121 (95%) have rework > 0
  under the current counting versus 25 (20%) counting stage records only — 418 phantom rework
  units — and **1 of 127 tasks (1%)** passes both telemetry clauses versus 93 (73%).
- ADR-035 item 2 already defines rework as "stage telemetry records beyond the first for any
  stage name". The rework half of this plan is a defect fix against that wording; the
  failed-record half is a deliberate narrowing of ADR-035 item 1.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
  — mixed: the rework clause *is* a defect, but it is inseparable from the definitional change
  to the failure clause (same records, same counting core, same re-baseline), so it is planned
  here rather than split into a bug report that would land half the correction.

## Locked design

- **Predicates state their record types; the iterator does not decide.**
  `iter_telemetry_task_records` may keep yielding both types for other callers, but
  `_has_failed_stage` and `_repeated_stage_count` filter to `type == "stage"` explicitly. The
  two clauses stop inheriting a record set by accident (ADR-052).
- Both provenances of `test_run` are excluded. A claimed record cannot fail (ADR-051) and an
  observed failure is an intra-session event.
- `failed → *` re-entry counting (`_failed_reentry_count`, `:117`) is unchanged — it reads task
  history, not telemetry.
- **The re-baseline is an artifact, not a side effect.** A short measurement over the existing
  archive records the before/after first-pass-merge rate and rework distribution, with the delta
  attributed separately to the rework clause and the failed-record clause. It goes in the plan's
  closing notes and in `docs/adr/052-*.md` if the measured figures differ from the ones recorded
  there.
- This lands **before** `tap-02`..`tap-06`. Detection work must not be the change that moves
  these numbers.

## Rejected Alternatives

- **Fix only the rework defect** — rejected (ADR-052): leaves the metric sensitive to detector
  fidelity, so `tap-02` would still publish a false regression.
- **Filter inside `iter_telemetry_task_records`** — rejected: other callers legitimately want
  both types, and hiding the choice in the iterator is what produced this defect.
- **Count only the last `test_run` per stage** — rejected (ADR-052): assumes a loop shape the
  records do not support, and breaks again when detection widens.
- **Move repeated test runs into a new "validation churn" metric now** — rejected as scope: a
  new measure in the same change would make the re-baseline unreadable.

## Task List

1. Filter `_has_failed_stage` and `_repeated_stage_count` to `type == "stage"`, updating their
   docstrings and `is_clean_merge`'s to name the record type they read — S (traces: R-12)
2. Measure and record the re-baseline over the existing telemetry archive: first-pass-merge rate
   and rework distribution before/after, delta attributed per clause — S (traces: R-12)
3. Update `CONTEXT.md` **First-Pass Merge** and **Rework** entries and the ADR-035 cross-reference
   to cite ADR-052 — S (traces: R-12)
4. Tests (see Validation Steps) — S (traces: R-12)
5. Merge branch to main and verify integration — S

**Size definitions:** S ≤ 2 hr / ≤ 150 lines · M ≤ 1 day / ≤ 600 lines.

### Floor Check

- [x] Stands alone: one counting core, one ADR, one re-baseline. Ships and is verifiable without
  any of the detection or adapter work, and is deliberately sequenced ahead of it.

## Files to Modify

- `src/aet/track_record.py`
- `tests/track_record/test_track_record_metrics.py` (new)
- `CONTEXT.md` (Factory Metrics entries — done during scope validation; verify they match code)
- `docs/adr/052-first-pass-merge-excludes-test-run-failures.md` (only if measured re-baseline
  figures differ from those recorded)

## Validation Steps

- [ ] `make validate` passes
- [ ] Coverage, in `tests/track_record/test_track_record_metrics.py`:
  - `test_rework_count_ignores_test_run_records_in_same_stage` (unit) — one stage record plus
    three `test_run` records in one stage yields `0`
  - `test_rework_count_still_counts_repeated_stage_records` (unit)
  - `test_rework_count_still_counts_failed_reentry_transitions` (unit)
  - `test_clean_merge_ignores_failed_test_run_record` (unit)
  - `test_clean_merge_still_fails_on_failed_stage_record` (unit)
  - `test_clean_merge_ignores_failed_test_run_of_either_provenance` (unit)
- [ ] R-trace coverage: R-12 by tasks 1, 2, 3, 4; no unknown R-ids
- [ ] Re-baseline figures recorded in the merge notes, with per-clause attribution
- [ ] `aet desk --eligibility` and `aet metrics` run against the existing archive and report the
      re-baselined figures without error
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit. The metrics return to counting `test_run` records and the reported
first-pass-merge rate returns to ≈1%. Nothing persists the derived numbers — the metrics are
computed at query time (ADR-035 item 5) — so the revert is complete and leaves no stamped state
to unwind.

---

*Stage: tdd-complete*
*Next step: run `aet-implement`*
