# Plan: Write References and Examples

## Context

PRD: `docs/prds/aet-release-prep-prd.md`
SKILL.md core: `rp-03-write-skill-core` (deep detail moved out to here)

Populate `references/` and `examples/` with supporting documentation so SKILL.md stays under 400 lines.

## Tasks

1. Write `aet-release-prep/references/COMMIT-CLASSIFICATION.md`:
   - Full classification table with regex patterns and examples
   - Breaking change detection rules
   - Keyword fallback rules
2. Write `aet-release-prep/references/PRODUCT-TEMPLATE.md`:
   - Scaffold template for first-time `PRODUCT.md` creation
   - "What's New" section format
   - Evergreen feature section format
3. Write `aet-release-prep/references/EDGE-CASES.md`:
   - No tags exist
   - No commits since last tag
   - `CHANGELOG.md` or `PRODUCT.md` missing
   - Only internal commits (no user-facing changes)
4. Write `aet-release-prep/examples/minor-release.md`:
   - End-to-end example with sample script output and agent actions
5. Write `aet-release-prep/examples/patch-release.md`:
   - End-to-end example for a bug-fix-only release
6. Merge branch to main and verify integration — S

**Estimated size:** M (≤ 1 day, ≤ 5 files, ≤ 200 lines)

## Dependencies

- `rp-01-scaffold-skill-structure`
- `rp-03-write-skill-core` (references expand on topics introduced in core)

## Validation Steps

- [ ] All relative links from `SKILL.md` to `references/` and `examples/` resolve
- [ ] `make lint` passes on all new markdown files
- [ ] `make format-check` passes
- [ ] `scripts/validate-skills.sh` passes for `aet-release-prep/`
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

`git rm -rf aet-release-prep/examples/ aet-release-prep/references/` and commit.

---

_Stage: plan-approved_
_Next step: run `aet-pipeline-implement` or `aet-work`_
