# Bug Report: `aet ship merge` records merge without merging the feature branch

## Metadata

- **Reported:** 2026-07-24T16:05:00Z
- **Severity:** critical
- **Status:** resolved

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

**Applied 2026-07-24.** Scope: `cmd_merge`/`_merge_into_target` in
`src/aet/cli/ship.py` (~45 lines) plus regression tests in `tests/test_ship_merge.py`.

1. **Resolve the feature branch from the task, not the checkout.** A new
   `_resolve_feature_branch(task_id)` helper resolves the merge source _by name_ — the
   orchestrator names each task's branch after its task id (`orchestrator.py` sets
   `qt["branch"] = task_id`) — preferring the local ref and falling back to
   `origin/<task_id>`. `cmd_merge` now calls it with the `_task_id_from_plan(plan_path)`
   it already computes and no longer reads `git branch --show-current`.
2. **Fail closed when the branch cannot be resolved.** If neither `<task_id>` nor
   `origin/<task_id>` exists, `cmd_merge` aborts ("Refusing to record a merge that did
   not happen") instead of falling through to a no-op.
3. **Guard against self-merge before merging.** If the resolved
   `feature_branch == target_branch`, `cmd_merge` aborts before the gate — the single
   check that would have hard-failed all three cfg-\* cases at "Merging main into main."
4. **Post-merge ancestry verification (ported).** `_merge_into_target` now runs
   `git merge-base --is-ancestor <feature_branch> <target_branch>` after the push and
   returns failure if it does not hold. The pre-check (3) and this post-condition are
   **complementary, not redundant**: `--is-ancestor` alone cannot catch the reported bug
   because `main` is trivially an ancestor of `main`.
5. **Bookkeeping records the real branch.** The closure record now carries
   `branch=task_id`, so `record-merge` reflects the branch that was actually merged.

**Manual workaround used today (for the already-corrupted cfg-\* merges):**

- Reset `main` to remove the bogus merge-mark commit.
- In the task worktree, update the plan footer to `merged` and commit.
- Run `git merge <branch> --no-ff` from `main`.
- Push corrected history.

## Regression Test

Added to `tests/test_ship_merge.py`:

- `test_merge_resolves_feature_branch_from_task_not_checkout` — real temp repo whose
  HEAD is on `main` with a `t1` branch carrying a commit absent from `main`; drives
  `cmd_merge` and asserts the branch handed to the merge is `t1`, never the `main`
  checkout. Fails against the pre-fix `git branch --show-current` resolution.
- `test_resolve_feature_branch_uses_task_id_not_checkout` — the resolver returns the
  task's branch and fails closed (`None`) for an unknown task.
- `test_merge_refuses_self_merge` / `test_merge_fails_closed_when_branch_unresolvable`
  — the two `cmd_merge` fail-closed guards abort before any merge or closure.
- `test_merge_fails_closed_when_branch_not_ancestor` — `_merge_into_target` returns
  failure when the branch is not an ancestor of the target after the merge (the ported
  post-condition).

## Validation

- [x] Reproduction steps no longer trigger the bug — codified as
  `test_merge_resolves_feature_branch_from_task_not_checkout`.
- [x] Existing test suite passes with no new failures — 1202 passed; the lone failure,
  `test_max_jobs_three_integration_steps_serialize`, is the known `--dist=loadgroup`
  parallelism flake (passes in isolation, unrelated to `ship.py`).
- [x] No regressions observed in related functionality — all 16 `tests/test_ship_merge.py`
  cases pass, including the four pre-existing `cmd_merge`/`_merge_into_target` tests.

## Lessons Learned

- **Pattern:** Merge/ship commands that update bookkeeping metadata without verifying the actual code merge.
- **Systemic class:** This is the third instance of "`aet ship` resolves branch/base identity from ambient git state instead of the plan id" — alongside the base-resolver bug (`_determine_pr_base` returning the branch's own name as PR base) and the cwd-sensitivity of `ship open`/`close`. The class-level fix is: **derive branch and base identity from the plan/task id, never from cwd or the current checkout.** Closing the class retires all three at once.
- **Prevention:** Any ship/merge command should have a fail-closed post-condition check that the source branch is an ancestor of the target branch — and a pre-condition check that source ≠ target. Do not trust exit code 0 alone.
- **Regression vector:** The post-merge ancestry check existed only as _prose_ in `aet-ship/SKILL.md` (Steps 12–13, plan bs-01) and silently regressed when `ship` became Python code (nc-03a/b/c), which never ported it. Safety invariants that live only in skill narration are invisible to the code that replaces them — port fail-closed checks into the code, not the prose.
- **Reference:** This report feeds into `aet-evolve` and should inform updates to `aet-ship` skill references and the `aet ship merge` implementation.
