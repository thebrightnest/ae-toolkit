---
id: waf-01-aet-work-queue-state
blocked_by:
  - waf-02-aet-work-worktree-hygiene
size: S
---

# Plan: aet-work Queue State Hardening

## Context

PRD: `docs/prds/workflow-audit-fixes-prd.md`
Audit finding #2 (done without merge verification), #8 (stale worktree fields), #9 (branch naming inconsistency).

The work queue currently allows tasks to be marked `done` with `merge_commit: null` and no `merge_verified` flag. It also tracks 50 worktree fields while only 11 worktrees exist on disk. Branch naming is inconsistent across tasks.

## Tasks

1. Update queue schema documentation in `aet-work/SKILL.md` — add `merged`, `abandoned`, and deprecate `done` — S
2. Add merge-verification gate: refuse to mark terminal unless `merge_verified: true` or `abandoned: true` with reason — M
3. Add `aet-work status` worktree validation: flag stale `worktree` fields that point to missing directories — S
4. Add `aet-work cleanup` stale-field repair: clear `worktree` when the directory is missing or has 0 commits ahead — S
5. Enforce branch naming convention and store actual branch name in queue `branch` field — M
6. Merge branch to main and verify integration — S

**Size definitions:**

- **S**: ≤ 2 hr human time / ≤ 3 files / ≤ 100 diff lines
- **M**: ≤ 1 day human time / ≤ 5 files / ≤ 200 diff lines
- **L**: > 1 day OR > 5 files OR > 200 lines — **must be split before implementation**

## Dependencies

- None — can start immediately.
- Blocks: waf-02-aet-work-worktree-hygiene (shares aet-work skill file).

## Validation Steps

- [ ] `make lint` passes
- [ ] `make validate` passes
- [ ] Manual: create a mock task, mark it done without merge verification → skill rejects it
- [ ] Manual: run `aet-work status` with a stale worktree path → flags it
- [ ] Manual: run `aet-work cleanup` with a stale worktree path → clears field
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert `aet-work/SKILL.md` and `scripts/.aet-work-orchestrator.sh` to previous commit. Old queue JSON remains readable because the new fields are additive.

---

_Stage: merged_
_Next step: none — pipeline complete_
