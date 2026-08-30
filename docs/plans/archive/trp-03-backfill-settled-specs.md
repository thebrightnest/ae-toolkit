---
id: trp-03-backfill-settled-specs
size: M
work_class: critical
blocked_by: []
pipeline: standard
security_review: required
security_review_reason: Mutates the append-only settled history log, the durable record of every merged task.
docs_sync: required
docs_sync_reason: Completes R-5's unrun migration and changes what a settled record is guaranteed to carry.
---

# Plan: Backfill the Spec Into Settled Records Before Anything Is Deleted

## Context

- PRD: `docs/prds/the-record-is-the-plan-prd.md` (R-6)
- ADR-058 (migration populates before it removes); ADR-059 (absence is not a fact)

Measured: **368 of 368** settled records in `.agents/work-history.jsonl` carry a
`plan_file` that does not exist on disk. Only **8** carry
`spec.frontmatter.size`. For the other 360, the 264 files in
`docs/plans/archive/` are the only surviving source of declared size.

`aet state backfill-specs` already exists and `spec_backfill.backfill_specs`
already takes a generic `list[dict]` — but the CLI points it at the queue only.
Settled records were never covered.

This plan strictly precedes `trp-05`. Deleting the archive first would destroy
declared-size history permanently, which is precisely what ADR-058 forbids.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] R-5's migration never ran; completing it is enhancement, not a defect fix

## Task List

1. **Point `backfill-specs` at `work-history.jsonl`** via an explicit flag,
   reusing `backfill_specs` unchanged — it already accepts any record list — M
   (traces: R-6)
2. **Resolve legacy plans from `docs/plans/archive/` as well as a git revision**,
   since that directory is where the 360 pre-R-19 plans actually live — M
   (traces: R-6)
3. **Report coverage and name every unrecoverable record by id.** A record whose
   plan is in no reachable source is reported, never silently skipped (ADR-059) —
   S (traces: R-6)
4. **Preserve append-only semantics**: the rewrite is atomic and changes only the
   `spec` key on existing records; no record is added, removed, or reordered — M
   (traces: R-6)
5. **Verify against the measured baseline**: records carrying
   `spec.frontmatter.size` rises from 8, and the unrecoverable count is stated —
   S (traces: R-6)
6. Merge branch to main and verify integration — S

## Floor Check

- [ ] Expected diff is below the calibrated floor threshold
- [ ] The change is limited to one subsystem and maintains no architectural invariant
- [ ] `Files to Modify` substantially overlaps a sibling this plan is linearly ordered against
- [ ] This is docs-only and its sole consumer is a single sibling

Zero boxes. It maintains the append-only invariant on the settled log and is the
ADR-058 precondition for `trp-05`.

## Rejected Alternatives

- **Delete the archive and accept the loss** — rejected: ADR-058 exists to
  prevent exactly this, and declared-vs-delivered size is ADR-046's calibration
  input.
- **Dual-read the archive from `metrics` forever** — rejected: the second read
  path R-5 was written to remove.
- **Backfill only the 8 post-R-19 records** — rejected: they already carry a
  spec; the 360 without one are the entire problem.
- **Reconstruct specs for unrecoverable records from the record's own fields** —
  rejected: inventing a spec makes an absence look like a fact (ADR-059).

## Files to Modify

- `src/aet/cli/aet_state.py`
- `src/aet/spec_backfill.py`
- `tests/state/test_spec_backfill_cli.py`
- `tests/state/`

## Validation Steps

- [ ] Lint passes
- [ ] Tests pass
- [ ] R-trace coverage: R-6 covered by tasks 1-5
- [ ] Dry-run reports coverage without mutating the log
- [ ] Applied run raises the spec-carrying count from its measured baseline of 8
- [ ] Every unrecoverable record is named by id in the report
- [ ] Record count in `work-history.jsonl` is unchanged before and after
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

The history log is rewritten atomically; restore from the pre-run copy. No
consumer requires the backfilled spec until `trp-04` lands, so a revert is safe.

## Pipeline

`standard`.

---

_Stage: plan-approved_
