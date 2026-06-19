---
id: tele-02-worktree-dependency-warmup
size: M
blocked_by: []
---

# Plan: Worktree Dependency Warmup

## Context

- PRD: `docs/prds/aet-telemetry-learning-prd.md`

New git worktrees created by `aet-work` start without dependency directories such as `app/node_modules` and `api/vendor`. Every pipeline stage rediscovers this and recreates the same symlink. This plan makes dependency warmup explicit and configurable.

This is an enhancement to the toolkit's own tooling, not a reproducible defect report.

## Task List

1. Add `prepare_worktree_dependencies(repo_root, worktree_dir)` to `aet-work/lib/worktree.py` — M
   - Read optional `.agents/aet-work.json` config with `symlink_dependencies` array.
   - For each entry, ensure the source exists and create a relative symlink inside the worktree.
   - Record the action or emit an `environment_issue` telemetry event on failure.
2. Call the helper in `aet-work/bin/orchestrator` immediately after `copy_untracked_files` — S
3. Document the config convention in `aet-work/SKILL.md` — S
4. Add migration note to `aet-work/references/upgrading-existing-project.md` — S
5. Run `make validate` — S

## Files to Modify

- `aet-work/lib/worktree.py`
- `aet-work/bin/orchestrator`
- `aet-work/SKILL.md`
- `aet-work/references/upgrading-existing-project.md`

## Validation Steps

- [ ] A sample `.agents/aet-work.json` with symlink entries results in correct symlinks inside a new worktree.
- [ ] Missing source directories are reported, not silently ignored.
- [ ] `make validate` passes.
- [ ] Each new source file introduced by this plan has a named test or validation step covering it.
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Remove the warmup helper and its orchestrator call; worktrees revert to manual dependency setup.

---

_Stage: plan-approved_
_Next step: run `aet-work`_
