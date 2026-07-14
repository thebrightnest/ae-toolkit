---
id: vgr-02-gate-docs-adr
size: M
blocked_by:
  - vgr-01-slim-markdown-gates
pipeline: minimal
status: draft
security_review: skipped
security_review_reason: Documentation and an ADR only; no code, dependency, or security surface.
docs_sync: skipped
docs_sync_reason: This plan's deliverable *is* the documentation and decision record; there is no downstream doc to sync.
---

# Plan: Gate Documentation + ADR-026

## Context

PRD: [validate-gate-review](../prds/validate-gate-review-prd.md). Satisfies **R-4**
(docs describe the post-change gates with no stale references; ADR-026 records the
decision, retained-validator rationale, and the pytest-xdist trade-off).

Blocked by vgr-01 so the docs describe the gate behavior that actually landed, and
because both plans would otherwise contend for `AGENTS.md`. `AGENTS.md:105`
currently calls _formatting_ part of the quality surface — that line must be
revised, not just appended to.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Task List

1. `AGENTS.md`: update the `make` command table — drop `format-check`; note `lint` is a manual/staged-only markdownlint — S (traces: R-4)
2. `AGENTS.md`: revise the "Trimmed tooling … structure and formatting" rationale (line 105) — formatting (prettier) is dropped as churn; the quality surface is structure + semantics (validate-skills, skills-lint, validate-workflows) + code (ruff, pytest), with markdownlint a light staged-only guard — S (traces: R-4)
3. `docs/CONVENTIONS.md` pre-commit section (~276–284): markdownlint (staged) + secrets scan; drop the `format-check` bullet; change the fallback line to `make lint` only — S (traces: R-4)
4. Create `docs/adr/026-slim-markdown-quality-gates.md` from `docs/adr/000-template.md` (Status: Accepted; Context = measured cost profile + cosmetic-vs-real; Decision = drop prettier, slim+pin markdownlint, fail-fast reorder, keep real validators; Consequences = lost yaml/json cosmetic formatting + the pytest-xdist dependency trade-off from vgr-04 + the ADR-025 interaction [markdown lint now lives at pre-commit, so `make validate`'s `LINT_ONLY` freshness path no longer re-lints markdown — acceptable, pre-commit covers staged files]; Alternatives = drop-both, keep-and-fix) and add its row to `docs/adr/README.md` — S (traces: R-4)
5. Verify (see Validation Steps) and merge — S (traces: R-4)

**Size labels:** 4 files (AGENTS.md, CONVENTIONS.md, new ADR, adr/README.md), ~90 diff lines → **M**.

## Batching Check

- [x] Not near-identical additions
- [x] Diff spans 4 files / >50 lines
- [x] Deliberately separated from vgr-01 to keep that slice ≤ 5 files

## Rejected Alternatives

- **Leave `AGENTS.md:105` as-is and only edit the command table** — rejected: the "structure and formatting" line would then contradict the shipped decision (merit over sunk cost).
- **Skip the ADR** — rejected: gate changes are decision-worthy in this repo (cf. ADR-019, ADR-025); the xdist trade-off in particular needs a durable record.

## Files to Modify

- `AGENTS.md`
- `docs/CONVENTIONS.md`
- `docs/adr/026-slim-markdown-quality-gates.md` (new)
- `docs/adr/README.md`

## Validation Steps

- [ ] `grep -rn format-check AGENTS.md docs/CONVENTIONS.md` returns nothing
- [ ] `AGENTS.md:105` no longer claims formatting is part of the quality surface
- [ ] `docs/adr/026-*.md` exists with Status: Accepted and is listed in `docs/adr/README.md`
- [ ] **No new source modules** — docs/ADR are not pytest-covered; correctness verified by the grep above
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

**Self-consistency lint:** Check 1 PASS · Check 2 (AGENTS.md=t1/2, CONVENTIONS.md=t3, ADR+README=t4) PASS · Check 3 (observable via grep) PASS · Check 4 (R-4 covered) PASS.

## Rollback Plan

`git revert` the commit; delete the new ADR and its README row.

## Pipeline

`minimal` — docs-only; all stages fit one session.

---

_Stage: plan-approved_
_Next step: run `aet-work`_
