---
id: nsr-06-per-task-cost-rollup
size: M
blocked_by:
  - twe-07-exit-gate-rehearsal
pipeline: standard
status: draft
security_review: skipped
security_review_reason: read-only aggregation of telemetry already on disk, written to the task's own ledger record via the sanctioned path; no new writer, network, or trust boundary. The value is inert data — explicitly no code path reads it to gate or kill.
docs_sync: required
docs_sync_reason: introduces a per-task `cost` field on the ledger record that the morning desk and analytics read; the field and its analytics-only contract are documented in `docs/PIPELINE.md` / CONTEXT.md.
---

# Plan: Per-Task Cost Rollup to the Ledger (analytics-only)

## Context

- PRD: `docs/prds/roadmap-p5-night-shift-runtime-prd.md` (G4; R-11). Independent of the failure chain — gated only on the Phase 4 exit, runs in parallel with nsr-01/02.
- Closes the roadmap's "per-task cost captured to the ledger" as **pure observation**: cost informs the desk, it never governs the run (the budget Non-Goal / owner decision 2026-07-15).
- **Ground truth (2026-07-15):** per-session token/cost already lands on `stage` telemetry records as `token_count`/`cost_estimate` (`_emit_stage_session`, `aet-work/bin/orchestrator:337`) and is summed **per-run** by `_usage_aggregates` (`:422`). What is missing is a **per-task** rollup written onto the task's ledger record. `usage.py` preserves null honestly (never estimates); this plan preserves that — an all-null task records null cost, never 0.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Locked design

- Add a per-task aggregation (mirroring `_usage_aggregates` but filtered to one `task_id`) that sums the task's `stage` records into `{total_tokens, total_cost}`, preserving null when no record carried a value.
- At task close (the finalize path, alongside the terminal transition), write the rolled-up `cost: {tokens, usd}` onto the task's git-refs ledger record.
- **Analytics-only guard (R-11):** no orchestrator code path reads this field for a gate, kill, throttle, or triage decision — enforced by a test asserting the value is write-only from the runtime's perspective (grep-style/behavioral check that no control path references it).

## Rejected Alternatives

- **Compute cost live to enforce a ceiling** — rejected: the budget Non-Goal (owner decision) — cost observes, never governs; and cost is only known post-hoc at session exit (`usage.py`), so a live ceiling is impossible without the estimation the module forbids.
- **Store zero when usage is unmeasurable** — rejected: null is the honest value (Kimi has no published price); zeroing would corrupt cost-per-task analytics. Preserve null end-to-end.
- **Leave cost per-run only** — rejected: the desk and the Phase 8 scoreboard need cost-per-*task*; per-run aggregation cannot be decomposed after the fact.

## Task List

1. Add a per-`task_id` token/cost aggregation over the run's `stage` telemetry (null-preserving) — M (traces: R-11)
2. Write the rolled-up `cost` onto the task's git-refs ledger record at task close — S (traces: R-11)
3. Docs: document the per-task `cost` field and its analytics-only contract in `docs/PIPELINE.md` / CONTEXT.md — S (traces: R-11)
4. Tests: `tests/test_per_task_cost_rollup.py` (new) — M (traces: R-11, R-13)

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] Not one of several near-identical additions
- [x] Diff expected to exceed 3 files or 50 lines
- [x] Cannot share a branch — independent surface (telemetry rollup); no shared files with the failure chain

## Files to Modify

- `aet-work/bin/orchestrator` (per-task rollup + write-at-close)
- `docs/PIPELINE.md`, `CONTEXT.md`
- `tests/test_per_task_cost_rollup.py` (new)

## Validation Steps

- [ ] `make validate` passes; full suite passes
- [ ] New source coverage — `tests/test_per_task_cost_rollup.py`:
  - `test_rollup_sums_stage_records_for_task`
  - `test_rollup_preserves_null_for_all_null_task`
  - `test_cost_written_to_ledger_record_at_close`
  - `test_no_control_path_reads_cost` (analytics-only guard)
- [ ] R-trace coverage: R-11 by tasks 1–3; R-13 by task 4; no unknown R-ids
- [ ] Distinguish test types: unit (aggregation, null-preservation) + integration (ledger write at close)
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit. The per-task `cost` field stops being written; per-run aggregation (`_usage_aggregates`) is untouched, so no existing analytics regress.

## Pipeline

`pipeline: standard` — additive read-only telemetry rollup; low risk, `standard` grouping is sufficient.

---

*Stage: implemented*
*Next step: run `aet-qa`*
