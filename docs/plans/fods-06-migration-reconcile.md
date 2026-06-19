---
id: fods-06-migration-reconcile
blocked_by:
  - fods-05-frontmatter-intake
  - fods-07-live-settled-partition
size: L
---

# Plan: One-Time Plan Migration, Queue Rebuild & Reconciliation Report

## Context

- PRD: `docs/prds/forward-only-deterministic-work-state-prd.md` (Workstream C, migration)
- ADR: `docs/adr/011-forward-only-deterministic-work-state.md` (decision 9; "Harder" consequence — current `blocked_by` is ~89% fictional)

A one-time migration brings the existing corpus onto the new contract: add frontmatter to every `docs/plans/*.md` (infer `id` from the stem, `blocked_by` from existing prose where **unambiguous**, flag the rest), rebuild the queue via the fail-closed `sync` (`fods-05`) into the new schema, backfill terminal state for already-merged work via `record-merge`, let the partition (`fods-07`) seal merged tasks to history, and emit a **human-reviewed reconciliation report**. Per Decision 9 the recovered DAG is not trusted until that report is approved.

This is an enhancement to the toolkit's own tooling, not a reproducible defect report.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Tasks

1. **Migration script** — M (`scripts/migrate-plans-to-frontmatter.py`)

   For each plan lacking frontmatter, add `id` (stem), `size` (from an existing S/M/L label, else `M`), and `blocked_by` inferred **only from unambiguous inter-plan references**. Intra-plan "Task N blocks Task M" text is NOT promoted to an inter-plan edge. Emit a per-plan inference record: recovered / unresolved / flagged-for-review. Dry-run by default.

2. **Rebuild + backfill driver** — M (`scripts/migrate-plans-to-frontmatter.py` driver mode)

   Re-ingest the corpus via the fail-closed `sync` into the new schema; for already-merged work run `aet-state record-merge` to resolve real squash SHAs; `fods-07` seals them into `work-history.jsonl`. Idempotent.

3. **Reconciliation report** — S (`docs/audits/2026-06-18-fods-migration-reconciliation.md`)

   List dependencies recovered, dependencies unresolved (for human review), tasks marked terminal, and plans flagged. This is the artifact the human signs off before the recovered DAG is trusted.

4. **Tests** — M (`tests/test_migration.py`)

   - `test_unambiguous_edge_recovered`
   - `test_intra_plan_text_not_promoted_to_edge`
   - `test_ambiguous_dependency_flagged`
   - `test_rebuilt_queue_validates_under_fail_closed_sync`
   - `test_merged_work_backfilled_into_history_not_live`

5. **Run migration (dry-run → apply) behind a human sign-off gate** — S

6. **Merge branch to main and verify integration** — S

## ⚠️ Data scope (surfaced for explicit approval)

This plan **rewrites the frontmatter of ~86 plan files as mechanical script output**, not a hand-authored diff. The reviewable **source** diff (script + report + tests) is well within the ≤8-file / ≤300-line atomic gate. The corpus rewrite and the recovered DAG require human sign-off on the reconciliation report (Decision 9) before being trusted — they are never silently auto-applied.

## Blocked by

- fods-05-frontmatter-intake
- fods-07-live-settled-partition

## Validation Steps

- [ ] Unambiguous inter-plan edges are recovered; intra-plan task text is not turned into an edge.
- [ ] Ambiguous dependencies are flagged for human review, not guessed.
- [ ] The rebuilt queue validates under the fail-closed `sync` with no empty-`blocked_by`-from-unparsed-section tasks.
- [ ] Already-merged work is backfilled terminal and lands in `work-history.jsonl`, not the live queue.
- [ ] The reconciliation report lists every recovered, unresolved, and terminal item.
- [ ] `make validate` passes.

## Rollback Plan

The migration runs against a branch; revert the branch to restore the prior `docs/plans/*.md` and `.agents/work-queue.json`. The append-only `work-history.jsonl` is additive and safe to leave.

---

_Stage: synced_
