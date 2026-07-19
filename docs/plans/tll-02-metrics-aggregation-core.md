---
id: tll-02-metrics-aggregation-core
size: M
status: approved
blocked_by:
  - tll-01-first-pass-rework-definitions
pipeline: standard
security_review: skipped
security_review_reason: Pure read-side analytics over local archives (history JSONL + telemetry JSONL + evidence); no auth, dependency, network, subprocess, or write-path surface in the diff.
docs_sync: required
docs_sync_reason: Establishes the canonical metric projection shape (field names, null/coverage contract) that the CLI (tll-03) and 7b's scoreboard will consume; the telemetry guide documents it.
---

# Plan: Metrics Aggregation Core (`lib/metrics.py`)

## Context

- PRD: `docs/prds/roadmap-p7a-telemetry-learning-loop-prd.md` (R-3, R-6; aggregates R-1/R-2 into rates).
- **Ground truth (2026-07-19):** per-task primitives land in tll-01 (`track_record.is_clean_merge` routing-aware, `track_record.rework_count`). Cost today is per-run only: nsr-06's `_task_usage_aggregates` (`aet-work/bin/orchestrator:468`) sums the settling run's stage records, so a task reworked across N runs keeps only the last run's cost on its ledger record. `iter_telemetry_task_records` (`track_record.py:42`) already scans a task's stage/test_run records across the *whole* archive. Settled records carry `settled_at` (seal at `aet_queue.append_history_record`), `merged_at`, `completed_at`, `work_class`, `plan_file`.
- Null contract (ADR-031, `aet-work/references/telemetry-log-schema.md`): unmeasured stays `null`, never 0 or estimated. Kimi `cost_usd` is always null (`usage.py:40`, by design).
- Blocked by tll-01 (consumes its shared definitions).

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect (roadmap Phase 7a)

## Locked design

- **New `aet-work/lib/metrics.py`** — cross-task aggregation, no CLI, no I/O beyond the existing readers:
  - `iter_settled_tasks(history_file, since=None) -> list[dict]` — `track_record.read_history_tasks` filtered by `settled_at >= since` (ISO `YYYY-MM-DD`, date comparison); legacy records without `settled_at` fall back to `completed_at`, then `merged_at`; a record with none of the three is included only when `since` is None.
  - `task_cost(task_id, ...) -> {"tokens": int | None, "usd": float | None}` — sum `token_count` / `cost_estimate` over the task's stage records from `iter_telemetry_task_records` (cross-run by construction). All-null ⇒ `None`; partial ⇒ sum of known values (coverage is reported at the aggregate level, not hidden).
  - `aggregate(history_file, since=None, ...) -> dict` — the canonical projection: `{"since": ..., "overall": bucket, "classes": {work_class: bucket}}` where each bucket is `{"settled": n, "merged": n, "first_pass": n, "first_pass_rate": float | None, "rework": int, "cost": {"tokens_total": int | None, "tokens_avg_per_merged": float | None, "usd_total": float | None, "usd_avg_per_merged": float | None, "usd_known_tasks": int}}`. `first_pass_rate` is `first_pass / merged`, `None` when `merged == 0`. Class buckets are **data-driven** (whatever `work_class` values appear in history, incl. `unclassified`), sorted — not hardcoded to trivial/normal/critical.
- **Read-only, analytics-only.** No writes, no gating input; every number derives from tll-01's shared definitions (`is_clean_merge`, `rework_count`) so desk, CLI, and the 7b scoreboard cannot disagree.

## Rejected Alternatives

- **Read cost from the ledger record's `cost` field instead of re-summing telemetry** — rejected: that field is the settling-run rollup only (nsr-06), so reworked tasks are under-counted; the archive scan is the honest cross-run figure. The ledger field stays as the desk's per-task display.
- **Hardcode the three known work classes** — rejected: work_class is plan data (twe-01); a metrics surface that silently drops an unfamiliar class recreates the reality gap. Data-driven buckets with `unclassified` explicit.
- **Estimate missing `usd` from a price table** — rejected: violates the null contract and ADR-031; unknown stays unknown, with coverage counts.

## Task List

1. `metrics.iter_settled_tasks` with `--since`-ready window filtering — S (traces: R-3)
2. `metrics.task_cost` cross-run, null-honest — M (traces: R-3)
3. `metrics.aggregate` projection (overall + data-driven class buckets; rates, rework, cost + coverage) — M (traces: R-3)
4. Tests: `tests/test_metrics.py` (new) — M (traces: R-6)

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] Not near-identical additions
- [x] Diff exceeds 3 files / 50 lines
- [x] Cannot share a branch — tll-03 (CLI) consumes this module; landing the core separately keeps the CLI diff reviewable

## Files to Modify

- `aet-work/lib/metrics.py` (new)
- `tests/test_metrics.py` (new)

## Validation Steps

- [ ] `make validate` passes
- [ ] New source coverage — `tests/test_metrics.py`:
  - `test_iter_settled_tasks_since_window_filters_on_settled_at`
  - `test_iter_settled_tasks_legacy_fallback_completed_at`
  - `test_task_cost_sums_stage_records_across_runs`
  - `test_task_cost_all_null_usd_returns_none`
  - `test_aggregate_first_pass_rate_per_class_and_overall`
  - `test_aggregate_rework_totals`
  - `test_aggregate_cost_averages_and_usd_coverage_count`
  - `test_aggregate_empty_history_returns_zeroed_projection`
  - `test_aggregate_unknown_work_class_gets_own_bucket`
- [ ] R-trace coverage: R-3 by tasks 1–3; R-6 by task 4; no unknown R-ids
- [ ] Test types: unit (window filter, cost sums, projection shape) + integration (aggregate over synthetic history + telemetry archive fixtures, conftest `AET_TELEMETRY_ARCHIVE_DIR` isolation)
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit. The new module and its tests disappear; no caller exists outside the plan (tll-03 lands separately), no stored data changes.

## Pipeline

`pipeline: standard` — new analytics module feeding future merge decisions; standard grouping.

---

*Stage: plan-approved*
*Next step: run `aet-work`*
