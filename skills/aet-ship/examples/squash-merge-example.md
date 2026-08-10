# Example: Squash-Merge Verification and Closure

## Scenario

Branch `feat/auth-refactor` was squash-merged via GitHub UI. The original branch
commits are not ancestors of the resolved trunk branch, so the regular ancestry
check fails.

## Step 1 — Verify the squash merge

Use `aet ship verify` with `--squash-fallback` to run the full resolution ladder
(ancestry → GitHub CLI → diff fallback). The command is read-only and mutates no
state.

```bash
$ aet ship verify feat/auth-refactor --squash-fallback
a1b2c3d4 squash (exact)
```

Output format: `<merge-sha> <strategy> (<match-kind>)`. Match kind is `exact` or
`drift` when the diff fallback resolved the commit; `drift` means the squash
commit differed from the branch diff by ≤ 20 changed lines and was accepted as a
tolerant match.

## Step 2 — Close with automatic branch cleanup

```bash
$ aet ship close feat/auth-refactor --delete-branch
Recorded merge for feat/auth-refactor: a1b2c3d4... (squash)
```

`--delete-branch` removes the remote and local feature branches only after the
closure transaction lands successfully. If closure fails, the branches are left
untouched and the command exits `EXIT_DELETE_BEFORE_RECORD`.

## Halt conditions and exit codes

`aet ship verify` exits with named codes so automation can stop safely:

| Code | Meaning | What to do |
|------|---------|------------|
| `0` | Match found | Use the printed SHA for `aet ship close` if needed. |
| `10` | `EXIT_VERIFY_NO_MATCH` | No ancestry, no `gh` mergeCommit, and no diff match. Branch may be unmerged or the fallback window missed it. |
| `11` | `EXIT_VERIFY_AMBIGUOUS` | Empty branch diff or more than one drift-match candidate. Resolve manually before closing. |

In all non-zero cases, do not delete the branch until a human confirms the merge
status.
