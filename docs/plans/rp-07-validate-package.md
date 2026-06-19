---
id: rp-07-validate-package
blocked_by:
  - rp-02-write-bash-script
  - rp-03-write-skill-core
  - rp-04-write-references-examples
  - rp-05-update-aet-ship-boundary
  - rp-06-write-adr
size: S
---

# Plan: Validate and Package aet-release-prep

## Context

PRD: `docs/prds/aet-release-prep-prd.md`
Final integration step: ensure the new skill passes all quality gates and is packaged correctly.

## Tasks

1. Run `make lint` — verify all markdown in `aet-release-prep/` passes
2. Run `make format-check` — verify prettier formatting
3. Run `make validate` — run full validation suite including `scripts/validate-skills.sh`
4. Run `make package` — generate `aet-release-prep.skill` zip archive
5. Verify `aet-release-prep.skill` exists and contains expected files
6. Run `make install-skills` (optional) — symlink to `~/.claude/skills/`
7. Merge branch to main and verify integration — S

**Estimated size:** S (≤ 2 hr, 0 new files, ≤ 20 lines of changes if fixes needed)

## Dependencies

- `rp-01-scaffold-skill-structure`
- `rp-02-write-bash-script`
- `rp-03-write-skill-core`
- `rp-04-write-references-examples`
- `rp-05-update-aet-ship-boundary`
- `rp-06-write-adr`

## Validation Steps

- [ ] `make lint` passes with zero errors
- [ ] `make format-check` passes
- [ ] `make validate` passes (structure, YAML frontmatter, links)
- [ ] `aet-release-prep.skill` exists and is a valid zip
- [ ] `make install-skills` creates symlink in `~/.claude/skills/aet-release-prep/`
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Delete `aet-release-prep.skill` and revert any lint fixes.

---

_Stage: plan-approved_
_Next step: run `aet-pipeline-implement` or `aet-work`_
