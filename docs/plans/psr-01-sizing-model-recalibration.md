---
id: psr-01-sizing-model-recalibration
size: M
blocked_by: []
pipeline: standard
status: queued
security_review: skipped
security_review_reason: threshold and prose changes plus removal of a size-proxy check; introduces no network, credential, subprocess, or filesystem-write surface
docs_sync: required
docs_sync_reason: changes the user-facing sizing guardrails documented in CONVENTIONS.md, both planning skills, and the plan template
---

# Plan: Recalibrate the sizing model and retire the plan-time size proxy

## Context

- PRD: `docs/prds/plan-sizing-recalibration-prd.md` (R-1 … R-6, R-11 … R-17)
- ADR: `docs/adr/046-plan-size-measured-not-gated.md` — the governing decision,
  authored during scope validation (see Locked design). This plan implements it.
- Supersedes: `docs/prds/task-size-guardrails-revision-prd.md` (adopted 2026-07-21)
- Related: ADR-006 (plan atomicity boundary — unchanged), ADR-015 (telemetry informs guardrails)

This plan changes the sizing model everywhere it is expressed: the numeric bands,
the framing that biases small, the dead validator check, and the ADR that records
why plan-time size gating was abandoned rather than re-proxied.

It is deliberately **one plan, not four**. The bands, the framing, the validator,
and the template all state the same model in different files; landing them
separately produces an intermediate state where the documented model contradicts
itself or the code. There is no ordering in which a partial adoption is coherent.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [ ] If a reproducible defect was described, redirected to `aet-bug-report`

The guardrails behave exactly as written; the written model is what is wrong.
Nothing here is a defect report.

## Locked design

- **Bands are set near the observed distribution, not below it.** S ≤ 150,
  M ≤ 600, L > 600 with explicit justification above 1500. Measured: S median 81,
  M median 405 / p90 836. Under the current M ≤ 200 bound only 29% of M plans fit
  their own label; under 600, roughly three quarters do.
- **The proxy is retired, not replaced.** `validate_size()` stops rejecting on
  task-list length and no new proxy takes its place. Two proxies (file count,
  then task-list length) have now failed; the measured correlation is r = 0.30
  with a flat relationship past ~6 lines. A third proxy inherits the same defect
  because plan-time diff size is not derivable from the plan document.
- **ADR-046 is already written; do not re-author it.** It was drafted during
  scope validation rather than left as a task here, because `aet sprint add`
  validates that every ADR a plan references resolves — a plan cannot enter the
  queue citing an ADR it intends to create. Treat the ADR as fixed input; this
  plan makes the docs and code agree with it.
- **The measured evidence goes in the repo, not just the PRD.** The correlation
  figure is recorded in `docs/CONVENTIONS.md` so the proxy is not reintroduced by
  a future revision that has forgotten why it was dropped.
- **Oversize becomes a 2-of-N rule.** One tripped signal is a prompt to justify,
  not an order to split. This is a deliberate increase in planner discretion,
  accepted because plan-time size is unknowable; the determinism moves to closure
  in `psr-02`.
- **Docs and tests ride free.** Subsystem coherence counts implementation
  subsystems only. A change that carries its own tests and documentation is one
  concern, not three.
- **The floor gets scope, not teeth.** The existing Batching Rule only rescues
  near-identical low-risk additions. It is replaced by a general floor test:
  a plan that does not stand alone as an independently shippable, reviewable
  behaviour change, or whose branch/PR/review overhead exceeds its diff, merges
  with a sibling. The floor is **advisory** — it prompts a written justification,
  it does not block at scope validation. This is deliberate symmetry with the
  2-of-N ceiling: both edges are plan-time judgements, and R-6 establishes that
  plan-time size is unknowable, so hard-enforcing either one re-creates the
  failure being retired. Do not implement it as a validator check.
- **`ATOMIC OVERSIZED` is untouched.** Its marker, the `aet-implement`
  refusal, and the unattended-mode hard stop keep their current semantics.
- **Do not write the emoji-prefixed marker literally in this plan.**
  `validate_size()` detects the marker by bare substring match over the whole
  file, so a plan that merely *discusses* the convention is treated as carrying
  it — which would trip the `aet-implement` refusal and demand an operator
  override for a plan that has no oversized task. This plan therefore refers to
  the marker by name only. The underlying detection defect is real but is a
  **reproducible defect, not part of this enhancement**; per intake triage it is
  routed to `aet-bug-report` rather than absorbed here.

## Task List

1. Update the `## Task Size Guardrails` section of `docs/CONVENTIONS.md`: new
   bands, story budget 1200, context budget ~60k/~100k, the retired-proxy note
   with the r = 0.30 evidence, implementation-only subsystem counting, the 2-of-N
   rule, and the advisory floor test replacing the Batching Rule — M
   (traces: R-1, R-2, R-3, R-5, R-11, R-12, R-13)
2. Update `skills/aet-plan/SKILL.md`: the Guardrail Model block, the Size Labels
   table, the `create-stories` and `plan` procedure steps that restate the
   numbers, and the Key Principles line — replacing "Split early, split often"
   with target-shaped framing that names the intended unit of work — M
   (traces: R-1, R-2, R-3, R-11, R-12, R-13, R-14)
3. Update `skills/aet-pipeline-plan/SKILL.md` so its guardrail reference and
   "Session-sized output" principle match, without duplicating the model — S
   (traces: R-1, R-14)
4. Update `.agents/templates/plan-template.md`: size definitions, the intake-limit
   sentence that cites the removed 300-line check, and the Batching Check block
   replaced by the floor test — S (traces: R-1, R-4, R-13)
5. Change `validate_size()` in `src/aet/plan_parser.py` to stop rejecting on
   task-list length, preserving the `ATOMIC OVERSIZED` warning signal in its
   return contract — S (traces: R-4, R-15)
6. Update `tests/queue/test_init_queue_sync.py` for the new validator behaviour,
   including a case pinning that a plan with a very long task list is accepted
   and a case pinning that `ATOMIC OVERSIZED` still surfaces — S
   (traces: R-4, R-15)
7. Add a revision note to `docs/prds/task-size-guardrails-revision-prd.md` naming
   the falsified premise and pointing to the new PRD — S (traces: R-17)
8. Cross-reference ADR-046 from the **Declared Size** entry in `CONTEXT.md` and
   from the retired-proxy note in `docs/CONVENTIONS.md`, so the decision is
   reachable from both the glossary and the guardrails — S (traces: R-6)
9. Run `aet queue sync` over the existing plan corpus and confirm no new
   validation failures are introduced — S (traces: R-16)
10. Merge branch to main and verify integration — S

**Size definitions (as proposed by this PRD, dogfooded here):**

- **S**: ≤ 2 hr human time / ≤ 150 expected diff lines
- **M**: ≤ 1 day human time / ≤ 600 expected diff lines
- **L**: > 600 lines — re-evaluate against the full model; justify above 1500

Expected diff ≈ 400–500 lines across docs, skills, one validator function, and
its tests (the ADR is already written, so it is not part of this diff). This is
**M** under the proposed bands. Under the current bands it
would be **L** and would have been force-split into four fragments that each
leave the documented model self-contradictory — which is the PRD's dogfooding
signal, recorded here deliberately.

### Floor Check

- [x] Stands alone as a shippable, reviewable behaviour change: after this lands,
      the documented model is coherent and the dead check is gone
- [x] Diff materially exceeds branch/PR/review overhead
- [x] Cannot be usefully merged with `psr-02`: that plan is runtime measurement
      code with no overlap in files or reviewers' concerns

## Rejected Alternatives

- **Split into four plans (bands / framing / validator / ADR)** — rejected: they
  edit the same four files, so parallel execution conflicts and serial execution
  produces intermediate states where CONVENTIONS.md, the skill, and the code
  disagree about the model.
- **Replace the task-list proxy with a files-to-modify or task-count proxy** —
  rejected: this is the third-proxy trap. The quantity being predicted is not
  derivable from the plan document; ADR-046 records this.
- **Keep the 300-line check as a warning instead of a rejection** — rejected:
  warning on a metric with r = 0.30 is noise that trains planners to ignore it.
- **Lower the bands instead and enforce them harder** — rejected: contradicted by
  measurement. 71% of M plans already exceed the current ceiling; the ceiling is
  not being under-enforced, it is wrong.
- **Make the bands per-project configurable now** — rejected: deferred by the PRD
  Non-Goals; adds a config surface before the measurement loop has data to
  justify per-project divergence.

## Files to Modify

- `docs/CONVENTIONS.md`
- `skills/aet-plan/SKILL.md`
- `skills/aet-pipeline-plan/SKILL.md`
- `.agents/templates/plan-template.md`
- `src/aet/plan_parser.py`
- `tests/queue/test_init_queue_sync.py`
- `docs/prds/task-size-guardrails-revision-prd.md`
- `CONTEXT.md`

## Validation Steps

- [x] Lint passes
- [x] Tests pass
- [x] `make validate` passes
- [x] New source coverage: no new source **file** is introduced; the changed
      function `validate_size()` is covered by `tests/queue/test_init_queue_sync.py`
      with (a) a unit test asserting a >300-line task list is accepted, and (b) a
      unit test asserting `ATOMIC OVERSIZED` is still reported in the return
      contract
- [x] Test types: both are unit tests on `plan_parser`; no integration or API
      boundary surface is touched
- [x] Cross-file consistency: the bands S ≤ 150 / M ≤ 600 / L > 600, the 1200
      story budget, and the ~60k/~100k context budget appear identically in
      `docs/CONVENTIONS.md`, `skills/aet-plan/SKILL.md`, and
      `.agents/templates/plan-template.md`, with no surviving reference to
      100/200/500 or 30k/50k
- [x] `grep -ri "split early, split often"` returns no hits in skills or convention
      documents (ADR-046 and the superseded PRD retain it as history)
- [x] The floor test is advisory: it is documented as prompting a justification and
      is **not** added to `validate_size()` or any other intake check (R-13)
- [x] The retired task-list-length proxy is gone from `docs/CONVENTIONS.md`, the
      planning skills, and `.agents/templates/plan-template.md` (merged plans and
      the superseded PRD retain the old wording as history)
- [x] `aet queue sync` over the existing plan corpus reports no new failures (R-16)
- [x] `aet-implement`'s `ATOMIC OVERSIZED` refusal and the unattended-mode hard
      stop are unchanged, verified by their existing tests still passing (R-15)
- [x] R-trace coverage: R-1 by tasks 1,2,3,4; R-2 by 1,2; R-3 by 1,2; R-4 by 4,5,6;
      R-5 by 1; R-6 by 8 (ADR-046 itself was authored during scope validation,
      because `aet sprint add` refuses a plan referencing an ADR that does not
      resolve — this task carries the cross-references); R-11 by 1,2; R-12 by 1,2;
      R-13 by 1,2,4; R-14 by 2,3; R-15 by 5,6; R-16 by 9; R-17 by 7.
      R-7 … R-10 are carried by `psr-02` and `psr-03`
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main` (task 10)

## Rollback Plan

Revert the commit. The validator change is a relaxation, so reverting re-tightens
an intake check that has never fired in 264 plans — no queued plan can be
invalidated by the rollback. The doc changes are text-only. ADR-046 would need its
status set to `Superseded` rather than deleted if the rollback is permanent.

## Pipeline

`standard`.

---

*Stage: implemented*
*Next step: run `aet-qa`*
