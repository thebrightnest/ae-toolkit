---
id: uvi-04-installer-docs-update
size: S
status: queued
blocked_by:
  - uvi-02-curl-installer-script
pipeline: minimal
security_review: skipped
security_review_reason: Documentation-only change.
docs_sync: required
docs_sync_reason: README Quick Start is updated to lead with the new installer.
---

# Plan: Update README and installer documentation

## Context

Part of the [uv one-line installer PRD](../prds/uv-one-line-installer-prd.md) (`docs/prds/uv-one-line-installer-prd.md`). Once the installer exists, the README Quick Start must lead with the one-liner and keep the manual paths as alternatives.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [ ] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. Rewrite README "Quick Start" section to lead with the curl one-liner — S (traces: R-1, R-14)
2. Move the existing pip/npx/manual instructions under "Manual install" or "Development" — S (traces: R-12, R-14)
3. Document installer flags (`--tag`, `--agent`, `--bin-dir`, `--skills-dir`, `--repo`, `--dry-run`) — S (traces: R-2)
4. Add a short troubleshooting note for "`~/.local/bin` not on PATH" — S (traces: existing behavior)
5. Run `make lint` on markdown files — S

**Size definitions:**

- **S**: ≤ 2 hr human time / ≤ 3 files / ≤ 100 diff lines
- **M**: ≤ 1 day human time / ≤ 5 files / ≤ 200 diff lines
- **L**: > 1 day OR > 5 files OR > 200 lines — **must be split before implementation**

## Batching Check

- [x] This is not one of several near-identical additions
- [ ] The diff is expected to exceed 3 files or 50 lines
- [x] The work cannot share a branch/PR with unrelated tasks

## Rejected Alternatives

- **Replace all manual instructions** — rejected: pip/editable and `make install-skills` are still required for development; removing them would break contributor onboarding.
- **Create a separate install guide doc** — rejected: the README is the primary entry point; a separate doc would fragment the quick start. A short section is enough until the installer grows more options.

## Files to Modify

- `README.md` — Quick Start rewrite

## Validation Steps

- [ ] `make lint` passes
- [ ] All relative internal links in README still resolve
- [ ] R-trace coverage: every in-scope R-id is covered by ≥ 1 task; no task cites an unknown R-id
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

`git revert` the commit; README reverts to the previous three-step instructions.

---

*Stage: qa-complete*
*Next step: run `aet-review`*
