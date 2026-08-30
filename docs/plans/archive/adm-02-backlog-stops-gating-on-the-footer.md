---
id: adm-02-backlog-stops-gating-on-the-footer
size: S
work_class: normal
blocked_by:
  - adm-01-single-admission-operation
pipeline: standard
security_review: skipped
security_review_reason: Removes a check that admits every plan written from the template; touches no auth, data or trust boundary.
docs_sync: required
docs_sync_reason: Changes the Plan Backlog glossary entry's accuracy.
---

# Plan: Backlog Stops Gating on the Footer

## Context

PRD: docs/prds/single-admission-path-prd.md
Decision: ADR-066 (Board Admission Has One Path), Alternative 5 and the
Consequences entry on `aet backlog add`.

`aet backlog add` (`src/aet/cli/backlog.py:64`) refuses a plan whose footer
stage is outside `_BACKLOG_STAGES = {"plan-draft", "plan-approved"}`. That set
spans the entire authoring lifecycle, so any plan written from the template
passes: the check gates nothing while costing the ADR-019 decision-4 audit a
permanent exception to reason about.

This is deliberately a separate plan from `adm-01`. The backlog is not the
board, the case is the contestable one, and keeping it separable means it can be
reverted without disturbing the admission operation.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] This is the disposition ADR-066 Alternative 5 weighed and recorded, not a
      defect report

## Task List

1. Remove the footer stage gate and `_BACKLOG_STAGES` from `_add`, keeping the
   plan-resolution failure path that reports a missing plan — S (traces: R-6)
2. Verify no admission or backlog gating branch reads `stage_from_plan`, and
   that the remaining call sites are the display reader in `gate.py`, the
   reporting readers in `context.py`, and the post-record fallback in
   `verifier.py` — S (traces: R-6, R-7)
3. Correct the **Plan Backlog** glossary entry in `CONTEXT.md`, which says
   "Approved plans in `docs/plans/`" and is no longer accurate — S
   (traces: R-12)
4. Regression test: a footerless plan is accepted by `aet backlog add` — S
   (traces: R-6)
5. Merge branch to main and verify integration — S

### Floor Check

- [x] Expected diff is below the calibrated floor threshold (≤ 50 headline lines)
- [ ] The change is limited to one subsystem and maintains no architectural invariant
- [ ] `Files to Modify` substantially overlaps a sibling it is ordered against
- [ ] This is docs-only and its sole consumer is a single sibling

One box checked, so the shape is justified in writing: this plan is what makes
ADR-066's audit property hold *without exception*, which is an architectural
invariant rather than a local cleanup, and it touches `backlog.py`, which
`adm-01` does not open. Merging it into `adm-01` would bury a contestable
decision inside a structural change and make the two inseparable on revert.

## Rejected Alternatives

- **Leave the footer read as a legitimate Author-phase read** — rejected on a
  narrower argument than the pre-intake one, which is genuinely defensible: the
  check accepts the whole authoring lifecycle, so it gates nothing. ADR-066
  Alternative 5.
- **Replace the stage gate with a frontmatter-contract check** — rejected for
  this plan: it would add a gate where the PRD's finding is that the existing
  one is vacuous. If backlog should validate, that is its own decision with its
  own evidence, not a substitution made in passing.
- **Fold into `adm-01`** — rejected: see the Floor Check justification.

## Files to Modify

- `src/aet/cli/backlog.py`
- `CONTEXT.md`
- `tests/cli/test_backlog.py`

## Validation Steps

- [ ] Lint passes
- [ ] Tests pass
- [ ] R-trace coverage: every in-scope R-id is covered by ≥ 1 task or explicitly deferred with a reason; no task cites an unknown R-id
- [ ] No new source file is introduced by this plan
- [ ] `grep -rn "stage_from_plan" src/` returns only the display, reporting and fallback readers
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the commit; `_BACKLOG_STAGES` and its gate return. Nothing depends on the
gate's absence except ADR-066's exception-free phrasing, which would revert to
carrying one documented exception.

## Pipeline

`standard`.

---

_Stage: plan-approved_
