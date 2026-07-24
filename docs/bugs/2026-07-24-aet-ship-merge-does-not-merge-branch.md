# Bug Report: `aet ship merge` records merge without merging the feature branch

## Metadata

- **Reported:** 2026-07-24T16:05:00Z
- **Severity:** critical
- **Status:** open

## Symptoms

`aet ship merge <task>` reports success and creates a commit on `main` that updates the plan footer to `merged`, but the feature branch's implementation commits are **not** merged into `main`. The code changes remain on the isolated feature branch, leaving `main` with only a plan-footer update.

Observed with:

- `cfg-01-config-resolution-overhaul`
- `cfg-03-cli-surface-fixes`
- `cfg-02-configure-writer`

In every case the tool printed:

```
Merging main into main...
   Merged main into main (<sha>)
Recorded merge for <task>: <sha> (manual)
```

The phrase "Merging main into main" indicates the merge source and target were the same branch.

## Reproduction Steps

1. Complete an AET plan through the orchestrator so it reaches `awaiting_merge`.
2. Ensure the feature branch exists and has implementation commits not on `main`:

   ```bash
   git log --oneline main..<branch>
   ```

3. Run:

   ```bash
   aet ship merge <task-id>
   ```

4. Observe output says "Merged main into main".
5. Inspect `main`:

   ```bash
   git log --oneline -n 5
   git diff --stat HEAD~1
   ```

   The top commit only changes `docs/plans/<task>.md` (the footer).
6. Verify the implementation branch is still unmerged:

   ```bash
   git merge-base main <branch>
   git log --oneline --graph --all -n 15
   ```

### Example from `cfg-02-configure-writer`

Commit produced by `aet ship merge`:

```
commit d26c63b — chore(cfg-02-configure-writer): mark plan as merged
 docs/plans/cfg-02-configure-writer.md | 4 ++--
 1 file changed, 2 insertions(+), 2 deletions(-)
```

Real merge produced manually:

```
commit 7987dd1 — merge cfg-02-configure-writer into main
 11 files changed, 400 insertions(+), 114 deletions(-)
```

The real merge included `src/aet/cli/configure_backend.py`, `tests/cli/test_configure.py`, skill updates, and PRD sync — none of which were present in the `aet ship merge` output.

## Root Cause

`aet ship merge` appears to resolve the merge source as `main` (or the current checkout) instead of the task's feature branch. It then performs a no-op merge of `main` into `main` and commits only the plan-footer update that marks the task as merged.

Evidence:

- The merge output says `Merging main into main` rather than `Merging <branch> into main`.
- The resulting commit only touches the plan file.
- `git merge-base main <branch>` before the fix is the same as before the merge, proving the branch was never incorporated.

Why existing checks did not catch it:

- The command exits 0 and prints a green checkmark, so the orchestrator and user both believe the merge succeeded.
- There is no post-merge verification that the branch commits are now ancestors of `main`.
- `aet status` removes the task from the active queue, so the missing code is not obvious until a downstream task fails or a human inspects the graph.

## Fix Summary

**Not yet applied.**

A code fix in the `aet ship merge` path should:

1. Identify the task's actual feature branch (from the queue record's `branch` or `worktree` field, or from `docs/plans/<task>.md` frontmatter plus the conventional branch name).
2. Merge that branch into the target branch (default `main`).
3. Only after the branch merge succeeds, commit the plan-footer update marking the task as `merged`.
4. Verify post-merge that `git merge-base --is-ancestor <branch> HEAD` is true.

**Manual workaround used today:**

- Reset `main` to remove the bogus merge-mark commit.
- In the task worktree, update the plan footer to `merged` and commit.
- Run `git merge <branch> --no-ff` from `main`.
- Push corrected history.

## Regression Test

No automated test exists for this path. A regression test should:

1. Create a temp repo with `main` and a feature branch containing a file not on `main`.
2. Queue the task and run `aet ship merge <task>`.
3. Assert the new file is present on `main`.
4. Assert `git merge-base --is-ancestor <branch> main` returns true.

## Validation

- [ ] Reproduction steps no longer trigger the bug
- [ ] Existing test suite passes with no new failures
- [ ] No regressions observed in related functionality

## Lessons Learned

- **Pattern:** Merge/ship commands that update bookkeeping metadata without verifying the actual code merge.
- **Prevention:** Any ship/merge command should have a fail-closed post-condition check that the source branch is an ancestor of the target branch. Do not trust exit code 0 alone.
- **Reference:** This report feeds into `aet-evolve` and should inform updates to `aet-ship` skill references and the `aet ship merge` implementation.
