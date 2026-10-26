---
id: root-checkout-is-operator-owned
status: scope-validated
---

# PRD: The Root Checkout Is Operator-Owned

## Overview

An active `aet run` and the `/aet-drive` loop build every task in its own
worktree from `origin/<integration-branch>`. The root checkout plays no part in
what a task builds on. The run still writes to it, and the base-hygiene gate
still requires it to be clean. Two consequences follow:

1. Planning during a run halts the run. A new PRD in `docs/prds/` makes the
   working tree dirty, and the next `aet run` in the `/aet-drive` loop stops
   with "Working tree is dirty".
2. Editing the root during a run can lose work. The merge-train flush runs
   `git reset --hard <snapshot>` in the root when the root has the integration
   branch checked out, in `flush` (`src/aet/train.py`). The base-hygiene gate runs
   only at run start, so it does not protect an edit made mid-run.

ADR-044 §5 already states the rule: "No AET code path may run a git command in
`repo_root` that changes `HEAD` there. The operator's working tree is not AET's
to move." The flush, the integration recovery path and the closure archive move
break this rule. This PRD enforces it, widens it from `HEAD` to the working tree
and the index, and removes the gates that only exist because the rule was not
enforced.

The operator also cannot queue new work during a run. `aet sprint add` refuses
while a run holds the queue lease, in `lease_guard` (`src/aet/queue.py`), although
the run re-reads the queue on every scheduling pass, in `_spawn_pass`
(`src/aet/cli/orchestrator.py`).

## Intake Triage

Enhancement. The run-start refusal is designed behavior, not a defect. The
mid-run `reset --hard` is a latent data-loss path read from code and not yet
reproduced; R-9 makes it a regression test. Work class: `critical`, because the
change touches git state that holds unrecoverable operator work.

## Goals

- **G1**: The operator writes PRDs, plans, ADRs and source edits in the root
  checkout while a run is active, with no effect on the run and no risk to the
  edits.
- **G2**: The operator queues new tasks while a run is active, and the live run
  picks them up.
- **G3**: A task agent sees only the uncommitted documents its own task links.

## Non-Goals

- Commands the operator runs by hand on a branch checked out in the root, which
  act on that checkout by design: `aet ship gate`, `aet ship open` and
  `aet ship split` when the root is the task workspace. The code is in
  `_rebase_independent_branch`, `_run_gate` and `cmd_split`
  (`src/aet/cli/ship.py`).
- Changing where worktrees branch from. Worktrees keep branching from
  `origin/<integration-branch>` (ADR-044, ADR-045).
- Making PRD, ADR or other document durability the run's job. The operator
  commits documents, as today.
- Editing or removing tasks that a live run owns. The lease still blocks those
  mutations.
- Pulling or fast-forwarding the root after a run. The operator does that.

## Requirements

- **R-1**: No code path reachable from `aet run`, `aet run-one`, the merge
  train, `aet ship merge` or `aet ship close` changes the root checkout's
  `HEAD`, index or working tree.
- **R-2**: When the integration branch is checked out in any worktree, a green
  flush pushes the snapshot to `origin/<branch>` without force and updates
  `refs/remotes/origin/<branch>`. The local branch ref stays unchanged. A
  rejected push halts the flush fail-closed (ADR-029).
- **R-3**: When the integration branch is not checked out in any worktree, a
  green flush moves the local branch with `git update-ref` and an old-value
  check. A failed check halts the flush and names the branch, the expected tip
  and the actual tip.
- **R-4**: A project with no `origin` remote and the integration branch checked
  out in the root halts at run start. The message names the branch and tells
  the operator to check out another branch in the root or to add a remote.
- **R-5**: Integration never resets, cleans or rebases in the root. When the
  task branch is checked out in the root, or its worktree is missing,
  integration halts the task and names the branch and the condition. It does
  not fall back to the root.
<!-- aet-lint: off -->
- **R-6**: Closure does not move, write or stage plan files in the root. The
  plan archive step, `archive_plan_file` (`src/aet/closure.py`), is removed, as ADR-055 §4
  retired the archive.
<!-- aet-lint: on -->
- **R-7**: Base hygiene no longer checks the working tree, and no longer checks
  whether the integration branch is behind origin. It still halts when the
  local integration branch is ahead of origin with a path outside
  `docs/plans/`.
- **R-8**: A task worktree receives an uncommitted document from the root only
  when it is the PRD that the task record links and that PRD is untracked. No
  other untracked document is mirrored.
- **R-9**: A mirrored PRD does not appear in `git status` in the task worktree,
  and `git add -A` in that worktree does not stage it.
- **R-10**: `aet sprint add` and `aet sprint intake` succeed during a live run
  when they only add new tasks. The exemption lives in the queue layer, so
  both admission doors share it (ADR-066). The add takes the queue lock, and the live run spawns the new task
  on its next scheduling pass when the task is unblocked.
- **R-11**: Every queue mutation other than an add of a new task still refuses
  during a live run, with the existing lease message and `--force` override.
- **R-12**: When a flush leaves the local integration branch behind origin
  (R-2), the run summary states the branch and the number of commits it is
  behind.
- **R-13**: A regression test runs a green flush while the root has the
  integration branch checked out, a modified tracked file, a staged change and
  an untracked PRD. After the flush, all three are byte-identical, the index is
  unchanged, and `HEAD` points at the same commit.
- **R-14**: An ADR records that the root checkout is operator-owned. It extends
  ADR-044 §5 from `HEAD` to the working tree and index, narrows ADR-027 base
  hygiene, sets the flush target rule for ADR-079, and states the add-only
  exception to the run lease.
- **R-15**: Skill and reference text that tells the operator to keep the root
  clean before or during a run is updated to the new contract.

## User Stories

- As an operator, I want to write a PRD in the root while `/aet-drive` runs, so
  that planning and execution overlap. (satisfies: R-1, R-7, R-13)
- As an operator, I want my uncommitted edits in the root to survive every
  flush, so that a run never destroys work I did not hand to it. (satisfies:
  R-1, R-2, R-3, R-5, R-6, R-13)
- As an operator, I want to queue a newly planned task while a run is active,
  so that `/aet-drive` reaches it without a restart. (satisfies: R-10, R-11)
- As an operator, I want to know after a run that my local branch is behind
  origin, so that I pull before I commit. (satisfies: R-2, R-12)
- As a task agent, I want to see only the PRD my task links, so that another
  draft in the root does not steer my work or land in my commits. (satisfies:
  R-8, R-9)
- As a maintainer, I want the rule recorded once, so that later changes do not
  bring back root writes. (satisfies: R-14, R-15)

## Acceptance Criteria

- [ ] With an untracked `docs/prds/x-prd.md` and a modified tracked file in the
      root, `aet run` starts and runs. (satisfies: R-7)
- [ ] A green flush with the root on `main` leaves local `main` unchanged,
      moves `origin/main`, and keeps the root's edits byte-identical.
      (satisfies: R-1, R-2, R-13)
- [ ] A green flush on an epic branch that no worktree has checked out moves
      the local branch. A concurrent change to that branch halts the flush with
      both tips in the message. (satisfies: R-3)
- [ ] A project with no remote and the root on the integration branch halts at
      run start with the R-4 message. (satisfies: R-4)
- [ ] `aet ship merge` for a task whose branch is checked out in the root halts
      with a message and leaves the root unchanged. (satisfies: R-5)
- [ ] `aet ship close` and `aet ship merge` leave `docs/plans/active/<id>.md`
      in place and the root index unchanged. (satisfies: R-6)
- [ ] A local commit that touches `src/` and is not pushed still halts
      `aet run`. (satisfies: R-7)
- [ ] With two untracked PRDs in the root, a task worktree contains only the
      PRD its task links. `git status` in the worktree does not list it.
      (satisfies: R-8, R-9)
- [ ] `aet sprint add docs/plans/active/new.md` during a live run exits 0, and
      the run log shows the task spawned. (satisfies: R-10)
- [ ] A queue edit of a task the run owns, made during the run, refuses with
      the lease message. (satisfies: R-11)
- [ ] The run summary after an origin-only flush names the branch and its
      behind count. (satisfies: R-12)
- [ ] The new ADR exists and is linked from ADR-044, ADR-027 and ADR-079 by
      relation frontmatter. (satisfies: R-14)
- [ ] No text under `skills/` or `.agents/reference/` tells the operator to
      keep the root clean for a run. (satisfies: R-15)

## Technical Notes

### Root writes found in code

<!-- aet-lint: off -->
| Symbol | File | Write | Requirement |
| --- | --- | --- | --- |
| `flush` | `src/aet/train.py` | `reset --hard <snapshot>` in root when root HEAD is the integration branch | R-2 |
| `flush` | `src/aet/train.py` | `update-ref` with no old-value check otherwise | R-3 |
| `integrate` | `src/aet/integrate.py` | `reset --hard`, `clean -fd`, `rebase` in `worktree_dir`, which is the root when the root is on the task branch and the task worktree is missing | R-5 |
| `archive_plan_file` | `src/aet/closure.py` | moves the plan file and stages the move in the root index | R-6 |
| `squash_merge_task_branch` | `src/aet/worktree.py` | checkout, squash and commit in root; no callers | R-1, removed as dead code |
<!-- aet-lint: on -->

The flush reaches the train from `process_task` and `_spawn_pass`
(`src/aet/cli/orchestrator.py`), and from `cmd_merge` (`src/aet/cli/ship.py`).

### Why origin-only is safe

The train computes its base from `refs/remotes/origin/<branch>`, in
`train_tip` and `resolve_train_base` (`src/aet/train.py`). Merge verification
checks ancestry against `origin/<target>`, in `is_ancestor_of_trunk` and
`is_ancestor_of_target` (`src/aet/cli/aet_state.py`). Neither reads
the local integration branch while a remote exists. A local branch left behind
therefore does not change the next snapshot or the merge verdict.

A plain `update-ref` on a branch checked out in the root is not an option. The
root index then stays at the old tree. The operator's next commit records that
old tree and reverts the integrated work without any message.

### Detecting a checked-out branch

`git worktree list --porcelain` lists every worktree with its branch.
`_find_target_worktree` (`src/aet/cli/ship.py`) already parses it.

### Mirror exclusion

`.git/info/exclude` is shared by all worktrees, so it cannot hold a
per-task rule. A per-worktree exclude needs `extensions.worktreeConfig` and a
worktree-scoped `core.excludesFile`. `git update-index --skip-worktree` does not
apply, because the mirrored file is untracked. The plan selects the mechanism.
R-9 fixes the observable result.

### Live intake

ADR-066 makes `aet sprint add` the one admission path. R-10 keeps that path
and changes only the lease check: an add of a new task id takes the queue lock
and does not need the lease. The run already reloads the backend on each
scheduling pass.

### Integration branch resolution

In single-PR mode, a task that links a PRD integrates into a branch named by
the PRD frontmatter `branch` or the PRD file stem, in
`resolve_integration_branch_for_task` (`src/aet/branch_ref.py`). R-2 and R-3
apply to whichever branch
resolves, so no special case is needed.

## Risks

- **Operator commits on a stale `main`.** After an origin-only flush, the
  operator may commit on local `main` without a pull. The push then fails as
  non-fast-forward, which is safe. R-12 reduces the surprise.
- **Hygiene loses its dirty-tree signal.** The signal protected nothing once
  R-1 holds, because no run step reads the root tree. R-13 is the guard that
  replaces it.
- **Live intake races the scheduler.** The queue lock serializes the add and
  the run's write. A task added between a load and a write must survive the
  write. The plan names a test for this case.
- **No-remote projects lose one workflow.** Running with the root on the
  integration branch and no remote now halts (R-4). This setup is rare and
  needs one `git checkout` to fix.

## Open Questions

- R-4 halts a no-remote project whose root is on the integration branch. The
  alternative is `git merge --ff-only` in the root for that case only. That
  keeps the workflow but breaks R-1. The draft takes R-1.

## Divergence Summary

_Recorded: 2026-10-26 — Branch: rco-01_

### rco-01: Changed from plan

- rco-01 task 2: `push_branch` in `src/aet/worktree.py` takes an optional
  `commit`. With it, the push refspec is `<commit>:refs/heads/<branch>`, so the
  checked-out case pushes the snapshot without a local ref move.
- rco-01 task 2: the `update-ref` old value is the local tip that the flush
  reads under the lock when it takes the snapshot. An absent branch uses the
  zero OID. ADR-082 §2 records this rule.
- rco-01 task 3: the behind-origin notice prints after each per-task flush in
  `process_task` and `run_single`, and once at the end of `run_batch`.

### rco-01: Added (unplanned)

- rco-01: `tests/orchestrator/test_orchestrator.py` reads `origin/main`
  instead of `main`, because a checked-out branch no longer moves locally.
- rco-01: `tests/ship/test_open_epic.py` detaches the root before the flush.
  The fixture's origin is the repo itself, so a checked-out epic branch
  rejects the push.

### rco-01: Deferred

- None.

_Recorded: 2026-10-26 — Branch: rco-02_

### rco-02: Changed from plan

- rco-02 task 2: `cmd_merge` halts only when the task branch is checked out in
  the root. A missing task worktree does not halt `cmd_merge`. It allocates a
  temporary worktree outside the repository, so no command runs in the root.
  `integrate` halts on a missing worktree, as R-5 requires.

### rco-02: Added (unplanned)

- rco-02: `docs/CONVENTIONS.md` and `skills/aet-ship/SKILL.md` state that
  closure leaves `docs/plans/active/<id>.md` in place. The archive row and rule
  are removed, because they described the behavior that R-6 removes.
- rco-02: `tests/cli/test_ship_close.py` and `tests/ship/test_aet_ship.py`
  assert that the plan file stays in place. They asserted the archive move.
- rco-02: R-6 and the "Root writes found in code" table are wrapped in
  `aet-lint` off markers. They name `archive_plan_file` and
  `squash_merge_task_branch`, which no longer exist in code.

### rco-02: Deferred

- rco-02: `aet.change_scope.targets` selects deleted test files as pytest
  targets, so `make validate` exits with code 5 on a branch that deletes a
  test file. The fix is out of scope and is filed in the local backlog.
- rco-02 task 6: the merge to main happens at the ship stage.

---

_Stage: synced_

_Next step: run `aet-ship`_
