---
id: epi-06-state-heal-gap-and-reset
size: M
blocked_by: [epi-02-thread-resolver-through-consumers]
pipeline: standard
status: queued
security_review: skipped
security_review_reason: edits queue state records and adds a reset command over existing git reads; no new external surface
docs_sync: required
docs_sync_reason: adds the `aet state reset` command and changes what heal repairs — both user-visible
---

# Plan: Close the heal gap, clear runtime fields, and add task-level reset

## Context

- PRD: `docs/prds/non-trunk-integration-workflow-prd.md` (R-11, R-12, R-13)
- ADR: `docs/adr/044-base-branch-is-configured-not-assumed.md` (decision 7)
- Bug: `docs/bugs/2026-07-22-queue-reset-dead-end.md` (root causes #2, #3)

The heal gap is two lines, not a missing capability. `derive_status`
(`aet_state.py:148-234`) computes the incident discrepancy correctly — with
`branch_exists=False` and `plan_exists=True` it derives `ready` or `blocked`.
`cmd_heal` matches only (`merged`, `stored != merged`) at `:518`, (`ready`,
{`failed`, `blocked`, `planned`}) at `:526`, and (`failed`, `in_progress`) at
`:533`. The incident pair — (`ready`|`blocked`, `in_progress`) — matches
neither, so heal reported "No healable discrepancies found" against a visibly
wrong queue.

Blocked on `epi-02`: the git-derived state heal resets *to* is only correct
off-trunk once `derive_status` reads the resolved trunk.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] If a reproducible defect was described, redirected to `aet-bug-report`

Root causes #2 and #3 of the bug report are reproducible defects. They are
planned together because the reset primitive (R-13) and the heal rule (R-11)
are the same operation — recompute from git and clear runtime fields — exposed
at two granularities.

## Locked design

- **Heal consumes what it already computes.** Add the rule matching
  (`derived ∈ {ready, blocked}`, `stored ∈ {in_progress, awaiting_merge}`) when
  the recorded branch does not exist, resetting the task to its derived state.
  Do not change `derive_status` — it is already right.
- **`state audit` reports the same pair.** It shares `derive_status`, so
  detection is free; the requirement is that the report names it rather than
  falling through (PRD R-11).
- **Runtime fields are cleared, not just states moved.** Nothing in
  `aet_state.py` clears `branch` or `worktree` today (`_apply_transition` at
  `:268` moves states only). Heal repairs and reset clear `branch`, `worktree`,
  and any other runtime pointer whose referent no longer exists (R-12).
- **`aet state reset <task_id>`** recomputes state from git and blockers, sets
  `ready`/`blocked`, and clears runtime fields (R-13). It is the single-task
  form of what heal does across the queue, and it is the documented way to
  un-start a task — today only the terminal transitions (`merged`, `abandoned`)
  are supported, and neither fits.

## Task List

1. Add the missing heal rule and make `state audit` report the pair
   — S (traces: R-11)
2. Clear stale `branch`/`worktree` runtime fields in heal repairs
   — S (traces: R-12)
3. Add `aet state reset <task_id>`: recompute from git + blockers, set
   `ready`/`blocked`, clear runtime fields — M (traces: R-13)
4. Merge branch to main and verify integration — S

**Size definitions:** S ≤ 2 hr / ≤ 100 lines; M ≤ 1 day / ≤ 200 lines; L must be
re-evaluated.

### Batching Check

- [x] Not one of several near-identical additions — a heal rule, field clearing,
      and a new command, batched because they are one operation at two
      granularities
- [x] The diff is expected to exceed 3 files or 50 lines
- [x] Cannot share a branch with `epi-05` — different module, different blocker
      (`epi-02`), different incident

## Rejected Alternatives

- **Teach `_apply_transition` to clear fields on every transition** — rejected:
  most transitions legitimately keep `branch` (e.g. `awaiting_merge` needs it
  for merge verification). Clearing is a property of the repair, not the
  transition.
- **Make reset a flag on heal (`heal --task`)** — rejected: heal is a sweep
  with a report; reset is a pointed, single-task operation an operator runs
  deliberately. One command with two granularities reads worse than two.
- **Widen the `:526` tuple to include `in_progress`** — rejected: that tuple is
  `derived == ready`; the incident pair also includes `derived == blocked`, and
  a tuple edit would silently drop the branch-existence condition that makes
  the repair safe.

## Files to Modify

- `src/aet/cli/aet_state.py`
- `tests/state/test_heal_missing_branch.py` (new)
- `tests/state/test_state_reset.py` (new)

## Validation Steps

- [ ] Lint passes
- [ ] Tests pass
- [ ] New source coverage: `tests/state/test_heal_missing_branch.py` asserts
      `state heal --apply` on an `in_progress` task whose branch was deleted
      moves it to its derived state and leaves `branch`/`worktree` cleared —
      demonstrated **failing** against the current "No healable discrepancies
      found" fall-through
- [ ] New source coverage: `tests/state/test_state_reset.py` asserts reset
      un-starts a task and the queue then round-trips through `init-queue`
      unchanged
- [ ] `state audit` output names the (`ready`|`blocked`, `in_progress`) pair
- [ ] The `awaiting_merge` case is covered alongside `in_progress`
- [ ] R-trace coverage: R-11 by task 1; R-12 by task 2; R-13 by task 3
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the commit. Heal returns to under-reporting and reset disappears; any
queue already repaired stays repaired because repairs are state edits, not
schema changes.

## Pipeline

`standard`.

---

*Stage: plan-approved*
*Next step: run `aet-work`*
