---
name: aet-ship
description: Judgment residue for aet-ship merge-verification edge cases. Use only when `aet ship close` fails with an ambiguous merge-verification result and you need a decision procedure. The pre-merge gate, PR creation, and post-merge closure are implemented in `aet ship`.
---

# aet-ship

The aet-ship workflow is now implemented in code:

- `aet ship <plan_file>` — run the gate, then open a PR.
- `aet ship gate <plan_file>` — run the pre-merge gate only.
- `aet ship open <plan_file>` — run the gate and open a PR.
- `aet ship close <task_id> <plan_file>` — record post-merge closure.

## When to Use This Skill

Only when `aet ship close` reports an ambiguous merge-verification failure and you must decide whether to proceed with manual verification.

## Decision Procedure for Ambiguous Merge Verification

1. Do not delete the feature branch.
2. Run `git fetch origin` and confirm the branch is not an ancestor of `origin/main`.
3. Check the PR page for the merge commit SHA.
4. If the merge commit is on `origin/main`, re-run `aet ship close --merge-commit <sha> <task_id> <plan_file>`.
5. If the merge commit is not on `origin/main` and the PR shows as merged, inspect the repository for a force-push or base-branch change; ask the user before overriding with `--merge-commit`.
