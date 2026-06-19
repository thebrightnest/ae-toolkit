---
id: aet-work-state-refactor-status-next-plan
blocked_by:
  - aet-work-state-refactor-derive-plan
  - aet-work-state-refactor-sync-init-plan
size: M
---

# Plan: Update `status`, `next`, and Orchestrator to Use Derived State

## Context

- PRD: `docs/prds/aet-work-queue-state-refactor-prd.md`
- ADR: `docs/adr/010-queue-derived-state.md`
- Once `derive` is blocker-aware and `sync`/`init-queue` store only facts, the read side of the queue must use derived state instead of relying on a stored `unblocked` label.

## Tasks

1. **Update `aet-work/bin/status`** — M

   - Call `aet-state derive` and use the returned derived status for counts and listings.
   - Remove the stored-vs-derived mismatch-warning column for ordinary `planned`/`blocked`/`unblocked` tasks.
   - Keep drift reporting and worktree validation.
   - Continue to report `failed` tasks from stored status.

2. **Update `aet-work/bin/next`** — M

   - Derive pickable tasks before selecting one.
   - Pick the first `unblocked` task in topological order.
   - Transition it to `in-progress` and set `branch` / `worktree`.
   - Refuse to proceed if plan drift is detected.

3. **Update `aet-work/bin/orchestrator`** — M

   - Replace `get_next_unblocked(queue)` with a derive step that finds tasks whose derived status is `unblocked`.
   - Continue to transition selected tasks to `in-progress`.

4. **Update `aet-work/SKILL.md` read-side commands** — S

   - Update `status`, `next`, `run`, and `run-one` sections to describe derived state.
   - Remove language that treats stored `unblocked` as the source of truth.

5. **Validate and package** — S
   - Run `make lint`, `make format-check`, `make validate`, and `make package`.

## Dependencies

- `aet-work-state-refactor-derive-plan.md`
- `aet-work-state-refactor-sync-init-plan.md`

## Validation Steps

- [ ] `aet-work status` shows `unblocked` tasks whose blockers are terminal, even though they are stored as `planned`.
- [ ] `aet-work status` shows no mismatch warnings for ordinary `unblocked` or `blocked` tasks.
- [ ] `aet-work next` picks a derived-`unblocked` task and sets it to `in-progress`.
- [ ] The orchestrator starts derived-`unblocked` tasks in isolation.
- [ ] `make lint` passes.
- [ ] `make format-check` passes.
- [ ] `make validate` passes.
- [ ] `make package` regenerates `.skill` files.

## Rollback Plan

1. Revert `aet-work/bin/status`, `aet-work/bin/next`, and `aet-work/bin/orchestrator` to their previous stored-status logic.
2. Revert the read-side sections of `aet-work/SKILL.md`.
3. Run `make validate && make package`.

---

_Stage: reviewed_
_Next step: run `aet-sync-docs`_
