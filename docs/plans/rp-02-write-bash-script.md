# Plan: Write release-prep.sh Bash Script

## Context

PRD: `docs/prds/aet-release-prep-prd.md`
Original logic: `/Users/pedrorocha/Work/manager/.claude/skills/release-prep/release-prep.js`

Convert the Node.js commit analyzer into a POSIX-compatible shell script that lives inside the skill directory.

## Tasks

1. Write `aet-release-prep/release-prep.sh`:
   - Detect version source: `package.json` → `VERSION` file → `git describe --tags --abbrev=0`
   - Get commits since last tag (or all commits if no tags)
   - Classify commits by conventional commit prefix and keyword fallback
   - Detect breaking changes (`BREAKING CHANGE` in body, `!` in type)
   - Suggest semantic bump (major → minor → patch)
   - Calculate next version (handle prerelease suffixes)
   - Group commits by type for changelog formatting
   - Output JSON matching the original Node.js schema
2. Make script executable (`chmod +x`)
3. Test manually against current repo's git history
4. Merge branch to main and verify integration — S

**Estimated size:** M (≤ 1 day, ≤ 5 files, ≤ 200 lines)

## Dependencies

- `rp-01-scaffold-skill-structure` (directory must exist)

## Validation Steps

- [ ] Script runs without errors: `./aet-release-prep/release-prep.sh | jq .`
- [ ] Output contains: `lastTag`, `currentVersion`, `commits`, `suggestedBump`, `nextVersion`, `groupedCommits`
- [ ] Commit classification matches original Node.js behavior for sample commits
- [ ] Stack detection picks correct source when multiple exist
- [ ] `make validate` passes (skill structure)
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

`git rm aet-release-prep/release-prep.sh` and commit.

---

_Stage: plan-approved_
_Next step: run `aet-pipeline-implement` or `aet-work`_
