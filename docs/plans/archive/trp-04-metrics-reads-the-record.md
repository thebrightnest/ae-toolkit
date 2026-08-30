---
id: trp-04-metrics-reads-the-record
size: S
work_class: normal
blocked_by:
  - trp-03-backfill-settled-specs
pipeline: standard
security_review: skipped
security_review_reason: Read-path change in a reporting command; no auth, data model, API, or dependency surface.
docs_sync: required
docs_sync_reason: Removes the archive read path R-5 documented and changes where declared size comes from.
---

# Plan: `aet metrics` Reads Declared Size From the Record

## Context

- PRD: `docs/prds/the-record-is-the-plan-prd.md` (R-5, R-9)

`metrics._declared_size` (`metrics.py:330-345`) resolves `task["plan_file"]`
through `_resolve_plan_path` and calls `parse_frontmatter`. Post-R-19 that file
never exists, `except OSError` returns `None`, and declared size is `None` for
**368 of 368** settled records. ADR-046's declared-vs-delivered calibration has
been computing against zero declared sizes.

The record carries the field structurally: `spec.frontmatter.size`. Reading one
key replaces a path resolver, an archive lookup, a repo fallback, and a
swallowed exception.

Blocked by `trp-03`: without the backfill only 8 records carry a spec, so
landing this first would trade one blind read for a nearly-blind one.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] The silent `None` is a defect symptom; the change here is which source of
      truth the reader uses, which is a model decision

## Task List

1. **Read declared size from `spec.frontmatter.size`** on the settled record — S
   (traces: R-5)
2. **Delete `_resolve_plan_path`** and the `plans_archive_dir` threading through
   `iter_settled_tasks` and its callers — S (traces: R-5)
3. **Fail closed on a record with no spec**: report it rather than returning
   `None`, so a blind read is visible instead of reading as "no data"
   (ADR-033 §3) — S (traces: R-9)
4. **Verify against the measured baseline**: non-null declared size rises from 0,
   and per-class figures are compared before and after — S (traces: R-5)
5. Merge branch to main and verify integration — S

## Floor Check

- [x] Expected diff is below the calibrated floor threshold (≤ 50 headline lines)
- [x] The change is limited to one subsystem and maintains no architectural invariant
- [ ] `Files to Modify` substantially overlaps a sibling this plan is linearly ordered against
- [ ] This is docs-only and its sole consumer is a single sibling

Two boxes — the guardrail says merge unless justified, so: the natural merge
target is `trp-03`, but `trp-03` mutates the append-only settled log and this
changes a read path. Bundling them would put a history rewrite and a reporting
change behind one verdict, and the backfill's correctness is measured *by* this
read. Keeping them separate is what makes task 4's before/after comparison
meaningful. `trp-05` is the other candidate and is blocked on `trp-03` for a
different reason (deletion safety).

## Rejected Alternatives

- **Keep the archive fallback for pre-R-19 records** — rejected: that is the
  dual read R-5 was written to remove; `trp-03` backfills instead.
- **Merge into `trp-03`** — rejected: see Floor Check; the read is the backfill's
  measurement instrument.
- **Read `delivered_size.declared_size`** — rejected: that field is written at
  closure from the same absent plan file, so it inherits the defect.

## Files to Modify

- `src/aet/metrics.py`
- `tests/telemetry/`

## Validation Steps

- [ ] Lint passes
- [ ] Tests pass
- [ ] R-trace coverage: R-5 (1,2,4), R-9 (3)
- [ ] `aet metrics --json` reports non-null declared size for spec-carrying records
- [ ] `grep -rn '_resolve_plan_path\|plans_archive_dir' src/aet/metrics.py` is empty
- [ ] Per-class figures compared before and after, with any change explained
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the commit. Declared size returns to `None` for every record — today's
behaviour — and the backfilled specs remain, unread.

## Pipeline

`standard`.

---

_Stage: plan-approved_
