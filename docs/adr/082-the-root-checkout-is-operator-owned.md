---
subject: root-checkout
relates: [27, 29, 44, 55, 66, 79]
---

# The Root Checkout Is Operator-Owned

## Status

Proposed (2026-10-26). Delivered by `rco-01` to `rco-05` (PRD:
`docs/prds/root-checkout-is-operator-owned-prd.md`). Extends ADR-044 §5,
narrows ADR-027, and sets the flush target rule for ADR-079.

## Context

Task worktrees branch from `origin/<integration-branch>` (ADR-044, ADR-045).
The root checkout does not change what a task builds on. Three run steps still
write to it:

- `flush` (`src/aet/train.py`) runs `git reset --hard <snapshot>` in the root
  when the root has the integration branch checked out.
- `integrate` (`src/aet/integrate.py`) runs `reset --hard`, `clean -fd` and
  `rebase` in the root when the root has the task branch checked out and the
  task worktree is missing.
- `archive_plan_file` (`src/aet/closure.py`) moves a plan file in the root and
  stages the move, although ADR-055 §4 retired the archive.

ADR-044 §5 forbids AET code from changing `HEAD` in `repo_root`. These writes
break that rule, or break its purpose.

ADR-027 base hygiene halts a run on any dirty non-plan path, and on a local
integration branch behind origin. ADR-054 narrowed the dirty check for
`docs/plans/` only. A new PRD in the root therefore halts the next `aet run`.
The check runs only at run start, so it does not protect an edit made during a
run.

The run lease also blocks `aet sprint add` and `aet sprint intake` for the whole
run, although the run reloads the queue on every scheduling pass.

## Decision

1. **The root checkout is operator-owned.** No code path reached from
   `aet run`, `aet run-one`, the merge train, `aet ship merge` or
   `aet ship close` changes the root checkout's `HEAD`, index or working tree.
   This extends ADR-044 §5 from `HEAD` to the index and the working tree.
2. **Flush target.** When the integration branch is checked out in any
   worktree, a green flush pushes the snapshot to origin without force and sets
   `refs/remotes/origin/<branch>`. The local branch ref does not move. When the
   branch is checked out in no worktree, the flush moves the local ref with
   `git update-ref` and an old-value check. A rejected push or a failed
   old-value check halts the flush fail-closed (ADR-029). This states which ref
   ADR-079 §3 fast-forwards.
3. **No plain ref move on a checked-out branch.** Moving a checked-out branch
   with `update-ref` leaves the root index at the old tree. The next operator
   commit then records the old tree and reverts the integrated work.
4. **Integration never falls back to the root.** When the task worktree is
   missing, or the root has the task branch checked out, integration halts the
   task with a message.
5. **Base hygiene checks only what the run depends on.** The dirty-tree check
   and the behind-origin check are removed. The ahead-of-origin check stays for
   any path outside `docs/plans/` (ADR-054 alternative 4). A project with no
   remote and the integration branch checked out in the root halts at run
   start, because decision 2 has no origin to push to.
6. **A task worktree receives only its linked PRD.** The mirror copies the PRD
   that the task record links, and only when it is untracked. The copy is
   excluded from that worktree's commits by a worktree-scoped exclude.
7. **Add-only intake passes the lease.** A queue write that adds only new task
   ids takes the queue lock and does not need the run lease. The exemption
   lives in the queue layer, so both ADR-066 doors share it. Every other queue
   mutation still needs the lease.

## Consequences

- **Easier:** The operator writes PRDs, plans and code in the root during a run.
- **Easier:** The operator queues new work during a run, and `/aet-drive`
  reaches it without a restart.
- **Easier:** A task agent no longer sees unrelated drafts from the root.
- **Harder:** After a run, the operator's local integration branch is behind
  origin, and the operator pulls. The run summary names the branch and the
  behind count.
- **Harder:** A no-remote project cannot run with the root on the integration
  branch.
- **Neutral:** ADR-027's guarantee holds in a narrower form. An unpushed code
  commit still halts a run, so no worktree builds from a base that omits local
  code.

## Alternatives Considered

1. **`git merge --ff-only` in the root.** Rejected. It writes to the operator's
   working tree and stalls the flush on any overlapping edit.
2. **Exempt more paths from the dirty check.** Rejected. The check protects
   nothing once decision 1 holds, and a path list grows with every new
   directory.
3. **Flush into a dedicated integration worktree.** Rejected. Git refuses to
   check out a branch that the root already has checked out.
4. **Commit the linked PRD with the task's PR.** Rejected. A PRD shared by
   several tasks lands in the first PR, and later tasks race on it.
5. **Defer intake to the next run.** Rejected. `/aet-drive` would not reach the
   task until the current run ends.
