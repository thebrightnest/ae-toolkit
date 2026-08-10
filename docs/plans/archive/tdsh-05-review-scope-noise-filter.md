---
id: tdsh-05-review-scope-noise-filter
size: S
blocked_by: []
pipeline: standard
status: merged
---

# Plan: Verify aet-review scope and project-level noise filter

## Context

Part of [Telemetry-Driven Skill Hardening](../prds/telemetry-driven-skill-hardening-prd.md). `mine-learnings` found 103 review-noise instances, often from `.gitignore`, `AGENTS.md`, and other project-level files.

The `aet-review/SKILL.md` `review` procedure already scopes the diff to the PR base and ignores `.gitignore` and `AGENTS.md` by default. This plan verifies and extends the filter to include `docs/CONVENTIONS.md` and other project-level docs, and clarifies when such files are considered in-scope.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [ ] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. Verify `aet-review/SKILL.md` scopes diff to PR base and ignores project-level noise by default — S
2. Extend the noise filter to include `docs/CONVENTIONS.md` and other project-level docs unless explicitly touched — S
3. Clarify when project-level files are considered in-scope — S
4. Repackage skill and run `make validate` — S

## Files to Modify

- `aet-review/SKILL.md`

## Validation Steps

- [ ] `make lint` passes
- [ ] `make format-check` passes
- [ ] `make validate` passes
- [ ] SKILL.md remains ≤ 400 lines
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

1. Revert `aet-review/SKILL.md` changes.
2. Re-run `make validate`.

---

_Stage: merged_
_Next step: run `aet-review`_
