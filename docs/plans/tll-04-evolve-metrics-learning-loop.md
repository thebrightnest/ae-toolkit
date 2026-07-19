---
id: tll-04-evolve-metrics-learning-loop
size: S
status: queued
blocked_by:
  - tll-03-metrics-cli-surface
pipeline: minimal
security_review: required
security_review_reason: Edits `aet-evolve` skill instructions — the LLM trust boundary itself; the diff tells future agents to run and cite a command, so the wording is worth a diff scan for trust-boundary violations.
docs_sync: required
docs_sync_reason: The skill's documented retro flow changes (new evidence step); this plan is itself the docs change plus the recorded cycle under `docs/retros/`.
---

# Plan: Learning Loop — `aet-evolve` Consumes `aet metrics`

## Context

- PRD: `docs/prds/roadmap-p7a-telemetry-learning-loop-prd.md` (R-5, R-7) — the phase exit gate: at least one `aet-evolve` cycle runs consuming the CLI metrics. Doc 04 challenge 7: "the factory doesn't learn yet"; doc 06 potential 2 pairs this with `aet eval` (7b scope, not here).
- **Ground truth (2026-07-19):** `aet-evolve` today consumes `.agents/learnings.jsonl`, `docs/retros/`, plan+diff, and the telemetry archive via `aet mine-learnings` (`aet-evolve/SKILL.md:114-128`); its Prerequisites dispatcher list is at `aet-evolve/SKILL.md:35`; the `aet retro` procedure is at `:100-112` with flag detail in `aet-evolve/references/aet-retro.md`. What it lacks is the *quantitative* input: first-pass merge rate, rework, cost per merged task.
- Blocked by tll-03 — this plan documents `aet metrics` invocations in skill markdown, and skills-lint fails the merge if the command is not yet in the argparse tree.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect (roadmap Phase 7a)

## Locked design

- **`aet-evolve/SKILL.md`:** add `aet metrics` to the Prerequisites dispatcher list; add an explicit evidence step to the `aet retro` procedure — run `aet metrics --json` (with `--since <last retro date>` when a previous retro exists) and cite the returned values when proposing skill/workflow edits, next to the `mine-learnings` pattern input. One sentence fixing the boundary: metrics *inform* proposals; the human applies edits (analytics-only, ADR-031/035).
- **`aet-evolve/references/aet-retro.md`:** document the flags (`--json`, `--since`) mirroring the existing `mine-learnings` flag documentation style.
- **Recorded cycle (exit gate R-7):** during this plan's execution, run one real retro cycle on this repo: read actual `aet metrics` output, write `docs/retros/<date>-aet-metrics-cycle.md` citing the numbers obtained (first-pass rate, rework, cost per merged task — overall and per class), and route the finding(s): either a concrete `system-evolve` proposal justified by the numbers, or an explicit "no change warranted" with the numbers as the evidence. Weak gate, by design — the point is that the loop *ran on data*.

## Rejected Alternatives

- **Have evolve parse the telemetry archive directly instead of the CLI** — rejected: duplicating aggregation logic in a second consumer is how definitions drift; the CLI is the single sanctioned surface (doc 06: the CLI is the enforcement boundary).
- **Auto-apply skill edits when metrics regress** — rejected: analytics-only fence; metrics never gate or trigger writes without a human. Also 7b's `aet eval` is the behavioral-verification half — 7a deliberately does not close that loop.
- **Skip the recorded cycle and let the gate be implied** — rejected: the roadmap's exit gate requires the cycle to *run*; an unrun integration is the prose-only advancement frh-11 retired.

## Task List

1. `aet-evolve/SKILL.md`: Prerequisites + `aet retro` evidence step consuming `aet metrics --json` — S (traces: R-5)
2. `aet-evolve/references/aet-retro.md`: flag documentation — S (traces: R-5)
3. Recorded cycle: run `aet metrics` on the real ledger/telemetry and write `docs/retros/<date>-aet-metrics-cycle.md` with cited values and routed finding(s) — S (traces: R-7)

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] Not near-identical additions
- [x] Diff within 3 files / ~100 lines but cannot share a branch — it is the phase exit gate and must land after tll-03

## Files to Modify

- `aet-evolve/SKILL.md`
- `aet-evolve/references/aet-retro.md`
- `docs/retros/<date>-aet-metrics-cycle.md` (new, written during execution)

## Validation Steps

- [ ] `make validate` passes — in particular skills-lint parses the new `aet metrics` invocations in `aet-evolve` markdown against the real argparse tree (requires tll-03 merged)
- [ ] Documented procedure coverage: the `aet retro` section names the metrics evidence step; no invocation uses a flag absent from `bin/metrics`' parser (`--json`, `--since` only)
- [ ] The retro record exists under `docs/retros/`, cites actual command output values, and routes at least one finding or records an explicit evidence-backed "no change warranted"
- [ ] R-trace coverage: R-5 by tasks 1–2; R-7 by task 3; no unknown R-ids
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit. The skill returns to prose/mining inputs only; the retro record under `docs/retros/` is a historical document and stays (retros are append-only).

## Pipeline

`pipeline: minimal` — docs/skill-markdown-only change plus a recorded procedure run; no source code, so stage grouping buys nothing.

---

*Stage: implemented*
*Next step: run `aet-qa`*
