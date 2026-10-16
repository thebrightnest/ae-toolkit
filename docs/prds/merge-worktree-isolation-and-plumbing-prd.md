---
id: merge-worktree-isolation-and-plumbing
status: scope-validated
---

# PRD: Merge Worktree Isolation & Plumbing Integration

## Overview

When running `aet ship merge` or merge trains in repositories watched by IDEs (VS Code, Cursor, JetBrains) or language servers, integration fails intermittently with `fatal: Unable to create '.git/worktrees/.../index.lock': File exists`. This occurs because `aet ship merge` allocates ephemeral merge worktrees directly inside the repository workspace (`.worktrees/.merge-*`) and executes 58 lines of high-churn Git porcelain (`reset --hard`, `clean -fd`, `checkout -f --detach`, `merge --squash`, `commit`), prompting external file watchers to run concurrent `git status` commands that grab `index.lock`.

This feature permanently resolves the root causes by:

1. Creating the squash-merge commit directly in Git's object database using Git plumbing (`git commit-tree`), completely eliminating `git checkout -f --detach`, working-tree file rewrites, and `index.lock` contention during squash merge.
2. Allocating ephemeral merge worktrees in the system temp directory (`tempfile.mkdtemp`) outside the repository root, isolating temporary checkouts from IDE inotify/FSEvents watchers.
3. Standardizing IDE watcher exclusions for persistent `.worktrees/` directories.

## Goals

- Eliminate `index.lock` collisions during `aet ship merge` and merge train processing.
- Eliminate gratuitous working tree churn during squash-merge by using native Git plumbing (`git commit-tree`).
- Isolate ephemeral merge worktrees from workspace file watchers by creating them in system temporary storage (`tempfile.mkdtemp`).
- Ensure 100% commit equivalence and zero regressions across existing integration and merge train suites.

## Non-Goals

- Implementing ad-hoc sleep/retry loops around failing porcelain commands as a primary fix (rejected as a symptom patch).
- Modifying Git's internal index locking mechanics.
- Altering the worktree lifecycle for persistent developer worktrees (`.worktrees/{task_id}`) beyond IDE watcher exclusion recommendations.

## Requirements

- **R-1**: In `src/aet/integrate.py`, the squash-merge commit on top of `target_ref` MUST be constructed using Git plumbing (`git commit-tree "$TREE_SHA" -p "$TARGET_REF" -m "Integrate $TASK_ID"`), completely replacing the porcelain sequence (`git reset --hard`, `git clean -fd`, `git checkout -f --detach`, `git merge --squash`, `git commit`).
- **R-2**: The squash commit produced by plumbing MUST have identical tree SHA, parent SHA, and commit message to the conventional porcelain squash merge.
- **R-3**: In `src/aet/cli/ship.py`, temporary merge worktrees MUST be created in the system temporary directory (`tempfile.mkdtemp(prefix=f"aet-merge-{task_id}-")`) rather than inside `repo_root / ".worktrees"`.
- **R-4**: Temporary merge worktrees MUST be unconditionally cleaned up in a `finally` block using `git worktree remove --force` and filesystem removal (`shutil.rmtree`), leaving no orphaned references in `.git/worktrees/`.
- **R-5**: In `skills/aet-setup/SKILL.md` (and related templates), document and generate recommended `.vscode/settings.json` exclusions for `**/.worktrees/**` in `files.watcherExclude` and `git.ignoredRepositories`.

## User Stories

- As an engineer using `aet ship merge`, I want integration to succeed reliably without `index.lock` errors caused by background editor watchers (satisfies: R-1, R-3).
- As a CI/CD or local automation pipeline, I want squash integration to execute instantaneously with zero disk churn (satisfies: R-1, R-2).
- As an engineer running multi-task merge trains, I want temporary merge worktrees to leave zero residual debris or dangling references in `.git/worktrees` (satisfies: R-4).
- As an engineer configuring a new repository with `aet-setup`, I want editor settings to automatically ignore `.worktrees/` so persistent worktrees do not trigger editor file watchers (satisfies: R-5).

## Acceptance Criteria

- [ ] `git commit-tree` is used in `src/aet/integrate.py` to create the squash commit; `git checkout -f --detach` is completely removed from the integration code path (satisfies: R-1).
- [ ] Integration tests verify that `staged_commit` created via `commit-tree` has `target_ref` as parent and the rebased task tree as its tree (satisfies: R-2).
- [ ] Ephemeral merge worktrees created by `aet ship merge` reside outside `repo_root` under OS temp (satisfies: R-3).
- [ ] Ephemeral merge worktrees are pruned from `.git/worktrees` upon completion or error (satisfies: R-4).
- [ ] `skills/aet-setup/SKILL.md` documents `.worktrees/**` exclusion for VS Code settings (satisfies: R-5).
- [ ] Existing integration test suites (`tests/test_integrate.py`, `tests/test_ship_merge.py`) pass cleanly (satisfies: R-1, R-2, R-3, R-4).

## Technical Notes

- When a task branch has been rebased onto `target_ref`, `git rev-parse HEAD^{tree}` in the worktree resolves the tree containing all task changes on top of the train tip.
- `git commit-tree` takes the tree SHA, parent commit (`-p <target_ref>`), and commit message (`-m "Integrate <task_id>"`). It writes the commit object directly to `.git/objects/` without touching the index or working directory.
- `train.py` already uses `tempfile.mkdtemp(prefix="aet-train-flush-")` at line 381. Aligning `ship.py` to use `tempfile.mkdtemp(prefix=f"aet-merge-{task_id}-")` unifies the temporary worktree pattern across `aet`.

## Open Questions

- None. The plumbing pattern is standard Git object manipulation and already verified against local fixtures.
