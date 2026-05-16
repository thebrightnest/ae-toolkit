# Plan: aet-ship Merge Verification Gate

## Context

PRD: `docs/prds/branch-safety-prd.md`
Parent issue: GitHub #3

`aet-ship` currently stops after PR creation (Step 11). It does not verify that the branch's commits are ancestors of `origin/main` before any branch deletion occurs. This gap is the root cause of the "Local Merge Trap."

## Tasks

1. Add Step 12 — Merge Verification to `aet-ship/SKILL.md` — S
2. Add Step 13 — Safe Branch Deletion to `aet-ship/SKILL.md` — S
3. Update Output and Key Principles sections — S
4. Run `make validate` and `make package` — S

### Renderer / UI Tasks

- [ ] Verify no unstyled `className` references remain

## Dependencies

None — can start immediately.

## Validation Steps

- [ ] `aet-ship/SKILL.md` line count ≤ 400 (warn only if exceeded)
- [ ] `make validate` passes (lint, format-check, skill structure)
- [ ] `make package` regenerates `aet-ship.skill` without errors
- [ ] Step 12 describes `git fetch origin` + `git merge-base --is-ancestor HEAD origin/main`
- [ ] Step 12 includes the exact warning message from the PRD on failure
- [ ] Step 13 only runs if Step 12 passed

## Rollback Plan

Revert `aet-ship/SKILL.md` to pre-change state and re-run `make package`.

---

_Stage: synced_
_Next step: run `aet-ship`_
