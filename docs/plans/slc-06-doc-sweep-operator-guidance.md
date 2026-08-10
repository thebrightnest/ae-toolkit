---
id: slc-06-doc-sweep-operator-guidance
size: M
work_class: trivial
blocked_by:
  - slc-03-frontmatter-status-removal
  - slc-04-mechanical-closure-transaction
  - slc-05-set-stage-gate-submit-atomicity
pipeline: minimal
security_review: skipped
security_review_reason: prose-only change; no code, auth, data, or dependency surface
docs_sync: required
docs_sync_reason: this plan IS the docs sync — the R-10 corpus sweep
---

# Plan: R-10 Doc Sweep — CONTEXT.md, Skills Corpus, and Multi-Machine Operator Guidance

## Context

PRD: `docs/prds/single-ledger-closure-prd.md` (R-10). ADR-055. The lop
precedent (R-10 there): every document instructing superseded behavior is
corrected in the same change family, because the skills are symlinked and
live — a stale instruction keeps producing the old workflow. This plan runs
after the behavior lands (slc-03/04/05) so docs are rewritten against real
code, never ahead of it.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. [x] CONTEXT.md rewrite: mint the **Provenance Ledger** term; rewrite **Status
   (plan lifecycle)**, **Work Queue / Sprint Board** (membership is the
   explicit sprint-add record), **Plan File** (source of truth for intent;
   terminal closure lives in the ledger), and the closure bullet in
   Relationships; fix the casual "ledger record" in **Per-Task Cost**;
   collapse the eight-store flagged ambiguities that R-1/R-9 resolved — M
   (traces: R-10)
2. [x] Skills corpus sweep: completion-protocol and footer-write duties not
   already deleted by slc-05 (~remaining instances from the study's 19
   across 10 skills), the aet-plan frontmatter contract, aet-validate-scope's
   completion protocol and its stale "sprint add requires committed plans"
   note, aet-pipeline-plan step 3 — M (traces: R-10)
3. [x] AGENTS.md: update the state-model references (ADR-039 taxonomy line and
   the decision log entry for ADR-054) to cite ADR-055 — S (traces: R-10)
4. [x] Operator guidance for the multi-machine posture: state travels via
   `refs/aet/*` on origin; a fresh clone fetches it; `~/.aet` stays
   machine-local; offline work is safe and closure is the syncing
   boundary — S (traces: R-10)
5. [ ] Merge branch to main and verify integration — S

### Floor Check

- [x] Stands alone: a single reviewable "docs now describe the new world"
  change. Splitting it per-file would create doc/code skew windows between
  PRs — the exact defect class it exists to close.
- [x] M label is justified by breadth (CONTEXT.md + ~10 skills + AGENTS.md),
  not depth; `pipeline: minimal` because no code paths change (advisory
  default satisfied on risk, not size).

## Rejected Alternatives

- **Update CONTEXT.md during scope validation** (the aet-validate-scope
  default) — rejected: CONTEXT.md must describe code as it is; rewriting it
  before slc-03/04/05 land recreates the doc-vs-code contradiction class
  this PRD kills. Resolved terms live in ADR-055 until this plan runs.
- **Per-skill PRs** — rejected: floor test; the sweep is one coherent
  behavior and splitting it opens skew windows.

## Files to Modify

- `CONTEXT.md`
- `AGENTS.md`
- `skills/*/SKILL.md` (per the study's duty map, residual after slc-05)
- `skills/aet-plan/SKILL.md`, `skills/aet-validate-scope/SKILL.md`,
  `skills/aet-pipeline-plan/SKILL.md`
- `.agents/templates/plan-template.md` (comment cleanup post-slc-03)
- `docs/CONVENTIONS.md`

## Validation Steps

- [x] `make lint` passes
- [x] `aet docs lint` passes
- [x] `grep -rn "status: draft\|frontmatter.*status\|commit the plan files\|
  requires.*committed" skills/ docs/ AGENTS.md CONTEXT.md` returns only
  historical records (docs/adr/, CHANGELOG.md) and the aet-plans-lint error
  description (structural)
- [x] Every behavior claim in the rewritten CONTEXT.md is verifiable against
  merged slc-01..05 code (manual review checklist in the PR)
- [x] R-trace coverage: R-10 covered by tasks 1–4
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge. Prose-only; no data or state involved.

## Pipeline

`minimal` — prose-only change; no isolation benefit per ADR-047's telemetry.

---

*Stage: implemented*
*Next step: run `aet-qa`*
