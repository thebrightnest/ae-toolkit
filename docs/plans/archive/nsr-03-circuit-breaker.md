---
id: nsr-03-circuit-breaker
size: M
blocked_by:
  - nsr-01-failure-taxonomy-signature
  - nsr-02-quarantined-state
pipeline: standard
status: merged
security_review: skipped
security_review_reason: bookkeeping over deterministic signatures plus a state transition already validated by `aet-state`; no new writer beyond the sanctioned transition, no network, no secret. The breaker only ever *stops* work (quarantine / stop-spawn), never grants it — fail-safe by direction.
docs_sync: required
docs_sync_reason: the per-task and systemic breaker thresholds and the "quarantined across shifts" behavior are operator-facing runtime semantics documented in `docs/PIPELINE.md` / `docs/CONVENTIONS.md`.
---

# Plan: Circuit Breaker — Per-Task + Systemic, Ledger-Persisted

## Context

- PRD: `docs/prds/roadmap-p5-night-shift-runtime-prd.md` (G2; R-4, R-5, R-6).
- Consumes nsr-01 signatures and drives tasks into the nsr-02 `quarantined` state. This is where "same signature 3× ⇒ quarantine" and "one signature across N tasks ⇒ stop the shift" live.
- **Ground truth (2026-07-15):** the finalize path is `_mark_failed` (`aet-work/bin/orchestrator:1125`) and `_finalize_task` (`:1191`); the batch loop is `run_batch` (`:1249`) with the spawn gate `has_actionable_tasks` and `stop_spawn` already a loop concept (`:1463`). Task records persist through the git-refs backend (`aet-work/lib/backends/git_refs_backend.py`, default since ewl-04). No breaker or retry-count exists today.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Locked design

- New `aet-work/lib/breaker.py`, pure decision logic over persisted counts:
  - **Per-task (R-4):** each failure appends `{signature, ts}` to the task record's `failure_signatures`. When the **same** signature appears `PER_TASK_BREAKER_THRESHOLD` (=3) times, `should_quarantine_task(record) -> True`; the finalize path then transitions the task `→ quarantined` (nsr-02) instead of requeuing. Differing signatures do not trip this rule (bounded separately by nsr-04's attempt cap).
  - **Systemic (R-5):** a shift-level tally maps `signature -> {distinct task_ids}`. When a signature's distinct-task count reaches `SYSTEMIC_BREAKER_THRESHOLD` (=3), `systemic_tripped(tally) -> signature`; `run_batch` sets `stop_spawn`, drains the running set, and exits with a named `systemic breaker: signature <sig> × <n> tasks` report.
- **Persistence (R-6):** per-task counts live on the task record (already git-refs-persisted). The systemic tally is persisted to the git-refs ledger under a dedicated `refs/aet/breaker` projection so a deterministic failure stays quarantined across shifts — **no new backend** (rides git-refs; PRD Open Question 4 resolved here as `refs/aet/breaker`, pending scope-validation).
- `canceled`-class failures (nsr-01) are excluded from both tallies (PRD Open Question 3: a clean stop is not breaker evidence).

## Rejected Alternatives

- **In-memory counts only** — rejected: a deterministic `design` failure would be re-attempted every shift; R-6 requires the quarantine to survive a restart, which needs persistence.
- **A new SQLite/JSON breaker store** — rejected: violates the no-second-backend fence; git-refs already persists task records and can hold a `refs/aet/breaker` projection.
- **Count raw failures, not signatures** — rejected: three *unrelated* failures on one task are not a deterministic cycle; only signature *stability* justifies giving up. Counting must key on the nsr-01 signature.

## Task List

1. ✓ Create `aet-work/lib/breaker.py`: per-task `should_quarantine_task`, systemic `systemic_tripped`, threshold constants — M (traces: R-4, R-5)
2. ✓ Persist per-task `failure_signatures` on the task record and the systemic tally to `refs/aet/breaker` via the git-refs backend — M (traces: R-6) [Changed: systemic tally persisted through `BreakerStore` in `aet-work/lib/breaker.py` rather than `aet-work/lib/backends/git_refs_backend.py`]
3. ✓ Wire the breaker into `run_batch`/finalize: per-task hit ⇒ `→ quarantined`; systemic trip ⇒ `stop_spawn` + drain + named report — M (traces: R-4, R-5)
4. ✓ Tests: `tests/test_circuit_breaker.py` (new) — M (traces: R-4, R-5, R-6, R-13) [Changed: also updated `tests/test_orchestrator.py` mocks for the new `_spawn_session_with_tail` signature]

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] Not one of several near-identical additions
- [x] Diff expected to exceed 3 files or 50 lines
- [x] Cannot share a branch — nsr-04 (triage/requeue) consumes the breaker verdict and is `blocked_by` it

## Files to Modify

- `aet-work/lib/breaker.py` (new)
- `aet-work/lib/backends/git_refs_backend.py` (breaker projection read/write)
- `aet-work/bin/orchestrator` (`run_batch`/finalize wiring)
- `tests/test_circuit_breaker.py` (new)

## Validation Steps

- [x] `make validate` passes; full suite passes
- [x] New source coverage — `tests/test_circuit_breaker.py` covers `aet-work/lib/breaker.py`:
  - `test_same_signature_thrice_quarantines`
  - `test_differing_signatures_do_not_quarantine`
  - `test_systemic_trip_at_n_distinct_tasks`
  - `test_canceled_excluded_from_tallies`
  - `test_breaker_counts_persist_across_reload` (integration, git-refs)
- [x] R-trace coverage: R-4/R-5 by tasks 1,3; R-6 by task 2; R-13 by task 4; no unknown R-ids
- [x] Distinguish test types: unit (breaker decisions) + integration (git-refs persistence + `run_batch` stop-spawn)
- [x] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit. Without the breaker, failures fall back to the pre-nsr `failed` terminal behavior; the `refs/aet/breaker` ref is orphaned harmlessly and can be deleted.

## Pipeline

`pipeline: standard` — behavior change in the batch loop with persistence; `standard` grouping covers the orchestrator integration surface.

---

*Stage: merged*
*Next step: None*
