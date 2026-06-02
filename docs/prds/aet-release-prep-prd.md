# PRD: aet-release-prep

## Overview

A new AE Toolkit skill that automates release preparation by analyzing git commits since the last tag, detecting the project's versioning scheme, suggesting semantic version bumps, and updating `CHANGELOG.md` and `PRODUCT.md` at the repository root. It is intentionally separate from `aet-ship`: multiple features can be merged without an immediate release, and release documentation is a distinct concern from merge/ship gating.

## Goals

- Provide a standalone, agent-agnostic skill for release preparation
- Automatically detect the project's version source (package.json, VERSION file, or git tags)
- Generate append-only, conventional-commit-grouped `CHANGELOG.md` at repo root
- Generate/update user-facing `PRODUCT.md` at repo root with "What's New" summaries
- Replace the original Node.js helper with a POSIX shell script aligned with toolkit conventions
- Follow all AE Toolkit skill conventions: YAML frontmatter with triggers, `examples/`, `references/`, under 400 lines

## Non-Goals

- Does not create git tags, push to remote, or publish artifacts (manual step or future skill)
- Does not support Windows natively (POSIX shell only; Windows support deferred)
- Does not merge code, create PRs, or run CI (those belong to `aet-ship`)
- Does not enforce that a release _must_ happen after every merge

## User Stories

- As a maintainer, I want to invoke a single skill before a release so that my changelog and product docs are automatically analyzed and drafted.
- As a maintainer, I want the skill to detect my project's version scheme automatically so I don't need manual configuration.
- As a reviewer, I want `CHANGELOG.md` to be append-only so historical releases are never corrupted.

## Acceptance Criteria

- [ ] Skill directory `aet-release-prep/` exists with `SKILL.md`, `examples/`, and `references/`
- [ ] `SKILL.md` has valid YAML frontmatter with `name`, `description`, and trigger phrases
- [ ] `SKILL.md` is under 400 lines; deep detail lives in `references/`
- [ ] Bash script `scripts/release-prep.sh` (or inside skill directory) replaces original Node.js logic
- [ ] Script detects version source automatically: `package.json` → `VERSION` file → latest git tag
- [ ] Script outputs JSON matching the original schema: last tag, commits, suggested bump, next version
- [ ] `CHANGELOG.md` is written to repo root, append-only, grouped by commit type
- [ ] `PRODUCT.md` is written to repo root with user-facing "What's New" section + evergreen feature docs
- [ ] Integration with `aet-ship` is documented: ship handles pre-merge; release-prep handles release docs
- [ ] `make validate` passes after skill is added
- [ ] `make package` generates `aet-release-prep.skill`

## Technical Notes

- **Stack adaptation order:** Check `package.json` first (Node projects), then `VERSION` (generic), then `git describe --tags --abbrev=0` (fallback). The detected source is reported in output so the user knows which was used.
- **Script location:** The helper should live inside `aet-release-prep/` (e.g., `aet-release-prep/release-prep.sh`) so it travels with the skill. The `SKILL.md` references it via `$(git rev-parse --show-toplevel)/aet-release-prep/release-prep.sh`.
- **Commit classification:** Replicate original logic in POSIX shell: conventional commit regexes, keyword fallbacks, breaking-change detection.
- **PRODUCT.md triage:** Preserve the original skill's strict user-facing vs internal filter. Internal changes (tests, refactors, CI) never appear in "What's New."
- **Append-only guard:** The skill instructions must mandate reading the full file first, inserting the new section after the header, and never rewriting existing sections.
- **aet-ship boundary:** Add a note to `aet-ship/SKILL.md` (or its references) clarifying that `aet-ship` does not update changelogs or product docs; those are `aet-release-prep`'s responsibility.

## Open Questions

1. Should `PRODUCT.md` include a template for first-time creation, or should the skill scaffold it on demand?
2. Should the bash script support a `--dry-run` flag so users can preview the bump without writing files?
3. Should we add a `docs/adr/` entry documenting the separation of concerns between `aet-ship` and `aet-release-prep`?

---

_Stage: scope-validated_
_Next step: run `aet-pipeline-implement` (single task) or `aet-work` (multi-task queue)_
