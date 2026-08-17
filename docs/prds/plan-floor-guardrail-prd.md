# PRD: Give the Plan-Size Floor the Same Rigour as the Ceiling

## Overview

`docs/CONVENTIONS.md` "Task Size Guardrails" governs both bounds on plan size, but only one of them is engineered. The ceiling has four quantified signals, a two-of-four trigger, an auto-split rule with recursion and a max depth, a marking convention, and a measurement history — ADR-046 retired two size proxies after measuring them, one at r = 0.30. The floor is a single paragraph with no signals, no thresholds, and a self-assessed checkbox trio whose stated remedy fires only when all three boxes are false.

Splitting therefore needs two of four signals; merging needs a condition that is almost never true, because nearly any plan "stands alone" when read charitably. The regime biases toward fragmentation, and it did: planning `docs/prds/open-work-board-prd.md` produced 15 plans, 7 of them `S`, of which 3 were unnecessary splits later consolidated by hand.

The floor's cost unit is also obsolete. It weighs "branch, worktree, and review overhead", but ADR-045's `integration_mode: single-pr` makes per-task branches ephemeral and local (§4) and opens one PR per epic. The cost that remains, and that the floor never names, is the per-task stage pipeline — each task runs its own worktree seed plus tdd/implement/qa/review/cso/sync-docs sessions with verdicts, and telemetry already records `token_count` and `cost_estimate` for each.

## Goals

- The floor prompts consolidation as reliably as the ceiling prompts splitting.
- Plan-set shape is judged against the cost that AET actually pays per task.
- The two mechanically decidable floor signals are checked, not remembered.

## Non-Goals

- **Blocking on the floor.** Whether two plans are one coherent change is judgment-shaped; the lint reports and demands a written justification, as the ceiling does.
- **Capping plans per PRD.** Arbitrary, and it couples plan count to PRD size rather than to coherence.
- **Revisiting the ceiling.** ADR-046 settled it with measurement; this PRD only brings the floor up to it.
- **Re-planning the `owb-*` set.** Its three unnecessary splits were consolidated by hand and serve as the calibration corpus.

## Requirements

- **R-1**: The floor states signals with thresholds and a two-of-N trigger, mirroring the ceiling's structure.
- **R-2**: The floor's cost is denominated in per-task stage sessions rather than branch, PR and review overhead, with ADR-045 cited for why two of those three terms no longer apply.
- **R-3**: The plan template's Floor Check uses the same two-of-N trigger, not "all boxes false".
- **R-4**: The two mechanically decidable floor signals — a `Files to Modify` set substantially overlapping a sibling the plan is linearly ordered against, and a docs-only plan whose sole consumer is one sibling — are implemented as a reporting lint.
- **R-5**: The floor's diff threshold is derived from measured delivery via `aet size`, with the number and its basis recorded, rather than guessed.

## User Stories

- As a planner, I want the floor to tell me when two plans are one change, the way the ceiling tells me when one plan is two (satisfies: R-1, R-3).
- As an operator, I want plan-set shape judged against what a task actually costs me in agent sessions (satisfies: R-2).
- As a maintainer, I want the decidable half of the floor checked rather than self-certified (satisfies: R-4).
- As a maintainer, I want the threshold calibrated from delivery data, as the ceiling's proxies were (satisfies: R-5).

## Acceptance Criteria

- [x] The floor section states signals with thresholds and a two-of-N trigger (satisfies: R-1)
- [x] The floor's cost unit is stage sessions, citing ADR-045 §4 (satisfies: R-2)
- [x] The template's Floor Check no longer requires all boxes false to merge (satisfies: R-3)
- [x] The lint flags the three consolidated splits from the `owb-*` set, and does not flag `owb-03`, `owb-08` or `owb-13` (satisfies: R-4)
- [x] The diff threshold is recorded with the measurement it came from (satisfies: R-5)

## Technical Notes

The calibration corpus already exists and is unusually clean: one PRD planned under the current regime, with the fragmentation cases identified and the independent `S` plans identified, in the same session. `owb-01`/`owb-02`, `owb-05`/`owb-06` and `owb-09`/`owb-10` are the positives; `owb-03`, `owb-08` and `owb-13` are the negatives. A check that cannot separate those two sets is not ready.

Both decidable signals are computable from data plans already carry — `blocked_by` frontmatter and the `Files to Modify` section — so R-4 needs no new plan metadata.

ADR-046 is the model for R-5: measure, publish the correlation, and set or retire the threshold on the evidence rather than on intuition.

## Open Questions

- Should the lint live in `plans_lint` (corpus-wide, run by `make validate`) or in `plan_validate` (per-plan, run at intake)? Corpus-wide is the natural home for a signal about *sibling* relationships.
- Does the stage-session cost unit want a number, or is naming the unit enough to make the trade-off legible?

---

*Stage: synced*

*Next step: run `aet-ship`*
