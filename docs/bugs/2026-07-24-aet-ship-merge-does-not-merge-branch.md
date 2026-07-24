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

`aet ship merge` resolves the merge **source** from the current checkout, not from the
task. `cmd_merge` reads the feature branch with:

```python
# src/aet/cli/ship.py:832
feature_branch = _run_git("branch", "--show-current", check=False).stdout.strip()
```

When the command is invoked from a checkout sitting on `main` (e.g. the repo root),
`feature_branch` resolves to `"main"` and `target_branch` defaults to `main`.
`_merge_into_target` then runs `git merge --no-ff main` on `main` — a no-op — and the only
commit produced is the plan-footer update written by the record-merge/closure step
(`cmd_record_merge`, `src/aet/cli/aet_state.py`). The task's real branch is never touched.

Evidence:

- The merge output at `ship.py:863` is `f"Merging {feature_branch} into {target_branch}..."`;
  the observed "Merging main into main" is that f-string with **both** operands resolved to
  `main` — direct proof `feature_branch == "main"`.
- The resulting commit only touches the plan file.
- `git merge-base main <branch>` is unchanged across the "merge", proving the branch was
  never incorporated.

Why existing checks did not catch it:

- The command exits 0 and prints a green checkmark, so the orchestrator and user both believe the merge succeeded.
- There is no post-merge verification that the branch commits are now ancestors of `main`.
- `aet status` removes the task from the active queue, so the missing code is not obvious until a downstream task fails or a human inspects the graph.

## Fix Summary

**Not yet applied.**

A code fix in the `aet ship merge` path should:

1. **Resolve the feature branch from the task, not the checkout.** Replace the
   `git branch --show-current` read at `ship.py:832` with a branch derived from the task id.
   `cmd_merge` already computes `_task_id_from_plan(plan_path)` (at `ship.py:873`, currently
   only for recording) and the plan path is known from line 827 — the task identity is
   already in scope *before* the merge; it just isn't used to pick the branch. Source the
   branch from the queue record's `branch`/`worktree` field or the conventional
   name derived from that task id.
2. **Guard against self-merge before merging.** Add a fail-closed pre-check: if the resolved
   `feature_branch == target_branch`, abort with "refusing to merge a branch into itself."
   This single line would have hard-failed all three cfg-* cases at the "Merging main into
   main" moment, before any bogus commit.
3. Merge that branch into the target branch (default `main`).
4. Only after the branch merge succeeds, commit the plan-footer update marking the task as
   `merged`.
5. Verify post-merge that `git merge-base --is-ancestor <branch> HEAD` is true
   (belt-and-braces with the pre-check in step 2).

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
- **Systemic class:** This is the third instance of "`aet ship` resolves branch/base identity from ambient git state instead of the plan id" — alongside the base-resolver bug (`_determine_pr_base` returning the branch's own name as PR base) and the cwd-sensitivity of `ship open`/`close`. The class-level fix is: **derive branch and base identity from the plan/task id, never from cwd or the current checkout.** Closing the class retires all three at once.
- **Prevention:** Any ship/merge command should have a fail-closed post-condition check that the source branch is an ancestor of the target branch — and a pre-condition check that source ≠ target. Do not trust exit code 0 alone.
- **Reference:** This report feeds into `aet-evolve` and should inform updates to `aet-ship` skill references and the `aet ship merge` implementation.
