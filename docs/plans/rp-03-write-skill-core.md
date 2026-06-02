# Plan: Write SKILL.md Core Workflow

## Context

PRD: `docs/prds/aet-release-prep-prd.md`
Script dependency: `aet-release-prep/release-prep.sh` (from rp-02)

Write the main skill instructions that guide an agent through release preparation.

## Tasks

1. Write the full `SKILL.md` body (replace skeleton from rp-01):
   - Step 1: Run the script and analyze output
   - Step 2: Confirm version bump with user
   - Step 3: Update `CHANGELOG.md` at repo root (append-only rules, format, guidelines)
   - Step 4: Update `PRODUCT.md` at repo root (triage user-facing vs internal, update evergreen sections, add "What's New")
   - Step 5: Bump version in detected source (package.json, VERSION file, or note for git tags)
   - Step 6: Provide release summary with next steps
2. Include edge cases: no tags, no commits, missing files
3. Keep file under 400 lines; move deep detail to `references/`
4. Merge branch to main and verify integration — S

**Estimated size:** M (≤ 1 day, 1 file, ≤ 200 lines of content)

## Dependencies

- `rp-01-scaffold-skill-structure`
- `rp-02-write-bash-script` (SKILL.md references the script path and output schema)

## Validation Steps

- [ ] `SKILL.md` is under 400 lines
- [ ] YAML frontmatter has trigger phrases (e.g., "prepare release", "update changelog", "release prep")
- [ ] Append-only rule for CHANGELOG is explicitly stated
- [ ] User-facing vs internal triage rule for PRODUCT.md is explicitly stated
- [ ] `make lint` passes
- [ ] `make format-check` passes
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Restore `SKILL.md` from rp-01 scaffold version.

---

_Stage: plan-approved_
_Next step: run `aet-pipeline-implement` or `aet-work`_
