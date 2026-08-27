# Bug Report: `aet ship merge` checks the ambient checkout while merging the resolved task ref

## Metadata

- **Reported:** 2026-08-27
- **Severity:** low (latent — the precondition held in the one batch measured)
- **Status:** open

## Symptoms

None observed. The defect is a precondition that is neither documented nor
enforced, so it holds by operator habit rather than by construction.

`aet ship merge <task-id>` resolves what to merge from the task id, and resolves
what to check from whatever branch happens to be checked out. When those differ,
the command prints three true statements about a tree it is not about to merge:

```
   Gate passed.
Checking for merge conflicts against origin/main...
   No conflicts detected.
Merging <feature-branch> into main...
```

Run from a `main` checkout, "Gate passed" reports `make validate` on `main`, the
conflict check compares `main` to `origin/main`, and the branch is then merged
unvalidated.

## Reproduction Steps

1. Complete a task so its branch reaches `awaiting_merge`.
2. Commit a change on that branch that fails `make validate`.
3. From the primary checkout with `main` checked out, run
   `aet ship merge <task-id>`.

Not executed. Confirming it means merging a known-broken branch to trunk, so the
evidence below is structural rather than observed.

## Root Cause

`_resolve_feature_branch` (`src/aet/cli/ship.py:102-115`) is deliberate about the
merge source, and its docstring says so: the branch is the `task_id` ref,
"never whatever branch happens to be checked out."

Every check reads `HEAD` in the working directory instead:

- `_run_gate` (`:470`) runs `make validate` in the cwd
- `_rebase_independent_branch` (`:441-445`) rebases `git branch --show-current`
- `_has_merge_conflicts` (`:930-936`) merge-trees `HEAD` against the target
- `_commit_count` (`:628`) and `_is_monolithic_commit` count `pr_base..HEAD`

Nothing asserts that `HEAD` is `feature_branch`, and
`skills/aet-ship/SKILL.md` does not state that the command must run from the
task's branch.

## Measurement

Fifteen merges from the 2026-08-27 batch in the consuming repository, comparing
each merge's `merge-base(^1, ^2)` against its first parent:

- 14 of 15 show the feature branch rebased onto the trunk tip before merge.
- 1 does not: `nrc-02-hold-classification-plan`.

A rebased second parent is what `_rebase_independent_branch` produces, so in
those 14 the gate was standing on the feature branch and `make validate` ran on
the merge result. The precondition held. `nrc-02` is an open thread — it may
simply have merged first in its group, before the trunk moved beneath it.

## Consequences

The gate is stronger than it appears, and that is the finding worth recording
alongside the defect. Because `_run_gate` rebases onto the fetched trunk *before*
running `make validate`, a serialized sequence of `aet ship merge` calls does
check each merge result against the trunk the previous merge just advanced. A
cross-branch semantic break — a requirement anchor claimed twice, a field made
required that a sibling's test does not pass — is therefore caught at merge, not
missed, provided the operator is on the branch.

What still does not compose is the per-branch pipeline verdict. QA, review and
security each evaluate a tree no sibling's changes have reached, so their passes
say nothing about the union. The catch happens at ship, after every expensive
stage has run.

## Fix Direction

Run the checks against the resolved ref rather than the ambient checkout.
`_merge_into_target` (`:986-1090`) already builds a worktree with the target
checked out, pulls, and merges `--no-ff` before pushing; gating inside that
window is `subprocess.run(..., cwd=worktree)` plus a reset on failure. That
removes the implicit cwd dependency rather than documenting around it.

~~Interim, one line: refuse when `HEAD` is not `feature_branch`.~~ **Withdrawn
2026-08-27.** Attempted and reverted: the guard contradicts a shipped fix.
`903c4f55` ("resolve merge source from task id, not the checkout") exists
precisely because `aet ship merge` is run from a trunk checkout, and
`test_merge_resolves_feature_branch_from_task_not_checkout` pins that shape with
a real repo whose HEAD is on `main`. Four further tests in
`tests/test_ship_merge.py` merge from `main` as their normal case. Refusing on
`HEAD != feature_branch` would forbid the workflow that regression test was
written to protect, so the "interim" line is not additive — it is a behaviour
reversal that needs the same deliberation as the structural fix.

That leaves the structural fix as the only route, and it is the better one
anyway: gating inside `_merge_into_target`'s worktree validates the tree that is
actually about to merge *while preserving checkout independence*, so it needs no
guard and breaks no existing caller.

Documentation, independent of either: state in `skills/aet-ship/SKILL.md` that a
parallel batch's per-branch verdicts do not compose, and that the rebase inside
the gate is what makes serialized merges safe.
