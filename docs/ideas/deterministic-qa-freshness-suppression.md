# Idea: Deterministic QA-Freshness Re-Run Suppression

- **Status:** Parked (2026-07-24). Deferred — efficiency-only and currently unmeasured.
- **Origin:** Surfaced as requirement **R-6** during scope validation of the
  validation-runtime-efficiency initiative and lifted out of that sprint.
  See `docs/prds/validation-runtime-efficiency-prd.md` (Scope Validation Findings) and
  `reports/2026-07-24-validation-runtime-review.md`.
- **Would-be plan (not written):** `vre-04-qa-freshness-deterministic-suppression`.

## Summary

Make the *redundant QA re-run suppression* deterministic in code. Today the orchestrator
already computes a freshness decision (`_qa_freshness_decision`, `orchestrator.py:414`) but
acts on it only by injecting an **agent-discretionary prose clause** (`_freshness_clause`,
`orchestrator.py:388`). The idea is to have the runtime itself suppress the redundant suite
re-run when freshness resolves to `SKIP`/`LINT_ONLY`, rather than relying on the agent to honor
the prose.

## Context

- `AET_QA_FRESHNESS` is exported but has **no runtime consumer** (verified 2026-07-24 — read
  only in tests and run logs). The prose clause is the sole driver of re-run suppression today.
- **ADR-025 decision 4** deliberately keeps the freshness signal *advisory*: it modulates only
  the prompt clause and an env signal, and **never** touches the fail-closed verdict gate
  `_require_passing_verdict`. Freshness is biased to `RUN`, so every ignore-path is safe — the
  worst case of the agent ignoring the prose is a redundant re-run (wasted time), never a
  skipped-but-needed verdict.
- Therefore this is an **efficiency-determinism gain, not a correctness fix**. It is *not* the
  prose→code correctness-regression class that the `aet ship merge` ancestry check fell into
  (that was a real gate that regressed; this is an advisory hint by deliberate design).

## Why it's deferred

- **Efficiency-only and unmeasured.** There is no turn-level telemetry to size how often the
  redundant re-run actually fires or what it costs in aggregate. Committing runtime + ADR effort
  to an unquantified win is premature — **ADR-031: enforce on evidence, never on a guess.**
  (This is the same telemetry gap that parks the cfg-01 session-efficiency idea —
  `docs/ideas/cfg-01-session-efficiency.md`.)
- **It reopens a deliberate decision.** Making suppression *enforced* rather than advisory
  changes ADR-025 decision 4, which was chosen on purpose. That reversal wants evidence behind
  it, not principle alone.

## The tension worth naming

This idea aligns with the standing preference for **determinism over AI discretion** (moving
behavior from agent-remembered prose into code-enforced logic). That pull is real. It is held in
check here only because this *particular* instance is efficiency-only, safe-by-construction
(bias-to-`RUN`), and unmeasured — not because determinism is unwelcome.

## What it would take if picked up

1. **ADR first.** Author an ADR extending ADR-025 that makes freshness suppression *enforced*
   (the runtime acts on the decision) while keeping `_require_passing_verdict` untouched and
   bias-to-`RUN` preserved. Per "ADRs must exist before `aet sprint add`", this precedes any
   plan.
2. **Plan.** Write `vre-04-qa-freshness-deterministic-suppression` tracing this idea: the
   runtime suppresses the redundant re-run on `SKIP`/`LINT_ONLY`; the verdict gate is unchanged;
   `AET_QA_FRESHNESS` gains a real consumer or is replaced by the in-process decision.
   Files: `src/aet/cli/orchestrator.py`, `tests/orchestrator/**`.
3. **Acceptance.** When freshness resolves to `SKIP`/`LINT_ONLY`, the redundant suite re-run is
   suppressed by the runtime (not only requested via prose); `_require_passing_verdict` is
   unchanged and bias-to-`RUN` is preserved.

## Revisit trigger

Pick this up when **turn-level telemetry lands** (the same enabler as Rec 1) and can show the
redundant re-run is a measurable cost — or when a concrete run demonstrates the agent skipping a
safe suppression often enough to matter.

## Links

- ADR-025 — Validation Freshness: Gate Stages Trust a Fresh QA Verdict Instead of Re-Running
  (`docs/adr/025-validation-freshness-trust-fresh-qa-verdict.md`)
- ADR-031 — Observation vs Enforcement: enforce only on evidence
- `docs/prds/validation-runtime-efficiency-prd.md` — Scope Validation Findings (R-6 reframing)
- `reports/2026-07-24-validation-runtime-review.md`
