# Plan: Update aet-ship Boundary Documentation

## Context

PRD: `docs/prds/aet-release-prep-prd.md`

Clarify the separation of concerns: `aet-ship` handles pre-merge validation and PR creation; `aet-release-prep` handles release documentation (changelog, product docs, version bump). Update `aet-ship` so users don't confuse the two.

## Tasks

1. Add a "Relationship to aet-release-prep" note to `aet-ship/SKILL.md` (or `aet-ship/references/` if SKILL.md is near 400-line limit)
2. Update `README.md` skill table to include `aet-release-prep` row with description and link
3. Ensure `aet-ship` description no longer implies it handles "changelog generation" for releases (it may generate local commit messages, but not project CHANGELOG.md)
4. Merge branch to main and verify integration — S

**Estimated size:** S (≤ 2 hr, ≤ 3 files, ≤ 50 lines)

## Dependencies

- `rp-03-write-skill-core` (need final skill description to reference)

## Validation Steps

- [ ] README table renders correctly with new row
- [ ] `aet-ship` documentation clearly distinguishes its scope from `aet-release-prep`
- [ ] `make lint` passes
- [ ] `make format-check` passes
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert `aet-ship/SKILL.md` and `README.md` to previous state.

---

_Stage: plan-approved_
_Next step: run `aet-pipeline-implement` or `aet-work`_
