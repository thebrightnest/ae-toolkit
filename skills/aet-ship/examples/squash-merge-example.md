# Example: Squash-Merge Verification

## Scenario

Branch `feat/auth-refactor` was squash-merged via GitHub UI. The original branch commits are not ancestors of the resolved trunk branch, so the regular ancestry check fails. In this repo the trunk branch is `main`; substitute `<trunk>` with the branch reported by `aet setup verify`.

## Step 1 — Ancestry check fails

```bash
$ git merge-base --is-ancestor HEAD origin/<trunk>
$ echo $?
1
```

Exit code 1 indicates the branch commits are not on the trunk branch — possible squash merge.

## Step 2 — GitHub API verification succeeds

```bash
$ PR_NUMBER=$(gh pr view --json number --jq '.number')
$ MERGE_COMMIT=$(gh pr view $PR_NUMBER --json mergeCommit --jq '.mergeCommit.oid')
$ git merge-base --is-ancestor $MERGE_COMMIT origin/<trunk>
$ echo $?
0
```

The squash commit `a1b2c3d` is an ancestor of the trunk branch. Squash merge verified.

## Step 3 — Force-delete the branch

```bash
$ git branch -D feat/auth-refactor
Deleted branch feat/auth-refactor (was e5f6a7b).
```

`git branch -D` is required because the original commits are not ancestors of the trunk branch.

## Work queue update

```bash
aet ship close feat/auth-refactor --merge-commit a1b2c3d4...
```

The `--merge-commit` is the squashed commit SHA on the trunk branch, not the original branch HEAD.
