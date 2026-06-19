---
id: aet-work-state-refactor-derive-plan
blocked_by:
  - aet-work-state-refactor-status-next-plan
size: M
---

# Plan: Make `aet-state derive` Blocker-Aware

## Context

- PRD: `docs/prds/aet-work-queue-state-refactor-prd.md`
- ADR: `docs/adr/010-queue-derived-state.md`
- Current `aet-state derive` ignores `blocked_by` and returns `planned` for any task without a branch. This conflicts with `sync`, which promotes blocker-satisfied tasks to `unblocked`, and causes false mismatch warnings in `status`.

## Tasks

1. ✓ **Update `aet-work/bin/aet-state` `derive_status`** — M [Changed: uses a recursive `blocker_status_fn` callback instead of a full-queue/blocker-map argument; behavior matches the plan.]

   - Accept the full queue (or blocker map) so the helper can inspect `blocked_by` statuses.
   - Apply the derivation rules in order:
     1. `merged` if branch or `merge_commit` is an ancestor of `origin/main`.
     2. `in-progress` if local branch exists.
     3. `unblocked` if plan exists, no branch, and all blockers are terminal (`merged`/`abandoned`).
     4. `blocked` if plan exists, no branch, and some blocker is not terminal.
   - If `plan_file` is missing, report drift rather than returning a status.
   - Keep existing warning logic for `done` without merge verification during the transition.

2. ✓ **Remove `promote_dependents` from `aet-work/lib/queue.py`** — S

   - Delete the function and any internal callers.
   - The orchestrator and `next` will rely on derived `unblocked` instead.

3. ✓ **Update `aet-work/SKILL.md` `derive` section** — S
   - Document that `derive` is the single source of truth for actionable state and that it respects `blocked_by`.
   - Remove language suggesting `sync` or `init-queue` should promote tasks to `unblocked`.

## Dependencies

- None.
- This plan blocks `aet-work-state-refactor-status-next-plan.md`.

## Validation Steps

- [ ] `python3 aet-work/bin/aet-state derive .agents/work-queue.json` returns `unblocked` for a task whose blockers are `merged`/`abandoned` and that has no branch.
- [ ] The same command returns `blocked` for a task whose blockers are not terminal.
- [ ] `make lint` passes.
- [ ] `make format-check` passes.
- [ ] `make validate` passes.
- [ ] `make package` regenerates `.skill` files.

## Rollback Plan

1. Revert `aet-work/bin/aet-state` to the previous derive logic.
2. Restore `promote_dependents` in `aet-work/lib/queue.py`.
3. Revert the `derive` section in `aet-work/SKILL.md`.
4. Run `make validate && make package`.

---

_Stage: synced_
_Next step: run `aet-ship`_
