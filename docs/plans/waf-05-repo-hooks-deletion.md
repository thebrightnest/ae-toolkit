# Plan: Repo Hooks — Pre-Push Deletion Short-Circuit

## Context

PRD: `docs/prds/workflow-audit-fixes-prd.md`
Audit finding #7 (pre-push hook timeout blocks branch cleanup).

Deleting remote branches with `git push origin --delete` triggers the pre-push hook, which runs the full test suite + coverage diff gate. This takes >60 seconds and times out background shell tasks.

## Tasks

1. Create `scripts/hooks/pre-push` with short-circuit logic: if all pushed refs are deletions (no new objects), skip the coverage gate and exit 0 — M
2. Create `scripts/hooks/pre-commit` matching the AE Toolkit quality needs (markdownlint, format-check, secrets scan) — M
3. Add hook install instructions to `docs/CONVENTIONS.md` (symlink from `.git/hooks/` to `scripts/hooks/`) — S
4. Verify the hook still runs the full gate when actual commits are being pushed — S
5. Document the behavior in `docs/CONVENTIONS.md` — S
6. Merge branch to main and verify integration — S

**Size definitions:**

- **S**: ≤ 2 hr human time / ≤ 3 files / ≤ 100 diff lines
- **M**: ≤ 1 day human time / ≤ 5 files / ≤ 200 diff lines
- **L**: > 1 day OR > 5 files OR > 200 lines — **must be split before implementation**

## Dependencies

- None — can start immediately.

## Validation Steps

- [ ] `make lint` passes (if hook is tracked as a script)
- [ ] Manual: `git push origin --delete test-branch` → hook exits quickly with no test run
- [ ] Manual: `git push origin feature-branch` → hook runs full gate as before
- [ ] Manual: verify `scripts/hooks/` files are tracked in git and installable via symlink
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Restore pre-push hook from git history.

---

_Stage: plan-approved_
_Next step: run `aet-pipeline-implement` or `aet-work`_
