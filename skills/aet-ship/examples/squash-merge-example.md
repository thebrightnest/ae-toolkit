# Example: Squash-Merge Verification

## Scenario

Branch `feat/auth-refactor` was squash-merged via GitHub UI. The original branch commits are not ancestors of `origin/main`, so the regular ancestry check fails.

## Step 1 — Ancestry check fails

```bash
$ git merge-base --is-ancestor HEAD origin/main
$ echo $?
1
```

Exit code 1 indicates the branch commits are not on `origin/main` — possible squash merge.

## Step 2 — GitHub API verification succeeds

```bash
$ PR_NUMBER=$(gh pr view --json number --jq '.number')
$ MERGE_COMMIT=$(gh pr view $PR_NUMBER --json mergeCommit --jq '.mergeCommit.oid')
$ git merge-base --is-ancestor $MERGE_COMMIT origin/main
$ echo $?
0
```

The squash commit `a1b2c3d` is an ancestor of `origin/main`. Squash merge verified.

## Step 3 — Force-delete the branch

```bash
$ git branch -D feat/auth-refactor
Deleted branch feat/auth-refactor (was e5f6a7b).
```

`git branch -D` is required because the original commits are not ancestors of `origin/main`.

## Work queue update

```json
{
  "ticket": "feat/auth-refactor",
  "merge_commit": "a1b2c3d4...",
  "merge_strategy": "squash"
}
```

The `merge_commit` is the squashed commit SHA on `main`, not the original branch HEAD.
