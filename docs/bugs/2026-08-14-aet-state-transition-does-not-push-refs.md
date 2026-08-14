# Bug: `aet-state transition` updates local refs but never pushes them

## Summary

When the git-refs backend is active, `aet-state transition` writes the new task
state to the local `refs/aet/tasks/<id>` ref but does **not** call
`backend.push()`. Because `backend.fetch()` uses the force refspec
`+refs/aet/*:refs/aet/*`, any later read-only command (e.g. `aet status`) pulls
the stale ref from origin and silently overwrites the local `in_progress` state
back to `ready`.

## Environment

- ae-toolkit source repo at current `main` (2026-08-14)
- Backend: `git-refs` (`task_backend: git-refs` in `.agents/aet-config.json`)
- Remote: `origin` with a pre-existing `refs/aet/tasks/<id>` ref

## Reproduction

```bash
# 1. Ensure origin has the task ref in state 'ready'.
# 2. Start a run that transitions the task to in_progress.
aet run-one docs/plans/owb-01-spec-travels-in-task-record-plan.md

# 3. In another shell / machine, or even the same checkout after the orchestrator
#    has transitioned locally:
aet status
```

Observed:

- The orchestrator logs that the task was transitioned to `in_progress`.
- `aet status` reports the task as `ready`.
- Repeating `aet status` keeps it `ready`.
- Manually force-pushing `refs/aet/tasks/<id>` to origin makes `aet status`
  report `in_progress`.

## Root cause

`aet-state transition` is implemented in `cmd_transition`
(`src/aet/cli/aet_state.py:1180`). The flow is:

1. `backend.fetch()` — force-fetches `refs/aet/*` from origin.
2. Apply the transition under `queue_lock` via `_apply_transition`, which calls
   `backend.save(queue)`.
3. Print success and exit.

There is no `backend.push()` call at the end of `cmd_transition`.

Other `aet-state` subcommands **do** push:

- `cmd_set_stage` → `backend.push()` at `src/aet/cli/aet_state.py:730`
- `cmd_record_merge` → `backend.push(mandatory=True)` at `:1395`

So state transitions (`ready -> in_progress`, `in_progress -> awaiting_merge`,
`ready -> blocked`, `in_progress -> failed`, etc.) are invisible to other
machines, while stage changes and terminal closure are replicated.

The orchestrator triggers the start transition through `aet-state transition`
(`src/aet/cli/orchestrator.py:2876` for batch, `:3066` for run-one), so the bug
is hit on every normal run start.

## Impact

- Multi-machine / multi-clone realtime queue sync is broken for the most common
  state change.
- `aet status` and any other fetch-on-read command act as a silent revert of
  the local `in_progress` ref.
- The orchestrator can believe it started a task while every other observer
  (including a later `aet status` from the same checkout) sees it as `ready`.
- This explains the observed symptom where the orchestrator logged a successful
  `in_progress` transition but the ref stayed `ready` until a manual push.

## Fix

Add `backend.push()` after `backend.save(queue)` in `cmd_transition`, mirroring
`cmd_set_stage`.

```python
# src/aet/cli/aet_state.py, inside cmd_transition after _apply_transition succeeds
backend.push()
```

Because `backend.push()` is best-effort by default, a network or forge failure
will not block the local transition; it will return `False` and the local ref
remains authoritative. A subsequent successful `aet status` on the same machine
will still see `in_progress`. The current force-fetch behavior then becomes
safe: origin and local agree once a push succeeds, and a failed push no longer
leaves origin as the hidden winner.

Optionally, the orchestrator could also push immediately after the transition
subprocess returns, but the canonical place to fix this is inside `aet-state`
itself: every transition should be replicated, not just the ones the
orchestrator happens to issue.

## Fix follow-up: forced push refspec (found during regression testing)

The end-to-end regression test exposed a second defect underneath this one:
`GitRefsBackend.push()` used the unforced refspec `refs/aet/*`. Because every
ref in the namespace points to a **blob**, git rejects *any* update to a
remote ref that already exists ("You cannot update a remote ref that points at
a non-commit object … without using the '--force' option"). So even the
existing pushes in `cmd_set_stage` and `cmd_record_merge` silently failed
(best-effort `False`) whenever the task ref was already on origin — the common
case. The push refspec is now `+refs/aet/*`, mirroring the forced fetch
refspec; last-writer-wins is the documented model for this backend-owned
namespace (ADR-055).

## Validation

- [x] Add a regression test that sets up a repo with a remote, runs
  `aet-state transition ...` on one clone, then asserts the remote ref reflects
  the new state. (`test_aet_state_transition_pushes_refs_to_remote` in
  `tests/backends/test_git_refs_sync.py`; plus a FakeBackend unit test that
  `cmd_transition` calls `backend.push()` after `save`.)
- [x] Add a regression test that simulates the `aet status` revert: local
  transition without push, then `backend.fetch()` from origin, then load shows
  the old state. (`test_fetch_reverts_unpushed_local_transition`.)
- [x] Run `make validate`.

## Related code

- `src/aet/cli/aet_state.py:1180` — `cmd_transition` (missing push)
- `src/aet/cli/aet_state.py:729` — `cmd_set_stage` (pushes)
- `src/aet/cli/aet_state.py:1395` — `cmd_record_merge` (mandatory push)
- `src/aet/backends/git_refs_backend.py:40` — force fetch spec
- `src/aet/cli/orchestrator.py:2876` — batch path calls `aet-state transition`
- `src/aet/cli/orchestrator.py:3066` — run-one path calls `aet-state transition`
