# Commit Splitting Guide

## What Makes a Commit Bisectable

A commit is bisectable when it contains exactly one logical change that can be independently reviewed, tested, and reverted.

## Splitting Patterns

### When to Split

- **Mixed concerns** — refactor + feature in one commit → split
- **Multiple features** — two unrelated changes → split
- **Review feedback** — post-review fixes mixed with original work → split

### How to Split

1. **Identify logical units** — what are the independent changes?
2. **Use git add -p** — stage only the hunks for one logical change
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

## Auto-Splitting in aet-ship

If `ship` detects non-bisectable commits:
1. Analyze the diff for logical boundaries
2. Use `git reset --soft HEAD~1` + `git add -p` to re-stage
3. Create separate commits with auto-generated messages
4. Warn the user what was split and why
