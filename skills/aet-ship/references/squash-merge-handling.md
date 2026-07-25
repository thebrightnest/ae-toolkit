# Squash-Merge Handling

In this repo the trunk branch is `main`; substitute `<trunk>` with the branch reported by `aet setup verify`.

## When This Applies

Use this fallback when `gh` is unavailable, the remote is not GitHub, or `gh pr view` returns no `mergeCommit` data. The primary verification path uses the GitHub API; this document covers the heuristic fallback.

## Diff-Based Verification

### 1. Capture the branch diff

```bash
MERGE_BASE=$(git merge-base HEAD origin/<trunk>)
BRANCH_DIFF=$(git diff $MERGE_BASE..HEAD)
```

### 2. Search recent `origin/<trunk>` commits

Check the last N commits on `origin/<trunk>` for a matching diff. A reasonable default is N=20:

```bash
for commit in $(git rev-list --max-count=20 origin/<trunk>); do
  COMMIT_DIFF=$(git diff ${commit}^..${commit})
  if [ "$BRANCH_DIFF" = "$COMMIT_DIFF" ]; then
    echo "Match found: $commit"
    break
  fi
done
```

### 3. Accept or halt

- **If a matching diff is found:** Treat the commit as the squash merge. Record it as `merge_commit` and proceed with force-delete (`git branch -D`).
- **If no match is found:** **HALT for manual verification.** Print a warning that diff-based detection is best-effort and the branch may be unmerged.

## Limitations

- **False positives:** Two unrelated changes can produce identical diffs (rare but possible with small changes).
- **Amended commits:** If the squash commit was amended on `origin/<trunk>`, the diff may no longer match exactly.
- **Partial squash:** If only some commits from the branch were squashed, the diff comparison will mismatch.
- **Large diffs:** Very large diffs can cause performance issues in the comparison loop.

## When to Halt for Manual Verification

- No `gh` CLI and no matching diff found
- The repository uses a non-GitHub remote (GitLab, Bitbucket, etc.)
- The branch diff is empty (all changes may have been committed via another path)
- Any uncertainty about whether the PR was actually merged

In all halt cases, **do not delete the branch** until a human confirms the merge status.
