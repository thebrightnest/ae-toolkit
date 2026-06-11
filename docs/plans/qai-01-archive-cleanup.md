# Plan: Archive Infrastructure and Cleanup Integration

## Context

Parent PRD: `docs/prds/aet-work-queue-archival-incremental-sync-prd.md`

This plan introduces the physical archive file and wires it into `aet-work cleanup`. Terminal tasks (`merged`, `done`, `abandoned`) are moved from `.agents/work-queue.json` to `.agents/work-archive.json` atomically before their worktrees are removed.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Tasks

1. **Add archive read/write helpers to `aet-work/lib/queue.py`** — S

   - `read_archive(path)` → returns tasks list (creates empty archive if missing)
   - `write_archive(path, tasks)` → writes archive JSON with `archived_at` timestamp
   - `archive_tasks(queue_file, archive_file)` → moves terminal tasks from queue to archive, returns (new_queue, archived_tasks)

2. **Add `archive` subcommand to `aet-work/bin/aet-state`** — M

   - `aet-state archive <queue> <archive>` — identifies terminal tasks, filters out those with active dependents, appends eligible tasks to archive, removes them from queue
   - Uses `read_queue` / `write_queue` / `write_archive` helpers
   - Prints: `Archived N tasks: {id1}, {id2}, ...`
   - Prints: `Skipped M terminal tasks with active dependents`
   - Prints: `Active queue: K tasks remaining`

3. **Update `aet-work/SKILL.md` cleanup procedure** — M

   - Replace step 1: Run `derive` on active queue only (skip terminal tasks)
   - New step 2: Identify terminal tasks via `aet-state derive` or status check
   - New step 3: Archive terminal tasks via `aet-state archive .agents/work-queue.json .agents/work-archive.json`
   - Existing worktree removal becomes step 4 (after successful archive)
   - Add atomicity note: if archiving fails, do not remove worktrees

4. **Normalize legacy `merge_verified` during archive** — S

   - Before archiving, rewrite any `merge_verified` status to `merged`
   - This happens in `aet-state archive` logic

5. **Merge branch to main and verify integration** — S

**Size definitions:**

- **S**: ≤ 2 hr human time / ≤ 3 files / ≤ 100 diff lines
- **M**: ≤ 1 day human time / ≤ 5 files / ≤ 200 diff lines
- **L**: > 1 day OR > 5 files OR > 200 lines — **must be split**

## Dependencies

- None — this is the first task in the pipeline.

## Validation Steps

- [ ] `make validate` passes (lint + format + skill structure)
- [ ] `python3 aet-work/bin/aet-state archive .agents/work-queue.json .agents/work-archive.json` runs without error
- [ ] After archiving, `.agents/work-archive.json` contains only terminal tasks
- [ ] After archiving, `.agents/work-queue.json` contains no terminal tasks
- [ ] Archive preserves all original fields: `id`, `title`, `plan_file`, `status`, `merge_commit`, `completed_at`, `merged_at`, `branch`, `worktree`, `blocked_by`, `blocks`
- [ ] For each new source file introduced by this plan, name the test that will cover it:
  - `aet-work/lib/queue.py` → covered by `scripts/test-aet-state.py` (archive read/write roundtrip)
  - `aet-work/bin/aet-state` → covered by `scripts/test-aet-state.py` (archive subcommand integration)

## Rollback Plan

1. Restore `.agents/work-queue.json` from git if committed.
2. Delete `.agents/work-archive.json` if created.
3. Re-run `aet-work init-queue` to rebuild queue from `docs/plans/*.md`.

---

_Stage: implemented_
_Next step: run `aet-qa`_
