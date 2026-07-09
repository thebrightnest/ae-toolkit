---
id: frh-04-make-test-ruff-gate
size: M
blocked_by: []
pipeline: standard
---

# Plan: Wire pytest and ruff into `make validate`

## Context

- PRD: `docs/prds/fable-review-hardening-prd.md` (G3)

`make validate` (Makefile `validate` target) runs markdownlint, prettier-check, and skill-structure validation — it never runs the 272-test pytest suite and no Python linter exists in the repo. The repo lints markdown more rigorously than the Python that mutates state. Known latent finding: `orchestrator:229` annotates `list[Stage]` without importing `Stage` (survives only via `from __future__ import annotations`); `pipeline.py:139` binds `repo_root` and never uses it. `ruff` is already installed on the dev machine; runtime code stays stdlib-only — ruff is a dev-only tool.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Task List

1. Makefile: add `test` target (`python3 -m pytest tests/ -q`) and `lint-py` target (`ruff check .`, failing with an install hint if `ruff` is absent); append both to the `validate` target — S
2. Add `ruff.toml`: rules `E`, `F`, `I`; `target-version = "py310"`; exclude `content/`, `docs/`, `.agents/`; include the extensionless `bin/*` scripts via `extend-include` — S
3. Per-file ignores, each with a pointer comment to the plan that removes it: `aet-work/bin/orchestrator` (`F821` — `Stage` import lands via the frh-02 chain) and `aet-work/lib/pipeline.py` (`F841` — `_divergences_found` is rewritten by frh-11). Fix all findings in every other file (unused imports, import order) — M
4. `.pre-commit-config.yaml`: add a ruff hook (no pytest hook — 42s is too slow for commit-time) — S
5. Update `AGENTS.md` quality-gate description to mention `make test`/`lint-py` as part of `make validate` — S
6. Merge branch to main and verify integration — S

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] Not one of several near-identical additions
- [x] Diff expected to exceed 3 files or 50 lines
- [x] Cannot share a branch with related tasks (file-disjoint from the state chain by design — orchestrator/pipeline get ignores, not edits)

## Files to Modify

- `Makefile`
- `ruff.toml` (new)
- `.pre-commit-config.yaml`
- `AGENTS.md`
- Small lint fixes across `aet-work/lib/*.py`, `aet-work/bin/*`, `aet-evolve/bin/*`, `aet-ship/bin/ship`, `aet-setup/bin/configure-task-backend` (mechanical, import-level only)

## Validation Steps

- [ ] `make validate` now fails when a test is made to fail (spot-check by temporary mutation, then revert)
- [ ] `make validate` fails on a deliberate `F401` (spot-check, then revert)
- [ ] Full suite green: `make test`
- [ ] `ruff check .` exits 0
- [ ] No new source files → no new named tests required; the gate itself is validated by the two spot-checks above
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit; `validate` returns to markdown-only checks.

---

_Stage: implemented_
_Next step: run `aet-qa`_
