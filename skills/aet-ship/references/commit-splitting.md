# Commit Splitting Guide

## What Makes a Commit Bisectable

A commit is bisectable when it contains exactly one logical change that can be independently reviewed, tested, and reverted.

## Splitting Patterns

### When to Split

- **Mixed concerns** — refactor + feature in one commit → split
- **Multiple features** — two unrelated changes → split
- **Review feedback** — post-review fixes mixed with original work → split
- **Multi-task plans with a single commit** — multi-task plan implemented in one commit trips `is_monolithic_commit` → split

### How to Split

1. **Identify logical units** — what are the independent changes?
2. **Use `git add -p`** — stage only the hunks for one logical change
3. **Commit with clear message** — describe the single change
4. **Repeat** until all changes are committed separately

### Example

**Before (bad):**

```
commit: "Add user auth and fix linting and update README"
```

**After (good):**

```
commit 1: "feat(auth): add login endpoint with JWT"
commit 2: "style: fix linting errors in auth module"
commit 3: "docs: update README with auth setup instructions"
```

## Pre-Stage Validation for Multi-Task Plans

Autonomous agents and contributors must verify that multi-task plans (`plan_task_count > 1`) have atomic commits per task before staging or calling `aet ship merge`:

1. **Check commit count**:
   ```bash
   git rev-list --count origin/main..HEAD
   ```
2. **Evaluate against plan tasks**:
   If the plan contains multiple tasks (`plan_task_count > 1`) and the commit count is 1, the pre-merge gate's `is_monolithic_commit` check will refuse integration (`guard_refused`).
3. **Split before merge**:
   Split the single commit into atomic commits corresponding to each plan task using `aet ship split`.

## Auto-Splitting in aet-ship

If `aet ship` (or `aet ship open`) detects non-bisectable commits or a monolithic commit on a multi-task plan, stop and use the dedicated command:

```bash
aet ship split docs/plans/TASK-001.md \
  --message "feat(auth): add login endpoint" --paths src/auth/login.py \
  --message "style: fix linting" --paths src/auth/*.py \
  --message "docs: update README" --paths README.md
```

`aet ship split` resets the PR range softly and commits each `--message`/`--paths` group in order. It fails closed if the resulting tree does not match the original HEAD, so an incomplete grouping is safe to recover with the printed original HEAD SHA.
