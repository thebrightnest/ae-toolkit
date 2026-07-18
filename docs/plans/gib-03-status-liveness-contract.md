---
id: gib-03-status-liveness-contract
size: M
blocked_by: []
pipeline: standard
status: draft
security_review: required
security_review_reason: makes `status` a required, validated intake field and changes how `init-queue` decides settled-ness. A wrong grandfathering rule either hard-fails the queue rebuild on legacy plans (the frh-17/18 failure mode) or admits terminal work as live; the intake gate is the correctness boundary and must be verified against the real 203-plan corpus.
docs_sync: required
docs_sync_reason: `status` becomes a required plan-frontmatter field with a defined lifecycle; the plan template, `aet-plan`, and CONTEXT.md document the contract and the grandfathering rule.
---

# Plan: Status Liveness Contract + Settled-From-Versioned-Data

## Context

- PRD: `docs/prds/github-issues-backlog-projection-prd.md` (R-6, R-7).
- **Ground truth (2026-07-17):** `plan_validate.py` has no concept of `status`. Corpus census: 203 plans — 81 `status: merged`, 1 draft, 1 approved, **121 with no `status` field at all**. `init-queue:257` derives settled-ness from `.agents/work-history.jsonl`, which `.gitignore:14` excludes — directly contradicting ADR-013 decision 3.
- The lifecycle vocabulary already exists (plan template comment): `draft → approved → queued → in_progress → awaiting_merge → merged → abandoned`. This task formalizes it; it does **not** invent new values.
- Enables gib-04 (membership derived from committed status).

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**; folds in the pre-existing ADR-013/init-queue contradiction as a scoped fix (R-7)

## Locked design

- **`status` required + validated.** `plan_validate` gains a check: frontmatter must carry `status` from the lifecycle set. **Grandfathering:** a plan with *no* `status` field is treated as settled (legacy corpus) and is exempt from the requirement; a plan *with* a `status` field must use a legal value. New plans (`aet-plan`, template) are born `status: draft`.
- **Approval ownership.** `draft → approved` is written by `aet-validate-scope` (the approval gate) when it advances the plan footer to `plan-approved` — resolving the PRD's open question. This keeps the frontmatter `status` and the footer stage moving together at the one point that already gates approval.
- **Settled = versioned.** `init-queue`/`sync` determine settled-ness from committed plan data: `status ∈ {merged, abandoned}` **or** no `status` field (legacy). The `.agents/work-history.jsonl` read at `:257` is removed from the settled decision (it may remain a reporting input elsewhere).
- **Grandfather guard is load-bearing.** A test runs the classifier over the real corpus and asserts exactly the 121 statusless + terminal plans are settled and the live ones are not — the frh-17/18 regression guard.

## Rejected Alternatives

- **Backfill `status` into all 121 legacy plans** — rejected (PRD Non-Goal): a 121-file migration that must be perfect, for zero present value; "no status field ⇒ settled" is safe because `status` postdates those plans.
- **Keep reading history for settled-ness** — rejected: gitignored and machine-local, so a second clone disagrees; contradicts ADR-013 decision 3 (R-7 exists to resolve this).
- **Add a new `status: sprint` value** (as the PRD wording implied) — rejected: `queued` already means "in the sprint" in the lifecycle; a parallel term fragments the vocabulary. Flagged for `aet-validate-scope` to ratify.

## Task List

1. `plan_validate`: require `status` from the lifecycle set; exempt statusless (legacy) plans — M (traces: R-6)
2. `init-queue`/`sync`: derive settled-ness from committed status (+ statusless=settled); drop the history read from the settled decision — M (traces: R-7)
3. `aet-plan` + `.agents/templates/plan-template.md`: emit/require `status: draft` at creation; document the lifecycle in CONTEXT.md — S (traces: R-6)
4. `aet-validate-scope`: write `status: approved` to frontmatter when advancing the footer to `plan-approved` — S (traces: R-6)
5. Tests: `tests/test_status_liveness_contract.py` (new), incl. the 203-plan corpus classifier guard — M (traces: R-6, R-7)

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] Not near-identical additions
- [x] Diff exceeds 3 files / 50 lines
- [x] Cannot share a branch — intake-contract surface

## Files to Modify

- `aet-work/lib/plan_validate.py`
- `aet-work/bin/init-queue`, `aet-work/bin/sync`
- `~/.claude/skills/aet-plan/SKILL.md` (repo copy), `.agents/templates/plan-template.md`, `CONTEXT.md`
- `tests/test_status_liveness_contract.py` (new)

## Validation Steps

- [ ] `make validate` passes; the existing suite passes with `status` required (fix any fixture plans that lack it)
- [ ] New source coverage — `tests/test_status_liveness_contract.py`:
  - `test_status_required_for_new_plan`
  - `test_statusless_legacy_plan_is_exempt_and_settled`
  - `test_illegal_status_value_rejected`
  - `test_settled_decision_ignores_history_log` (R-7)
  - `test_corpus_classifier_matches_known_live_set` (frh-17/18 guard over real `docs/plans/`)
- [ ] R-trace coverage: R-6 (t1, t3), R-7 (t2); no unknown R-ids
- [ ] Distinguish test types: unit (validator, classifier) + integration (init-queue rebuild with history absent)
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit. `status` reverts to optional; `init-queue` reverts to the history-based settled decision. Note: any plans created after this lands will carry `status: draft` harmlessly.

## Pipeline

`pipeline: standard` — intake-contract change with corpus-wide blast radius; standard grouping is warranted.

---

*Stage: reviewed*
*Next step: run `aet-cso`*
