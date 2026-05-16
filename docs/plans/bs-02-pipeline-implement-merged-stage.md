# Plan: aet-pipeline-implement `merged` Stage

## Context

PRD: `docs/prds/branch-safety-prd.md`
Parent issue: GitHub #3
Blocked by: `bs-01-aet-ship-merge-verification`

`aet-pipeline-implement` ends at stage `synced` with the message "Next step: run `aet-ship`". There is no stage representing "the code is actually on `origin/main`". This plan adds a `merged` stage and post-ship verification.

## Tasks

1. Add `merged` stage to the Resuming from a Stage table in `aet-pipeline-implement/SKILL.md` — S
2. Add Post-Ship Verification procedure section — S
3. Update Completion Protocol to reference `merged` stage — S
4. Run `make validate` and `make package` — S

## Dependencies

- `bs-01-aet-ship-merge-verification` — the post-ship verification in this plan references the merge verification behavior added to `aet-ship`

## Validation Steps

- [ ] `aet-pipeline-implement/SKILL.md` line count ≤ 400 (warn only if exceeded)
- [ ] `make validate` passes (lint, format-check, skill structure)
- [ ] `make package` regenerates `aet-pipeline-implement.skill` without errors
- [ ] Stage table includes `merged` after `synced`
- [ ] Post-ship verification uses `git merge-base --is-ancestor HEAD origin/main`
- [ ] On success, plan stage updates to `merged` and work queue gets `merge_verified`

## Rollback Plan

Revert `aet-pipeline-implement/SKILL.md` to pre-change state and re-run `make package`.

---

_Stage: synced_
_Next step: run `aet-ship`, then `post-ship-verify` to reach `merged`_
