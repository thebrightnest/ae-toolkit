# Plan: Scaffold aet-release-prep Skill Structure

## Context

PRD: `docs/prds/aet-release-prep-prd.md`

Create the directory structure, YAML frontmatter, and placeholder content for the new skill. This is the foundation everything else builds on.

## Tasks

1. Create `aet-release-prep/` directory with `examples/` and `references/` subdirectories
2. Write `aet-release-prep/SKILL.md` with:
   - Valid YAML frontmatter (`name`, `description` with trigger phrases, `category`)
   - Skeleton markdown body with section headers (Steps 1-6)
   - Placeholder references to the bash script and deep-dive docs
   - Keep under 400 lines
3. Add `.skill` entry to `.gitignore` if not already present (should already be there)
4. Merge branch to main and verify integration — S

**Estimated size:** S (≤ 2 hr, ≤ 3 files, ≤ 100 lines)

## Dependencies

None — can start immediately.

## Validation Steps

- [ ] `ls aet-release-prep/{SKILL.md,examples/,references/}` succeeds
- [ ] YAML frontmatter parses correctly
- [ ] `make lint` passes on SKILL.md
- [ ] `make format-check` passes
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

`git rm -rf aet-release-prep/` and commit.

---

_Stage: plan-approved_
_Next step: run `aet-pipeline-implement` or `aet-work`_
