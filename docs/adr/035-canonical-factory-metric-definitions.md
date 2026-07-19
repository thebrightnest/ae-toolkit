# Canonical Factory-Metric Definitions

## Status

Accepted. Refines ADR-028 (work-class attribute and zero-review policy); extends ADR-031 (runtime observation vs enforcement).

## Context

Roadmap Phase 7a makes the three factory metrics — first-pass merge rate, rework count, cost per merged task — queryable through the CLI and consumed by `aet-evolve`. At grounding, two definitions of "clean merge" coexisted: `track_record.is_clean_merge` required all four verdict kinds, while `aet desk` derived the required set from the plan's gate-routing keys (`security_review` / `docs_sync`: `required|skipped`). A task whose plan legitimately routed a gate to `skipped` could be clean to the desk and unclean to the track record at the same time. Cost had a parallel problem: nsr-06's rollup sums only the settling run's stage telemetry, so a task reworked across several runs kept only the last run's cost. If the desk, the CLI, and the future scoreboard compute these numbers differently, the numbers are anecdotes — the docs↔code reality gap this program exists to kill.

## Decision

1. **First-pass merge (clean)** — a settled task counts as first-pass-clean when it reached `merged`, every verdict kind required *by its plan's gate routing* passes (`qa`/`review` always; `cso`/`sync-docs` unless the plan routed that key to `skipped`), no failed stage/test_run telemetry record exists, and it carries no rework (item 2). One shared implementation — `plan_parser.required_verdict_kinds` + `track_record.is_clean_merge` — is consumed by `aet desk --eligibility`, `aet metrics`, and later the 7b scoreboard. This refines ADR-028's clean-merge definition to be routing-aware. A missing or unreadable plan file fails safe: all four kinds required, preserving pre-7a behavior for legacy settled tasks.
2. **Rework count** — per task: repeated stage runs (stage telemetry records beyond the first for any stage name) plus `failed → *` re-entry transitions from the task's history. The boolean predicates inside `is_clean_merge` and the integer count exposed to metrics share one counting core so the two cannot drift.
3. **Cost per merged task** — the sum of a task's stage telemetry (`token_count` / `cost_estimate`) across the *whole* telemetry archive, i.e. cross-run, not the settling-run rollup stored on the ledger record. Null-honest per ADR-031 and the telemetry schema: an all-null measure stays `null` (Kimi `usd` is null by design), partial data is summed with explicit coverage counts (`usd_known_tasks`), and nothing is ever estimated or zero-filled.
4. **Analytics-only** (extends ADR-031) — the metrics are computed read-side from existing stores (settled history, telemetry archive, gate evidence). Phase 7a adds no telemetry emission, no ledger write paths, and no persisted `first_pass` flag; derivation is retroactive at query time. No code path reads these numbers to gate, kill, route, throttle, or triage; `aet-evolve` cites them as evidence for proposals a human applies. The zero-review *arming* decision that will eventually consume these counts is 7b's gate, certified on Phase 6's de-correlated review data.
5. **Retroactive derivation over stamping** — no `first_pass` boolean is written onto task records at merge time. Recomputation is cheap at this scale and works uniformly over already-settled history; revisit only if 7b's scoreboard demonstrates a query-cost or audit need for the stamp.

## Consequences

- `aet desk --eligibility` counts may shift upward for classes whose plans routed gates to `skipped` — those tasks now count as first-pass-clean. That is the correction this ADR records, not a regression.
- 7b's scoreboard rows and the zero-review arming decision read these definitions. Changing a definition later re-baselines the track record; treat any future change as a new ADR, not an edit.
- The ledger's per-task `cost` field (settling-run rollup) stays as the desk's per-task display; the cross-run figure lives in the metrics aggregation. The two are labeled distinctly so they are never conflated.
