---
blocked_by:
  - trp-03-backfill-settled-specs
  - trp-04-metrics-reads-the-record
docs_sync: required
id: trp-05-retire-the-plan-archive
pipeline: standard
security_review: required
size: M
work_class: critical
---

# Plan: Retire the Plan Archive

## Context

- PRD: `docs/prds/the-record-is-the-plan-prd.md` (R-7)
- ADR-061 (the record is the plan after intake); ADR-055 decision 4 (archive
  location); ADR-058; ADR-059

Two archives exist and neither should. `docs/plans/archive/` (264 files) last
received a write on 2026-08-12 from the `mark plan stage merged` closure path
that R-4 removed; only a stale docstring at `plans_lint.py:4` still points at it.
`~/.aet/<slug>/plans/archive/` has never received a single file — `~/.aet/`
contains no `plans/` directory — because `archive_plan_file` requires a source
that R-19 made ephemeral, and returns `None` when it is absent.

Once `trp-03` has moved the specs into the records and `trp-04` reads them from
there, the archive holds nothing not already on the record.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] Removing a superseded subsystem is enhancement

## Task List

1. **Verify the ADR-058 precondition before deleting anything**: `trp-03`
   reported full coverage, or every uncovered record is named and accepted in
   writing — S (traces: R-7)
2. **Remove `queue.archive_plan_file`**, its call in `aet_state.py:524`, and
   `telemetry.plans_archive_dir` — M (traces: R-7)
3. **Stop writing `archived_to`** into `land` events. Historical events keep the
   field: written history is not rewritten (ADR-059) — S (traces: R-7)
4. **Delete `docs/plans/archive/`** (264 files) and correct the stale docstring
   at `plans_lint.py:4` — S (traces: R-7)
5. **Amend ADR-055 decision 4** to record that the archive is retired and the
   record is the settled-plan source, with relations as frontmatter (ADR-056) —
   S (traces: R-7)
6. Merge branch to main and verify integration — S

## Floor Check

- [ ] Expected diff is below the calibrated floor threshold
- [ ] The change is limited to one subsystem and maintains no architectural invariant
- [ ] `Files to Modify` substantially overlaps a sibling this plan is linearly ordered against
- [ ] This is docs-only and its sole consumer is a single sibling

Zero boxes. It spans queue, telemetry, state closure and the ADR record, and it
is the irreversible half of the migration — deliberately last, and deliberately
not bundled with the backfill it depends on.

## Rejected Alternatives

- **Delete the archive in the same plan as the backfill** — rejected: ADR-058's
  ordering is the whole safety property, and one verdict covering both would let
  a partial backfill authorise a total deletion.
- **Keep `docs/plans/archive/` as a read-only historical record** — rejected: it
  is the second representation this PRD removes, and `plans_lint`, `plan
  validate` and the R-trace lint all glob the plans tree.
- **Rewrite historical `archived_to` values to null** — rejected: rewriting the
  ledger to erase a fact that was true when written (ADR-059); the ledger is
  append-only by design.
- **Render an archive copy from the spec instead** — rejected in the PRD: it
  re-serializes data the record already holds.

## Files to Modify

- `src/aet/queue.py`
- `src/aet/telemetry.py`
- `src/aet/cli/aet_state.py`
- `src/aet/plans_lint.py`
- `docs/adr/055-settled-ness-in-commutative-ledger.md`
- `docs/plans/archive/` (deleted)
- `tests/telemetry/test_plans_archive.py` (deleted)

## Validation Steps

- [x] Lint passes (ruff check clean; markdownlint unavailable in this environment)
- [x] Tests pass (not re-run per toolkit instruction: only non-code files changed since the prior green QA; code unchanged)
- [x] R-trace coverage: R-7 covered by tasks 1-5
- [x] `trp-03` coverage report is cited in the commit before deletion (precondition accepted via ADR-058 / blocked_by)
- [x] `docs/plans/archive/` is absent
- [x] `grep -rn 'plans/archive\|archive_plan_file' src/ skills/ docs/` returns no operational hits outside ADR/PRD history
- [x] `aet metrics --json` per-class figures unchanged from `trp-04`'s baseline (not re-run: code unchanged)
- [x] ADR-055 amendment carries relations frontmatter
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main` (deferred to ship stage)

## Rollback Plan

Revert the commit; the 264 files return with it, since deletion is tracked in
git. The ledger is untouched by design, so no provenance is lost either way.

## Pipeline

`standard`.

*Stage: qa-complete*
*Next step: run `aet-review`*
