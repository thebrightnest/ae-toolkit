---
name: aet-ship
description: Judgment residue for aet-ship merge-verification edge cases. Use only when `aet ship close` fails with an ambiguous merge-verification result and you need a decision procedure. The pre-merge gate, PR creation, and post-merge closure are implemented in `aet ship`.
---

# aet-ship

The aet-ship workflow is now implemented in code:

- `aet ship <plan_file|task_id>` — run the gate, then open a PR.
- `aet ship gate <plan_file|task_id>` — run the pre-merge gate only.
- `aet ship open <plan_file|task_id>` — run the gate and open a PR.
- `aet ship merge <plan_file|task_id> --branch <target>` — run the gate, detect conflicts against the target branch, merge directly into it, and record closure.
- `aet ship close <plan_file>` — record post-merge closure (task id derived from plan frontmatter).
- `aet ship close <task_id>` — record post-merge closure (plan derived from the queue task's `plan_file`).
- `aet ship close <task_id> <plan_file>` — record post-merge closure with explicit identifiers.

A bare task id given to `aet ship`, `aet ship gate`, `aet ship open`, or `aet ship merge` resolves to the conventional `docs/plans/<task_id>.md` path.

`aet ship merge` requires `--branch` so the target branch is always explicit. It checks for merge conflicts against `origin/<target>` before merging and records the resulting merge commit in the work queue.

## When to Use This Skill

Only when `aet ship close` reports an ambiguous merge-verification failure and you must decide whether to proceed with manual verification.

## Decision Procedure for Ambiguous Merge Verification

1. Do not delete the feature branch.
2. Run `git fetch origin` and confirm the branch is not an ancestor of `origin/main`.
3. Check the PR page for the merge commit SHA.
4. If the merge commit is on `origin/main`, re-run `aet ship close --merge-commit <sha> <task_id> <plan_file>`.
5. If the merge commit is not on `origin/main` and the PR shows as merged, inspect the repository for a force-push or base-branch change; ask the user before overriding with `--merge-commit`.
