---
id: gdl-01-plan-floor-guardrail
size: M
work_class: normal
blocked_by: []
pipeline: standard
security_review: required
docs_sync: required
---

# Plan: Give the Plan-Size Floor the Same Rigour as the Ceiling

## Context

- PRD: `docs/prds/plan-floor-guardrail-prd.md`
- Guardrails: `docs/CONVENTIONS.md` "Task Size Guardrails", `.agents/templates/plan-template.md` Floor Check
- Measurement precedent: ADR-046 (plan size measured at closure, not gated at intake)
- Integration model that invalidated the floor's cost unit: ADR-045 (`integration_mode: single-pr`)

The guardrail model is asymmetric, and the asymmetry is measurable:

| | Ceiling (split) | Floor (merge) |
| --- | --- | --- |
| Signals | 4, each with a threshold | 0 |
| Trigger | 2 of 4 | 3 of 3 boxes false |
| Machinery | Auto-Split Rule, recursion, max depth 3, `ATOMIC OVERSIZED`, `Split from:` | one paragraph |
| Measurement | ADR-046 measured and retired two proxies (file count; task-list length at r = 0.30) | none |

Splitting needs two of four signals; merging needs all three template boxes false, which is nearly never true because almost any plan "stands alone" if read charitably. The regime produces fragmentation, and it did: planning the open-work-board PRD yielded 15 plans, 7 of them `S`, of which 3 were unnecessary splits — `owb-02` from `owb-01`, `owb-06` from `owb-05`, `owb-09` from `owb-10`. All three were consolidated by hand at review, which is exactly the work a guardrail should have prompted.

The floor's cost unit is also obsolete. It weighs "branch, worktree, and review overhead", but under ADR-045 `single-pr` per-task branches are ephemeral and local (§4) and there is one PR per epic. The cost that does not vanish — and that the floor never names — is the per-task stage pipeline: each task runs its own worktree seed plus tdd/implement/qa/review/cso/sync-docs sessions with verdicts. Telemetry already records `token_count` and `cost_estimate` per stage.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] The fragmentation it addresses is a guardrail gap, not a code defect

## Task List

1. **Give the floor four signals with a 2-of-N trigger**, mirroring the ceiling's structure in `docs/CONVENTIONS.md`: expected diff below half the `S` ceiling; one subsystem and no architectural invariant maintained; a `Files to Modify` set substantially overlapping a sibling it is linearly ordered against; docs-only with a single sibling as its sole consumer — M (traces: R-1)
2. **Re-denominate the floor in stage sessions**, not branch/PR/review overhead, citing ADR-045 §4 for why the branch and PR terms mostly vanish under `single-pr` — S (traces: R-2)
3. **Fix the template's trigger.** `.agents/templates/plan-template.md` says "if all boxes are unchecked, merge" — a 3-of-3 rule. Align it with the 2-of-N model and add the two new signals as checkable items — S (traces: R-3)
4. **Implement the two computable signals in `plans_lint`**: file-set overlap with a linearly-ordered sibling, and a docs-only plan whose sole consumer is one sibling. Report, do not block — coherence is judgment-shaped, so the lint prompts a written justification the way the ceiling does — M (traces: R-4)
5. **Calibrate the diff threshold from measured delivery** using `aet size` / `plan_size.py` rather than the guessed half-`S` figure, the way ADR-046 retired two proxies with real numbers. Record the number and its basis — M (traces: R-5)
6. **Validate against this session's own data**: the check must flag the three consolidated splits and must not flag `owb-03`, `owb-08`, `owb-13`, which are genuinely independent `S` plans — M (traces: R-4, R-5)
7. Merge branch to main and verify integration — S

## Floor Check

- [x] Stands alone: it changes how every future plan set is shaped, independently of any PRD.
- [x] Diff exceeds overhead: a guardrail section, a template, a lint implementation, a calibration pass, a corpus test.
- [x] Cannot share a branch with the `owb-*` set — that is the corpus this is calibrated against, and bundling the measurer with the measured hides which one is wrong.

## Rejected Alternatives

- **Leave the floor advisory-only** — rejected: this session produced 7 `S` plans and 3 unnecessary splits under exactly that regime. The ceiling is advisory too, but it has signals and thresholds; the floor has neither.
- **Make the floor a hard block at scope validation** — rejected: whether two plans are one coherent change is judgment-shaped. The lint should report and demand a justification, as the ceiling does, not refuse.
- **Cap plans per PRD** — rejected: arbitrary, and it couples plan count to PRD size rather than to coherence.
- **Keep "branch/PR/review overhead" as the cost unit** — rejected: ADR-045 removed two of its three terms, and the remaining real cost is per-task agent sessions, which telemetry already measures.

## Files to Modify

- `docs/CONVENTIONS.md`
- `.agents/templates/plan-template.md`
- `src/aet/plans_lint.py`
- `src/aet/plan_size.py`
- `tests/plan/`

## Validation Steps

- [ ] The floor section states four signals with thresholds and a 2-of-N trigger
- [ ] The template's Floor Check no longer requires 3-of-3 to merge
- [ ] `plans lint` flags the three consolidated splits from this session
- [ ] `plans lint` does not flag `owb-03`, `owb-08`, `owb-13`
- [ ] The diff threshold is derived from measured delivery, with the number and basis recorded
- [ ] Lint passes
- [ ] Tests pass
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the commits. The guardrail text and the template return to their prior wording, and the lint check is additive — removing it changes no plan on disk.

---

*Stage: plan-approved*

*Next step: run aet sprint add docs/plans/gdl-01-plan-floor-guardrail.md*
