# Issue: resetting a stuck queue is a dead end; deleting it is unrecoverable

**Date:** 2026-07-22
**Component:** `aet init-queue`, `aet state heal`, `aet state transition`
(`src/aet/...`)
**Severity:** medium — no data loss possible (queue is ephemeral/gitignored),
but an operator can back themselves into a state where the sprint board cannot
be regenerated and there is no supported command to fix it.
**Status:** open. Queue file for `example-service` is currently absent; the run
is on hold pending the ADR-044/045 rework.

## Context

This follows the worktree-hijack incident
(`docs/bugs/2026-07-22-orchestrator-base-branch-hardcoded.md`). After recovering
the operator's worktree and deleting the bogus task branches, the ephemeral
`.agents/work-queue.json` was left in an inconsistent state and every attempt to
clean it up hit a wall.

## What happened

Starting state after recovery: the queue held
`abc-123-s8` as `in_progress` with `branch` and `worktree`
fields pointing at a branch/dir that had just been deleted, and
`abc-123-s2` `ready` but with the same kind of stale
`branch`/`worktree` fields.

1. **`aet init-queue`** — re-derived clean state for every task *except* the two
   pre-existing entries: it **preserved** `s8`'s `in_progress` and both tasks'
   stale `branch`/`worktree`. `init-queue` merges onto existing entries rather
   than resetting non-terminal runtime state.

2. **`aet state heal --apply`** — reported **"No healable discrepancies found"**
   and changed nothing, even though `s8` was `in_progress` with a `branch` that
   no longer exists and a `worktree` directory that no longer exists. From git
   ground truth that is plainly a discrepancy (no branch ⇒ cannot be
   `in_progress`), but heal did not detect it.

3. **No task-level reset exists.** There is no documented command to move a task
   from `in_progress` back to `ready`/`blocked`, or to clear stale
   `branch`/`worktree` fields. The only supported manual transitions are the
   terminal ones (`merged`, `abandoned`), neither of which fits a task that
   simply needs to un-start.

4. **Deleting the queue to force a clean rebuild failed closed.** Removing
   `work-queue.json` (+ empty `work-history.jsonl`) and re-running
   `aet init-queue` wrote **no file at all**. `init-queue` validates **every**
   `docs/plans/*.md` in the directory, and this shared repo contains 17
   *unrelated* plans from other features (`abc-200-*`, `legacy-*`, …) with
   statuses it rejects (`completed`, `partially_implemented`) and
   `rtrace`/`scope` errors. Those unrelated failures aborted the whole rebuild.
   Because the queue is gitignored, it cannot be restored from git either.

Net: the operator can reach a state where the queue is stuck *and* cannot be
regenerated, with no supported recovery command.

## Root causes

1. **`init-queue` validation scope is the entire plans directory.** Unrelated or
   legacy plans that fail validation block regenerating a queue that only needs
   a subset. It should build from the plans it is including and *warn-and-skip*
   invalid siblings rather than fail closed on them.
2. **`state heal` does not detect `in_progress`-without-branch.** Its
   stale-worktree repair only fires when a `worktree` field points at a missing
   directory; it misses a task whose recorded `branch` is gone, which should
   reset the task to its git-derived state and clear the stale fields.
3. **No task-level reset primitive.** There is no `aet state reset <task>` (or
   equivalent) to un-start a task and clear runtime fields.
4. **ADR-013 assumption violated.** ADR-013 treats the sprint board as ephemeral
   and safe to lose because it can be regenerated from plans. Root cause #1
   breaks that guarantee in any repo whose `docs/plans/` also holds unrelated or
   legacy plans — which is the norm for a shared repo.

## Recommendation

1. Scope `init-queue` (and `queue sync`) validation to the plans being added;
   warn-and-skip invalid unrelated plans instead of aborting. Never leave the
   queue file unwritten because of a plan the caller did not ask to include.
2. Add `aet state reset <task_id>`: recompute the task's state from git +
   blockers, set `ready`/`blocked`, and clear `branch`/`worktree`/`in_progress`.
3. Extend `state heal` / `state audit` to flag and repair
   `in_progress` (or `awaiting_merge`) with no existing local branch.
4. Make deleting the queue a supported reset path: `init-queue --force` (or
   `--only <glob>`) that rebuilds from a plan subset regardless of sibling plan
   validity.

## Current workaround

None applied (holding off per operator). To rebuild the `example-service` queue
manually when work resumes, reconstruct the 11 `abc-123-*` tasks from each
plan's frontmatter (`id`, `blocked_by`) with clean states — the plan frontmatter
is the source of truth (ADR-013). This should not be necessary once #1/#4 land.

## Verification against `aiskills@main` (2026-07-22, added during planning)

Both root causes confirmed. Root cause #2 is more specific than reported, and
the precise gap is worth recording because it explains the misleading
"No healable discrepancies found" exactly.

**Root cause #1 — confirmed, with the ordering pinned.** `init_queue.py`
validates the full `plan_files` set and returns `1` on any finding (`:230-238`)
**before** the per-plan `is_settled_plan` skip at `:253` and the
`is_sprint_member` skip at `:260`. So a plan that would be skipped anyway still
aborts the rebuild. This is the same ordering defect already recorded for
`frh-17`/`frh-18`; the shared-repo case (17 unrelated plans) is a second, worse
instance of it, because there the invalid plans are not merely stale — they
belong to other people's features and will never be fixed by this operator.

**Root cause #2 — confirmed, and the gap is two lines.** `derive_status`
(`aet_state.py:148-234`) is *not* blind to the missing branch: with
`branch_exists=False` and `plan_exists=True` it correctly derives `ready` or
`blocked`. The failure is in `cmd_heal`, which matches only these pairs:

- `aet_state.py:518` — `derived == merged`, `stored != merged`
- `aet_state.py:526` — `derived == ready`, `stored ∈ {failed, blocked, planned}`
- `aet_state.py:533` — `derived == failed`, `stored == in_progress`

The incident state was `derived ∈ {ready, blocked}` with `stored == in_progress`.
`stored` is absent from the `:526` tuple and `derived` never equals `failed`
(that requires `plan_exists=False`), so the task falls through **every** branch
and heal reports nothing to do. It is not that heal cannot see the discrepancy —
it computes it correctly and then has no rule that consumes it.

**Root cause #3 — confirmed.** Nothing in `aet_state.py` clears `branch` or
`worktree`. `_apply_transition` (`:268`) moves states; no code path resets
runtime fields, so even a correct transition would leave the stale pointers.

**Consequence not in the report:** because `is_ancestor_of_main`
(`aet_state.py:69`) hardcodes `origin/main`, `derive_status` cannot derive
`merged` at all in a `dev`-based repo. In such a project heal's primary repair
(`:518`) is permanently unreachable, and dependent tasks never unblock. Fixing
the heal gap without also generalizing the trunk ref would leave that intact.
