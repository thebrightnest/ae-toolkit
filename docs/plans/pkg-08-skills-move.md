---
id: pkg-08-skills-move
size: L
blocked_by:
  - pkg-05-panel-extraction
  - pkg-06-cross-skill-extraction
pipeline: standard
status: queued
security_review: skipped
security_review_reason: Content-only relocation plus validator/Makefile path updates; no runtime behavior or dependency changes.
docs_sync: required
docs_sync_reason: README skill table, CONVENTIONS.md project structure, and AGENTS.md directory layout all describe skill locations and must move in lockstep.
---

# Plan: Move Skills to `skills/` (A3)

## Context

PRD: `docs/prds/aet-package-extraction-prd.md` (R-5,
R-11). With all code extracted (pkg-03/04/05/06), skill directories are pure
content. Move them under `skills/`, update every path-owning tool, and add the
validator rule that keeps skills code-free permanently. The
`npx skills add ... --all` discovery path must be verified working against the
new layout before this plan is considered done.

> **⚠️ ATOMIC OVERSIZED — requires explicit user approval.**
> ~20 skill directories plus validator/Makefile/README/CONVENTIONS/AGENTS
> updates exceed the file guardrail. Splitting per-skill produces 20 identical
> PRs and leaves the validator pointing at a half-moved tree; the move is only
> coherent as one sweep. Rename-dominated diff.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. Verify `npx skills add` discovery semantics against a `skills/` subdir
   (read the CLI's discovery docs/source; if root-only discovery is found,
   STOP and re-plan — record the finding either way in the PR description) — S
   (traces: R-5)
2. `git mv aet-* skills/` for all skill directories — M (traces: R-5)
3. Add validator rule to `scripts/validate-skills.sh`: skill directories must
   contain no executable code (no `.py`, no `.sh`, no `bin/`, no `lib/` —
   `.example` content assets exempt); update skill discovery root to
   `skills/`; update fixtures — M (traces: R-5)
4. Update `Makefile` (`SKILLS_DIR`, `install-skills`, `add-skill`),
   `scripts/skills-lint`, and `tests/fixtures/**` paths — M (traces: R-5)
5. Update `README.md` skill table links, `docs/CONVENTIONS.md` project
   structure, `AGENTS.md` directory structure, and any cross-skill relative
   links flagged by the validator — M (traces: R-11)
6. Fresh-install verification: `make install-skills` symlinks from `skills/`;
   all skills resolve in `~/.agents/skills/`; document the `npx skills add`
   check from task 1 — S (traces: R-5)
7. Merge branch to main and verify integration — S

**Size definitions:**

- **S**: ≤ 2 hr human time / ≤ 3 files / ≤ 100 diff lines
- **M**: ≤ 1 day human time / ≤ 5 files / ≤ 200 diff lines
- **L**: > 1 day OR > 5 files OR > 200 lines — **must be split before implementation**

### Batching Check

- [x] One coherent tree move; validator + docs must change in the same commit
  or `make validate` is red on main between steps.

## Rejected Alternatives

- **Per-skill move plans** — rejected: 20 identical PRs; the validator cannot
  pass on a half-moved tree without temporary dual-root support, which is more
  complexity than the move itself.
- **Keep skills at root** — rejected: PRD G2 and the roadmap decision; root
  mixing of content and platform is the original problem.

## Files to Modify

- `aet-*/` → `skills/aet-*/` (all skill directories)
- `scripts/validate-skills.sh`
- `scripts/skills-lint`
- `Makefile`
- `tests/fixtures/**` (skill-path fixtures)
- `tests/test_validate_skills.py`, `tests/test_skills_lint.py`
- `README.md`, `docs/CONVENTIONS.md`, `AGENTS.md`

## Validation Steps

- [ ] `make validate` green from a clean checkout
- [ ] New validator rule proven: a fixture skill containing a `.py` file fails
  `validate-skills.sh` (named test: `tests/test_validate_skills.py` case added
  for the no-code rule — the one new test this plan introduces, covering the
  new validator rule in `scripts/validate-skills.sh`)
- [ ] `tests/test_validate_skills.py`, `tests/test_skills_lint.py` (named,
  existing) pass against updated fixtures
- [ ] `make install-skills` produces working symlinks; `aet status` runs from
  an installed skill dir
- [ ] `npx skills add` discovery result documented in the PR description
  (acceptance criterion R-5)
- [ ] R-trace coverage: R-5 by tasks 1–4, 6; R-11 by task 5; no unknown R-ids
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

`git revert` the merge; symlinks under `~/.agents/skills/` may need one
`make install-skills` re-run to repoint at the restored root-level dirs
(reversible, documented in the PR).

---

*Stage: plan-approved*
*Next step: run `aet-work`*
