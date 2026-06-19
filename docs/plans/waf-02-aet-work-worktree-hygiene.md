---
id: waf-02-aet-work-worktree-hygiene
blocked_by:
  - waf-01-aet-work-queue-state
size: S
---

# Plan: aet-work Worktree Hygiene

## Context

PRD: `docs/prds/workflow-audit-fixes-prd.md`
Audit finding #3 (empty worktrees left behind), #5 (plan path duplication in worktrees).

The orchestrator creates a git worktree for every unblocked task. If the agent fails early or hits a step limit, the worktree exists with zero commits ahead of main. The orchestrator also copies `docs/plans` into the worktree, and agents sometimes write to `docs/plans/plans/`, creating duplicates.

## Tasks

1. Update `aet-work/SKILL.md` cleanup procedure to detect worktrees with 0 commits ahead of main and auto-remove them — S
2. Update orchestrator to remove the worktree if the spawned agent exits without creating any commits — M
3. Remove the `cp -R` lines for `docs/plans` and `docs/prds` from the orchestrator template; the git worktree already contains these directories — M
4. If untracked plan files must be visible, copy only untracked files (not the full directory) and set them read-only — S
5. Add a guardrail in `aet-plan/SKILL.md` and `aet-pipeline-implement/SKILL.md`: never create `docs/plans/plans/` or nested duplicate directories — S
6. Merge branch to main and verify integration — S

**Size definitions:**

- **S**: ≤ 2 hr human time / ≤ 3 files / ≤ 100 diff lines
- **M**: ≤ 1 day human time / ≤ 5 files / ≤ 200 diff lines
- **L**: > 1 day OR > 5 files OR > 200 lines — **must be split before implementation**

## Dependencies

- Blocked by: waf-01-aet-work-queue-state (to avoid merge conflicts in aet-work skill file).

## Validation Steps

- [ ] `make lint` passes
- [ ] `make validate` passes
- [ ] Manual: create a worktree with 0 commits ahead, run `aet-work cleanup` → worktree removed
- [ ] Manual: start an orchestrator run, verify `docs/plans` is a normal git directory (not a copy) in the worktree
- [ ] Manual: agent writes a plan update → no `docs/plans/plans/` directory created
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert `aet-work/SKILL.md` and `scripts/.aet-work-orchestrator.sh` to previous commit.

---

_Stage: merged_
_Next step: none — pipeline complete_
