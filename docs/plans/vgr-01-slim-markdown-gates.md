---
id: vgr-01-slim-markdown-gates
size: M
blocked_by: []
pipeline: standard
status: merged
security_review: skipped
security_review_reason: Removes only cosmetic markdown gates (prettier, all-files markdownlint); detect-private-key and every real validator are retained — no auth, secret, or input-handling surface changes.
docs_sync: skipped
docs_sync_reason: Gate documentation (AGENTS.md, CONVENTIONS.md) and the ADR are delivered by the dependent plan vgr-02-gate-docs-adr.
---

# Plan: Slim the Markdown Gates + Fail-Fast Reorder `make validate`

## Context

PRD: [validate-gate-review](../prds/validate-gate-review-prd.md). Satisfies **R-1**
(prettier out of all gates), **R-2** (markdownlint pinned + staged-only, drift
removed), **R-3** (fail-fast `make validate` order).

Prettier (10.27s) and markdownlint (5.07s) sweep all 454 tracked `.md` files at
commit, `make validate`, and push while catching zero structural defects. The
Makefile also runs an _unpinned_ `npx markdownlint-cli2` while pre-commit pins
`v0.17.2` — the two paths can disagree. And `make validate` runs pytest (92s)
before the sub-second high-signal checks.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] The latent drift bug (R-2) is folded in here as a correctness item, not a separate bug report

## Task List

1. Remove the `mirrors-prettier` hook block (lines 13–17) from `.pre-commit-config.yaml` — S (traces: R-1)
2. `Makefile`: pin the `lint` target to `npx markdownlint-cli2@0.17.2` (match the pre-commit rev) and remove `make lint` from the `validate` target — S (traces: R-2)
3. `Makefile`: remove the `format-check` target; keep `format` as a manual-only prettier convenience wired into no gate; update `.PHONY` — S (traces: R-1)
4. `Makefile`: reorder `validate` to `lint-py` → `validate-workflows` → `skills-lint` → `validate-skills.sh` → `test` (pytest last); update the `validate` doc comment — S (traces: R-3)
5. `scripts/hooks/pre-commit`: fallback (lines 12–14) drops `make format-check`, keeps `make lint`; fix the header comment (line 5) — S (traces: R-1, R-2)
6. Verify (see Validation Steps) and merge to main — S (traces: R-1, R-2, R-3)

**Size labels:** S ≤ 3 files / ≤ 100 lines. This plan is 3 files, ~35 diff lines → **M** (behavioral change to commit/validate/push semantics warrants the higher label).

## Batching Check

- [x] Not one of several near-identical additions
- [x] Diff spans 3 files (config + Makefile + hook) — one cohesive behavioral slice
- [x] Cannot share a branch with vgr-02 (docs) without tripping the L split trigger

## Rejected Alternatives

- **Drop markdownlint entirely too** — rejected: a pinned staged-only lint is near-zero cost and prevents heading/list drift across 454 docs; owner chose to keep it.
- **Keep prettier with a `.prettierignore`/config** — rejected: still auto-rewrites staged files (the core friction) and adds ~10s of cosmetic sweep for zero defect-catching.
- **Fold docs + ADR into this plan** — rejected: pushes it to 6 files (L split trigger); the docs form a coherent decision-record slice (vgr-02).

## Files to Modify

- `.pre-commit-config.yaml`
- `Makefile`
- `scripts/hooks/pre-commit`

## Validation Steps

- [ ] `pre-commit run --all-files` succeeds and prettier no longer appears in the run
- [ ] `make validate` runs green; markdownlint/prettier do **not** execute; output order is `lint-py → validate-workflows → skills-lint → validate-skills.sh → test`
- [ ] Staging a deliberately mis-wrapped `.md` and committing rewrites nothing and runs only markdownlint on the staged file
- [ ] Breaking a documented `aet` command reference makes `make validate` fail at `skills-lint` in <1s (before pytest)
- [ ] `grep -n markdownlint-cli2 Makefile` shows the version pinned to the pre-commit rev
- [ ] **No new source modules introduced** — changes are build/hook config, verified by the manual gate checks above (not pytest-covered)
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

**Self-consistency lint:** Check 1 (prose→tasks) PASS · Check 2 (files→tasks: config=t1, Makefile=t2/3/4, hook=t5) PASS · Check 3 (observable AC) PASS · Check 4 (R-trace R-1/R-2/R-3 covered, no unknown R) PASS.

## Rollback Plan

`git revert` the commit, or `git checkout` the three files. Single change, no data migration.

## Pipeline

`standard` — config/hook change with commit/validate/push impact; default grouping.

---

_Stage: merged_
_Next step: run `aet-work`_
