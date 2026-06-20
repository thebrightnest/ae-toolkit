---
id: tele-06-validate-and-package
size: S
blocked_by:
  - tele-01-enrich-telemetry-schema
  - tele-02-worktree-dependency-warmup
  - tele-03-stage-group-session-reuse
  - tele-04-focused-tests-diff-scoping
  - tele-05-cross-project-telemetry-archive
---

# Plan: Validate & Package the Telemetry Learning Update

## Context

- PRD: `docs/prds/aet-telemetry-learning-prd.md`
- Depends on: all `tele-*` plans

After the individual skill and library changes are complete, run the toolkit's quality gates and regenerate the `.skill` packages.

This is an enhancement to the toolkit's own tooling, not a reproducible defect report.

## Task List

1. Run `make validate` — S
2. Fix any lint, formatting, or skill-structure issues — M
3. Run `make package` — S
4. Verify that the updated `.skill` files include the new instructions and scripts — S

## Files to Modify

- Generated `.skill` archives under the repository root.

## Validation Steps

- [ ] `make validate` passes.
- [ ] `make package` completes without errors.
- [ ] `scripts/check-reproducible-package.sh` confirms deterministic packaging.
- [ ] Each updated `.skill` file contains the expected changes.
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the commits for the individual plans and re-run `make package` from the prior state.

---

_Stage: secure_
