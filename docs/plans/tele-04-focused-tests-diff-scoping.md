---
id: tele-04-focused-tests-diff-scoping
size: M
blocked_by: []
---

# Plan: Focused Tests & Diff Scoping

## Context

- PRD: `docs/prds/aet-telemetry-learning-prd.md`

The reviewed run spent time on four full Vitest suite runs and on review/CSO deliberation over project-level diff noise. This plan updates skill instructions to run tests selectively and to scope review/CSO to the actual branch diff.

This is an enhancement to the toolkit's own tooling, not a reproducible defect report.

## Task List

1. Update `aet-implement/SKILL.md` validation strategy — S
   - Run focused tests while iterating.
   - Run the full suite once before the final commit.
2. Update `aet-qa/SKILL.md` test strategy — S
   - Run impact-scoped tests first (files touched by the diff).
   - Run the full suite only when core framework files changed.
3. Update `aet-review/SKILL.md` — S
   - Compute the PR base (`origin/main` or parent branch) and review `git diff <base>..HEAD`.
   - Ignore noise from `.gitignore` and `AGENTS.md` unless the task explicitly touches them.
   - Downgrade first-party mock concerns to `flag-for-human` unless no integration boundary test exists.
4. Update `aet-cso/SKILL.md` with the same PR-base and noise-filter guidance — S
5. Run `make validate` — S

## Files to Modify

- `aet-implement/SKILL.md`
- `aet-qa/SKILL.md`
- `aet-review/SKILL.md`
- `aet-cso/SKILL.md`

## Validation Steps

- [ ] `make validate` passes.
- [ ] `make package` regenerates `.skill` files including the updated instructions.
- [ ] Each skill file remains under 400 lines after edits.
- [ ] Each new source file introduced by this plan has a named test or validation step covering it.
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the skill markdown changes and re-run `make package`.

---

_Stage: plan-approved_
_Next step: run `aet-work`_
