# Plan: Simplify `sync` and Create `init-queue`

## Context

- PRD: `docs/prds/aet-work-queue-state-refactor-prd.md`
- ADR: `docs/adr/010-queue-derived-state.md`
- Current `aet-work/bin/sync` re-implements a full queue rebuild: it scans every plan, builds the DAG, normalizes statuses, promotes dependents, and calls `derive`. This overlaps with `init-queue` and makes incremental updates expensive and confusing.

## Tasks

1. **Create `aet-work/bin/init-queue`** — M

   - Scan all `docs/plans/*.md`.
   - Build `blocked_by` from each plan’s `## Blocked by` section.
   - Build `blocks` inverse mappings.
   - Preserve existing metadata (`branch`, `worktree`, `merge_commit`, terminal statuses) if the queue file already exists.
   - Set new or non-terminal tasks to `planned`.
   - Set `source_prd` wrapper metadata to the most recent `docs/prds/*.md` if one exists.
   - Set `queue_updated_at`.
   - Do **not** call `derive` or promote tasks to `unblocked`.

2. **Simplify `aet-work/bin/sync`** — M

   - Load existing queue and archive.
   - Append only newly created plan files that are not already in the queue or archive.
   - Validate atomicity (no cross-plan references, no multiple Phase sections) and size.
   - Recompute `blocks` for the entire queue.
   - Normalize only `merge_verified` → `merged`.
   - Report missing plan files as drift; do not mutate stored status to `orphaned`.
   - Update `queue_updated_at`.
   - Remove the call to `derive_statuses` and the stored-status patch logic.

3. **Consolidate wrapper-metadata handling in `aet-work/lib/queue.py`** — S

   - Ensure `read_queue` / `write_queue` reliably preserve `source_prd` and `queue_updated_at`.
   - Remove inline wrapper handling from `sync`.

4. **Update `aet-work/SKILL.md` `init-queue` and `sync` sections** — S
   - Describe `init-queue` as a real rebuild command.
   - Describe `sync` as append-only.
   - Remove promotion and derive-patch language.

## Dependencies

- None.
- This plan blocks `aet-work-state-refactor-status-next-plan.md`.

## Validation Steps

- [ ] `python3 aet-work/bin/init-queue` rebuilds `.agents/work-queue.json` with all tasks set to `planned` (or preserved terminal statuses).
- [ ] Running `sync` after adding a new plan file appends exactly one new task and does not modify existing tasks.
- [ ] `sync` no longer calls `aet-state derive`.
- [ ] `make lint` passes.
- [ ] `make format-check` passes.
- [ ] `make validate` passes.
- [ ] `make package` regenerates `.skill` files.

## Rollback Plan

1. Delete `aet-work/bin/init-queue`.
2. Revert `aet-work/bin/sync` to the previous full-rebuild logic.
3. Restore any wrapper handling needed by the previous sync.
4. Revert `aet-work/SKILL.md` `init-queue` / `sync` sections.
5. Run `make validate && make package`.

---

_Stage: reviewed_
_Next step: run `aet-sync-docs`_
