---
type: idea
status: parked
recorded: 2026-07-24
source: reports/2026-07-24-validation-runtime-review.md
trigger: >-
  Turn-level telemetry lands; until then the lever cannot be measured, so it cannot be planned into tasks.
depends_on: 
  - idea-turn-level-telemetry (not filed; see the blocker note in this item)
blocks: []
---

# Idea: Shorten the Long Implement/QA Session (the real 72%)

- **Status:** Parked (2026-07-24). Blocked on telemetry — cannot be planned into tasks yet.
- **Origin:** Recommendation 1 of `reports/2026-07-24-validation-runtime-review.md`
  (Investigation A). Carved out of the validation-runtime-efficiency initiative as a separate
  concern; see that PRD's Non-Goals.
- **Class:** Task-sizing / session-efficiency / model choice — **not** a validation-runtime
  problem. No validation change touches it.

## Summary

One agent session dominated an entire `aet run` batch. `cfg-01` session 1 ran **29 min 26 s —
72% of the whole batch's wall clock** — and validation was only ~9% of it. The other ~27 minutes
was agent work (reading the plan, writing the config-resolution overhaul, QA). The lever here is
how large a single plan/session is and how the agent spends its turns, not which tests run.

## The measured problem (Investigation A)

| Metric | Value |
|---|---|
| Session-1 duration | 1765.7 s (29 min 26 s) — **72% of wall clock** |
| pytest inside session 1 | 2 s fail + 2 min 41 s pass = **9.2%** of the session |
| Tokens | **22.6 M — 52.8%** of the batch's 42.8 M |
| Files modified | **38** (17 `src/`, 21 `tests/`) |
| Commits | 3 |
| Agent CLI | `kimi` |

- `cfg-01`'s three sessions together are **99.8%** of the batch's 2444.8 s wall clock; `cfg-03`
  ran entirely inside `cfg-01`'s shadow and added ~0 wall-clock time. `cfg-01` *is* the critical
  path.
- The session was a genuinely large change (the config-resolution overhaul spanning
  `factory.py`, `aet_state.py`, `orchestrator.py`, `setup.py`, … plus 21 test files), not obvious
  context-thrash — but 22.6 M tokens for one session also hints at large context re-reads or
  verbose exploration.

## Why it's parked (blocked on telemetry)

The finest telemetry granularity the toolkit emits today is the **stage** record — there is **no
per-tool-call or per-turn data**. So Recommendation 1 / Suggested Action 1 — "profile the
session's tool calls to find where the ~27 non-validation minutes went" — **is not possible from
telemetry as it stands**. Without that attribution you cannot tell context re-reads from genuine
work, so there is nothing concrete to plan against. This is the same telemetry gap that parks the
freshness idea (`content/backlog/deterministic-qa-freshness-suppression.md`).

## The one lever available today

**Task sizing.** A 38-file, 22.6 M-token single session is a decomposition candidate. Note this
is advisory, not a gate: **ADR-046** measures plan size at *closure*, not at intake — so the
signal here is "plans this large are worth splitting during planning," not a new intake check.

## What it would take to pick it up

1. **Turn-level telemetry enrichment** (per-tool-call / per-turn timing + tokens) or
   agent-transcript capture — the enabler. Everything else waits on this.
2. **Profile `cfg-01` session 1** against that data: attribute the ~27 minutes to context
   re-reads vs. exploration vs. genuine change; check whether `plan-approved → implemented →
   qa-complete` are correctly grouped into one session or the agent re-reads context it already
   had.
3. **Pick the lever the data points to:** decomposition guidance (split large plans in planning),
   session-grouping fixes (stop re-reading context across stages), or agent/model choice for
   large sessions.

## Revisit trigger

Pick this up when **turn-level telemetry lands** — the enabler that makes the profile possible
(shared with the freshness idea) — or when a run reproduces a single session dominating wall
clock badly enough to force the task-sizing conversation sooner.

## Links

- `reports/2026-07-24-validation-runtime-review.md` — Recommendation 1, Investigation A,
  Suggested Immediate Actions #1
- `docs/prds/validation-runtime-efficiency-prd.md` — Non-Goals (the carve-out)
- ADR-046 — Plan size is measured after implementation, not gated before it
- `content/backlog/deterministic-qa-freshness-suppression.md` — sibling idea, same telemetry gap
