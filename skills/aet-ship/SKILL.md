---
name: aet-ship
description: Pre-merge validation, PR creation, merge, and post-merge closure for AET tasks. Use when a task reaches awaiting_merge, when opening or merging a PR, or when `aet ship close` reports an ambiguous merge-verification result.
---

# aet-ship

Pre-merge gate, PR creation, merge, and post-merge closure for AET tasks.

## When to Use

- A task has reached `awaiting_merge` and you need to open or merge its PR
- You want to run the pre-merge gate (`aet ship gate`) before opening a PR
- You need to merge a task branch directly into its target branch
- `aet ship close` reports an ambiguous merge-verification result and you need a decision procedure

## Commands

- `aet ship <plan_file|task_id>` — run the gate, then open a PR.
- `aet ship gate <plan_file|task_id>` — run the pre-merge gate only.
- `aet ship open <plan_file|task_id>` — run the gate and open a PR.
- `aet ship merge <plan_file|task_id> --branch <target>` — run the gate, detect conflicts against the target branch, merge directly into it, and record closure. `--branch` defaults to the resolved trunk branch.
- `aet ship close <plan_file>` — record post-merge closure (task id derived from plan frontmatter).
- `aet ship close <task_id>` — record post-merge closure (plan derived from the queue task's `plan_file`).
- `aet ship close <task_id> <plan_file>` — record post-merge closure with explicit identifiers.

A bare task id given to `aet ship`, `aet ship gate`, `aet ship open`, or `aet ship merge` resolves to the conventional `docs/plans/<task_id>.md` path.

`aet ship merge` checks for merge conflicts against `origin/<target>` before merging and records the resulting merge commit in the work queue.

## Integration Modes

### `pr-per-task` (default)

Each task ships in its own PR to the resolved trunk branch. Typical flow:

```bash
aet ship open docs/plans/FEAT-001.md
# After the PR merges:
aet ship close FEAT-001
```

### `single-pr` (epic mode)

Tasks integrate into a shared Integration Branch (`--base`) and the epic ships
as one PR to trunk. Typical flow:

```bash
# Start or continue the epic on the integration branch
aet run --base feat/epic-name

# When the epic branch is ready to merge to trunk, ship it directly:
aet ship merge feat/epic-name --branch main

# Close each task that was part of the epic, pointing at the epic branch as
# the integration target and the trunk merge commit if needed:
aet ship close FEAT-001 --target-branch feat/epic-name
```

`--target-branch` tells `aet ship close` which branch the task merged into.
Use the configured integration branch (the epic branch) for per-task closure;
use `main` when closing the epic itself after it merged to trunk.

## Merge Verification

`aet-ship` resolves the trunk branch from config →
`refs/remotes/origin/HEAD` → `main`. It never hardcodes `origin/main` as the
verification target. Run `aet setup verify` to see the resolved trunk for the
current checkout.

For squash merges, the original branch commits are not ancestors of the trunk
branch. `aet ship close` accepts `--merge-commit <sha>` to record the squashed
commit that actually landed on trunk.

## Decision Procedure for Ambiguous Merge Verification

Use this only when `aet ship close` reports an ambiguous merge-verification
failure and you must decide whether to proceed with manual verification.

1. Do not delete the feature branch.
2. Run `git fetch origin` and confirm the branch is not an ancestor of the resolved trunk branch.
3. Check the PR page for the merge commit SHA.
4. If the merge commit is on the resolved trunk branch, re-run `aet ship close --merge-commit <sha> <task_id> <plan_file>`.
5. If the merge commit is not on the resolved trunk branch and the PR shows as merged, inspect the repository for a force-push or base-branch change; ask the user before overriding with `--merge-commit`.
