# Plan: aet-ship Branch Lifecycle & Release Gating

## Context

PRD: `docs/prds/workflow-audit-fixes-prd.md`
Audit finding #1 (post-merge branch commits), #10 (release bumps on feature branches).

Multiple branches were squash-merged into `main`, but subsequent commits (plan stage updates, review reports, release bumps) were added to the same branch. Release bumps (`chore(release)`) were also committed on feature branches.

## Tasks

1. Update `aet-ship/SKILL.md` Step 13: add `git push origin --delete <branch>` after local branch deletion to prevent remote branch from receiving post-merge commits — M
2. Remove `chore(release)` version bump from `aet-ship/SKILL.md` Step 10; note version bump as future skill responsibility — S
3. Add repo-level pre-commit hook that rejects `chore(release)` commits on non-main branches — M
4. Document branch lifecycle policy in `docs/CONVENTIONS.md` — S
5. Merge branch to main and verify integration — S

**Size definitions:**

- **S**: ≤ 2 hr human time / ≤ 3 files / ≤ 100 diff lines
- **M**: ≤ 1 day human time / ≤ 5 files / ≤ 200 diff lines
- **L**: > 1 day OR > 5 files OR > 200 lines — **must be split before implementation**

## Dependencies

- None — can start immediately.

## Validation Steps

- [ ] `make lint` passes
- [ ] `make validate` passes
- [ ] Manual: simulate squash merge via `aet-ship` → local AND remote feature branches are deleted
- [ ] Manual: attempt `chore(release)` commit on a feature branch → pre-commit rejects it
- [ ] Manual: run `aet-ship` → no version bump step; ship completes without bumping VERSION
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert `aet-ship/SKILL.md`, pre-commit hook, and `docs/CONVENTIONS.md` to previous commit.

---

\_Stage: merged
\_Next step: none — pipeline complete
