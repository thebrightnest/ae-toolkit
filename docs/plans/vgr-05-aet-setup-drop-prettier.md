---
id: vgr-05-aet-setup-drop-prettier
size: S
blocked_by: []
pipeline: minimal
status: draft
security_review: skipped
security_review_reason: Edits scaffold prose/templates only; removes a formatter from generated config, adds no code path or surface.
docs_sync: skipped
docs_sync_reason: aet-setup's content *is* the scaffold/documentation being edited; there is no separate doc to sync.
---

# Plan: Drop Prettier from the aet-setup Scaffold

## Context

PRD: [validate-gate-review](../prds/validate-gate-review-prd.md). Satisfies **R-7**
(newly scaffolded repos inherit the slimmer gate — no prettier).

`aet-setup` scaffolds the same gates into downstream repos. `aet-setup/SKILL.md`
and `aet-setup/examples/illustrative-walkthrough.md` reference prettier /
`format-check`. If prettier is not worth it here, the scaffold should not install
it into new repos either. Independent of the other plans (different files), so it
may run in parallel.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Task List

1. `aet-setup/SKILL.md`: remove prettier from the scaffolded gate set (pre-commit config guidance + Makefile guidance); keep markdownlint as a staged-only check — S (traces: R-7)
2. `aet-setup/examples/illustrative-walkthrough.md`: update the walkthrough so it no longer shows prettier / `format-check` — S (traces: R-7)
3. Verify (see Validation Steps) and merge — S (traces: R-7)

**Size labels:** 2 files, ~25 diff lines → **S**.

## Batching Check

- [x] Not near-identical additions
- [ ] Diff expected to exceed 3 files or 50 lines — **no** (2 files, small)
- [x] Independent scaffold files; cannot share a branch with the Makefile/docs plans

(Small and self-contained; kept as its own plan because it targets a distinct blast
radius — downstream repos — that the owner chose to fold into this pipeline.)

## Rejected Alternatives

- **Defer to a follow-up pipeline** — considered; owner chose to include propagation now so the scaffold matches this repo's slimmer gate immediately.

## Files to Modify

- `aet-setup/SKILL.md`
- `aet-setup/examples/illustrative-walkthrough.md`

## Validation Steps

- [ ] `grep -rniE 'prettier|format-check' aet-setup/` returns no live scaffolding references (only intentional historical mentions, if any, remain and are called out)
- [ ] Confirm no other aet-setup scaffold template (e.g., an embedded `.pre-commit-config`/Makefile snippet) still injects prettier
- [ ] The walkthrough reads coherently with markdownlint-only gating
- [ ] **No new source modules** — scaffold content is template/doc, exercised by the aet-setup skill flow, not pytest; verified by the grep above
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

**Self-consistency lint:** Check 1 PASS · Check 2 (SKILL.md=t1, walkthrough=t2) PASS · Check 3 (observable via grep) PASS · Check 4 (R-7 covered) PASS.

## Rollback Plan

`git revert` the commit; the two scaffold files return to installing prettier.

## Pipeline

`minimal` — small template/doc edits; all stages fit one session.

---

_Stage: implemented_
_Next step: run `aet-qa`_
