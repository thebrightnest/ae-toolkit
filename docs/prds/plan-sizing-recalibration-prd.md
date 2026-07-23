# PRD: Recalibrate Plan Sizing and Replace the Plan-Time Size Gate

## Overview

AET's task-size guardrails systematically under-scope plans. This PRD replaces the current model on the strength of measured evidence rather than intuition: across 264 plans and 1,048 commits, the declared size labels are miscalibrated by roughly 2x against delivered work, and the single code-enforced check measures a variable with almost no predictive power (r = 0.30) at a threshold ~30x beyond anything ever observed.

The fix has two halves. First, **recalibrate** the soft budgets to what work actually costs. Second, **stop gating size before implementation and start measuring it after** — plan-time diff size is fundamentally unknowable, which is why every proxy tried so far has failed. A ship-time measurement loop turns sizing from a guess enforced at intake into evidence collected at closure, which is the only point where the true number exists.

This supersedes `docs/prds/task-size-guardrails-revision-prd.md` (adopted 2026-07-21), whose central premise — that task-list length is a sound proxy for diff size — is falsified below.

## Goals

- **G1:** Align the S/M/L bands and story budgets with measured delivery, so a label predicts reality instead of contradicting it.
- **G2:** Retire the task-list-length intake gate and record, with evidence, why proxy-based plan-time size gating does not work.
- **G3:** Establish a ship-time size measurement loop so future threshold changes are derived from data, not re-argued from intuition.
- **G4:** Remove the structural bias toward small plans: the one-directional framing, the any-one-signal disjunction, and the subsystem check that penalises a change for carrying its own docs and tests.
- **G5:** Preserve the protective intent — no unbounded, multi-concern session enters the queue unnoticed.
- **G6:** Do not retroactively invalidate existing plans.

## Non-Goals

- This PRD does not remove size guidance entirely; it recalibrates it and moves enforcement to where the data exists.
- This PRD does not change the plan frontmatter contract, the queue schema, or the `docs/plans` vs `docs/roadmaps` boundary (ADR-006).
- This PRD does not make thresholds per-project configurable — that remains deferred (see Open Questions).
- This PRD does not weaken the vertical-slice rule; slices stay end-to-end, they just stop being cut smaller than necessary.
- This PRD does not introduce an external telemetry service. Measurement stays local-first, consistent with ADR-015.
- This PRD does not re-evaluate or re-size already-merged plans.

## Evidence

All figures measured on 2026-07-23 over `docs/plans/*.md` (264 plans) and non-merge commits attributed to plans by id (1,048 commits scanned, 729 attributed, 147 plans with a measurable code diff). "Code diff" counts added+deleted lines outside `docs/`, `.agents/`, `content/`, and `reports/`.

### The labels understate delivery by ~2x

| Label | Claimed bound | Actual median | p90 | Max | Exceeds its own bound |
| ----- | ------------- | ------------- | ---- | ---- | --------------------- |
| S     | ≤ 100         | 81            | 384  | 420  | 40%                   |
| M     | ≤ 200         | **405**       | 836  | 1440 | **71%**               |
| L     | > 200         | 832           | 6244 | 6244 | —                     |

M is the modal label (117 of 147 measured plans, 68% of all plans by frontmatter) and overshoots its stated ceiling in 71% of cases, by about 2x at the median.

### The enforced metric does not predict what it claims to

Correlation between task-list length and actual code diff: **r = 0.30**. Beyond roughly six task-list lines the relationship is flat:

| Task-list lines | n  | Median code diff |
| --------------- | -- | ---------------- |
| 1–5             | 8  | 76               |
| 6–10            | 60 | 413              |
| 11–20           | 31 | 361              |
| 21+             | 25 | 352              |

A 25-line task list produces *less* diff than a 7-line one. The revision PRD's stated rationale — "a task list that long is almost certainly a > 300-line diff" — is false by more than an order of magnitude.

### The gate is inert

Task-list lengths across all 264 plans: median 10, mean 13.2, p90 25, **max 54** — 18% of the 300-line cap. **Zero** plans have ever exceeded it. At the observed ratio (~38 diff lines per task-list line), the 300-line cap corresponds to an ~11,550-line diff. `validate_size()` has never rejected a plan and structurally cannot.

### Threshold-loosening alone has already been tried

The 2026-07-21 revision dropped the file-count limit and calendar-time limits. Post-revision plans (n=21) shifted only marginally — median task-list length 10 → 16, mean 12.5 → 18.2, max *down* 54 → 35 — and the label mix was unchanged (L: 4% before, 5% after). Loosening numbers without changing the framing did not move behaviour.

## Requirements

### Recalibration

- **R-1** — The S/M/L bands are redefined against measured delivery: **S ≤ 150**, **M ≤ 600**, **L > 600** (re-evaluate against the full model; justify explicitly above 1500). The band edges are set near the observed distribution so a label is a prediction rather than an aspiration.
- **R-2** — The story-level diff budget is raised from 500 to **1200** expected lines.
- **R-3** — The context-budget figures are raised from ~30k/~50k tokens to **~60k (task) / ~100k (story)**, reflecting current context capacity rather than the original 100k-session-ceiling rationale.

### Retiring the plan-time gate

- **R-4** — `src/aet/plan_parser.py::validate_size()` no longer rejects a plan on task-list length. Intake stops enforcing a size proxy.
- **R-5** — The task-list-length-as-diff-proxy rationale is explicitly retracted in `docs/CONVENTIONS.md`, `skills/aet-plan/SKILL.md`, and `.agents/templates/plan-template.md`, with the measured correlation recorded so the proxy is not reintroduced a third time.
- **R-6** — An ADR records the governing decision: **plan size is measured after implementation, not gated before it**, because plan-time diff size is unknowable and every proxy for it has failed empirically.

### Ship-time measurement loop

- **R-7** — At task closure, the actual diff size is computed deterministically from the task record's `branch` and `merge_commit` against the merge base, and recorded on the task's history entry.
- **R-8** — The recorded actual is stored alongside the plan's declared `size` label so the two are comparable per task.
- **R-9** — The accumulated actuals are inspectable in aggregate (per label, with median/p90), so future threshold changes are derived from the recorded distribution rather than re-argued.
- **R-10** — Existing `.agents/work-history.jsonl` records (289 at time of writing) are backfilled where `merge_commit` is present, so the loop starts with history rather than from empty.

### Removing the bias toward small

- **R-11** — Subsystem coherence counts **implementation** subsystems only. Documentation and tests accompanying a change do not consume the subsystem budget.
- **R-12** — A plan is flagged oversized only when **two or more** signals trip, or when one trips and the planner cannot justify it — replacing the current any-one-of-five disjunction.
- **R-13** — A floor test is introduced, symmetric to the ceiling: a plan that does not stand alone as an independently shippable, reviewable behaviour change, or whose branch/PR/review overhead exceeds its diff, is merged with a sibling. This is not restricted to near-identical additions as the current Batching Rule is. The floor is **advisory**, matching the ceiling's 2-of-N rule (R-12): a plan that fails it is justified in writing, not blocked. Enforcement of either edge at plan time would contradict R-6 — plan-time size is unknowable, so a blocking floor would enforce a guess in the opposite direction from the one just retired.
- **R-14** — One-directional imperatives are removed. Specifically, "Split early, split often" (`skills/aet-plan/SKILL.md` Key Principles) is replaced with target-shaped framing that names the intended unit of work rather than only the ways to exceed it.

### Continuity

- **R-15** — The `⚠️ ATOMIC OVERSIZED` marker and its human-override semantics are preserved, including the `aet-implement` refusal behaviour and the unattended-mode hard stop.
- **R-16** — Existing plans remain valid. The change is forward-looking; no merged or approved plan is re-evaluated or re-labelled.
- **R-17** — `docs/prds/task-size-guardrails-revision-prd.md` carries a revision note pointing here and stating which of its premises was falsified.

## User Stories

- As a planner, I want size labels that match what the work actually costs, so that I am not writing a number I will predictably exceed by 2x (satisfies: R-1, R-2, R-3).
- As a planner, I want the guidance to name the unit of work I am aiming for rather than only the five ways to be too big, so that I stop defaulting to the smallest defensible slice (satisfies: R-12, R-13, R-14).
- As a planner, I want a change to carry its own tests and docs without spending its coherence budget, so that a normal vertical slice is not flagged for being complete (satisfies: R-11).
- As a maintainer, I want intake to stop enforcing a metric that does not predict what it claims, so that the one deterministic check is not theatre (satisfies: R-4, R-5).
- As a maintainer, I want actual delivered size recorded at closure, so that the next threshold argument is settled by the recorded distribution instead of intuition (satisfies: R-7, R-8, R-9, R-10).
- As a reviewer, I want plans that are neither artificially fragmented nor unbounded, so that each PR is a coherent unit worth its own review (satisfies: R-12, R-13, R-15).

## Acceptance Criteria

- [ ] `docs/CONVENTIONS.md`, `skills/aet-plan/SKILL.md`, and `.agents/templates/plan-template.md` state the recalibrated bands S ≤ 150 / M ≤ 600 / L > 600, consistently and without contradiction between files (satisfies: R-1).
- [ ] The story-level diff budget reads 1200 and the context budget reads ~60k/~100k in every location that states them (satisfies: R-2, R-3).
- [ ] `validate_size()` no longer returns a rejection based on task-list length, and its tests are updated to pin the new behaviour, including a case proving a long task list is accepted (satisfies: R-4).
- [ ] The measured correlation (r = 0.30, flat beyond ~6 lines) is recorded in `docs/CONVENTIONS.md` as the reason the proxy was retired (satisfies: R-5).
- [ ] A new ADR records "plan size is measured after implementation, not gated before it" with its consequences (satisfies: R-6).
- [ ] Closing a task writes the actual diff size, computed from `branch` + `merge_commit` against the merge base, to its `work-history.jsonl` entry (satisfies: R-7, R-8).
- [ ] An aggregate view reports actual diff distribution per declared label (median and p90 at minimum) (satisfies: R-9).
- [ ] Backfill populates actuals for existing history records that carry a `merge_commit`, and reports how many could not be resolved (satisfies: R-10).
- [ ] The subsystem-coherence rule states that docs and tests accompanying a change do not count toward the subsystem budget (satisfies: R-11).
- [ ] The oversize rule requires 2+ tripped signals, or 1 plus an unmet justification (satisfies: R-12).
- [ ] A floor test appears alongside the ceiling in `docs/CONVENTIONS.md` and `skills/aet-plan/SKILL.md`, not scoped to near-identical additions (satisfies: R-13).
- [ ] "Split early, split often" no longer appears in any skill or convention document; the replacement names the target unit of work (satisfies: R-14).
- [ ] `⚠️ ATOMIC OVERSIZED` handling in `aet-implement` and unattended mode is unchanged, verified by its existing tests still passing (satisfies: R-15).
- [ ] `aet queue sync` over the existing 264 plans reports no new validation failures introduced by this change (satisfies: R-16).
- [ ] `docs/prds/task-size-guardrails-revision-prd.md` carries a revision note naming the falsified premise (satisfies: R-17).
- [ ] `make validate` passes (satisfies: R-1 … R-17).

## Technical Notes

### Why plan-time gating cannot work

Two proxies have now been tried and both failed. The original model gated on file count; the 2026-07-21 revision replaced it with task-list length and asserted the latter tracked diff size. Measurement shows r = 0.30 with a flat relationship past six lines. This is not a calibration error to be fixed by a third proxy — the quantity being predicted (how much code a change will require) is not knowable from the document describing the change. Any replacement proxy inherits the same defect. The correct response is to stop gating on it and start measuring the real thing at the one moment it is known.

### Why the measurement is exact, not heuristic

The evidence in this PRD was gathered by matching commit subjects to plan ids, which is approximate. The production loop does not need that heuristic: `work-history.jsonl` already carries `merge_commit`, `plan_file`, and `merged_at` per task. At closure, `git diff <merge_commit>^1..<merge_commit>` yields the exact delivered diff for that task — for a squash merge the first parent is the trunk tip at merge time, and for a regular merge commit `^1` is the trunk side, so in both cases the range is precisely what the task contributed.

The measurement is deliberately anchored on `merge_commit` rather than on `branch` or on a merge base against the trunk ref. Three reasons: 267 of 289 existing records (92%) carry a `merge_commit` while only 167 (58%) carry a `branch`; branches are pruned after merge, so a branch-anchored measurement cannot backfill; and a merge-base-against-trunk computation would couple this work to `src/aet/branch_ref.py`, which does not exist yet (it is created by `epi-01-base-branch-resolver`, queued under an unrelated PRD). No new frontmatter and no new attribution scheme is required.

Diff accounting should exclude planning artifacts (`docs/`, `.agents/`) from the headline number, matching how the bands are defined, while retaining the total so the split is visible.

### Relationship to ADR-015

ADR-015 already establishes that telemetry informs documentation and guardrails, and keeps analysis local-first. The measurement loop is a direct instance of that decision, not a new capability class. It writes to existing local surfaces and introduces no external service.

### Band derivation

Proposed bands sit near the observed distribution rather than below it: S ≤ 150 against an observed S median of 81; M ≤ 600 against an M median of 405 and p90 of 836. Under the current M ≤ 200 bound, 29% of M plans fit their label; under 600, roughly three quarters do. The intent is that a label is a falsifiable prediction, which the measurement loop then checks.

### Scope shape

The doc/recalibration half (R-1 … R-5, R-11 … R-14, R-16, R-17) and the measurement half (R-7 … R-10) are separable and will likely land as distinct plans; R-6 gates the framing for both. The measurement half is the larger engineering lift.

### Dogfooding note

The plans implementing this PRD are themselves sized under the new model. If the recalibrated bands force an artificial split of this work, that is a signal the bands are still wrong and should be raised before adoption.

## Risks

- **Larger plans are harder to review.** Raising ceilings could produce PRs that are unwieldy in review even if they are coherent. Mitigated by the floor and ceiling moving together, by the 2-signal rule still catching genuinely multi-concern work, and by the measurement loop making the effect visible within a few cycles.
- **Removing the only mechanical gate leaves nothing automatic at intake.** In practice the gate has never fired in 264 plans, so the realised loss is zero; `⚠️ ATOMIC OVERSIZED`, the scope-validation stage, and human review remain.
- **The 2-signal rule adds planner discretion** at a moment when the project's stated direction is to reduce discretion. Accepted deliberately: discretion at plan time is unavoidable because the input is unknowable, and the loop moves the determinism to closure where it can be exact.
- **Post-revision sample is small.** The before/after comparison rests on n = 21, so it supports "loosening alone did not obviously work" rather than a strong causal claim. The recalibration rests on the 147-plan delivery sample, which is not affected by this limitation.
- **Backfill may be partial.** Older history records may lack a usable `merge_commit` or reference pruned branches; R-10 requires reporting the unresolved count rather than silently under-reporting.

## Open Questions

1. Should the recalibrated bands be fixed constants, or derived on a schedule from the recorded distribution once the loop has data? Fixed for this change is the safer default; automatic re-derivation risks a drift loop where thresholds chase whatever was last shipped.
2. Should thresholds become per-project configurable? The original PRD resolved this as "hardcoded for v1." Now that projects with different shapes use the toolkit, this may deserve revisiting — but not in this PRD.
3. ~~Where should the aggregate size report surface — `aet status`, the panel, or a dedicated subcommand?~~ **Resolved during scope validation (2026-07-23):** a dedicated noun-scoped group, `aet size report` / `aet size backfill`, per ADR-039. Folding it into `aet status` would put a distribution nobody asked for on every status call.
4. ~~Should the floor test (R-13) be advisory or blocking at scope validation?~~ **Resolved during scope validation (2026-07-23): advisory.** A blocking floor would enforce a plan-time judgement at exactly the point R-6 establishes is unknowable, and would be asymmetric with the ceiling, which R-12 simultaneously softens to 2-of-N. Both edges prompt a written justification; neither blocks. If fragmentation persists once the measurement loop has data, that is the evidence a future PRD would need to argue for teeth.
5. Should the headline diff number exclude test lines as well as docs? Tests are ~30% of measured volume; counting them keeps the incentive to write them, so the default here is to include them.

---

*Stage: scope-validated*
*Next step: run `aet-work` (single-plan or multi-task queue)*
