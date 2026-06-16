# Archive-Aware Work Queue Sync

## Status

Accepted

## Context

`aet-work sync` scans every `docs/plans/*.md` file and adds new ones to the active queue. The archive at `.agents/work-archive.json` already holds terminal tasks from previous cycles. When the queue is empty or reset, a sync resurrects every historical plan — including those already archived — as new active tasks. This creates duplicate work items and forces manual cleanup.

The duplication surfaced after a sync added 82 plans to the queue; 19 of them were already present in the archive (some under the same task ID, others under an older short ID with the same `plan_file`).

## Decision

Make `aet-work sync` (and `init-queue`) archive-aware:

1. Before adding a new task, check both the active queue and the archive.
2. Skip any plan whose `plan_file` or task ID already exists in the archive.
3. Report how many plans were skipped because they were already archived.

The implementation is centralized in a new `aet-work/bin/sync` script. The skill instructions in `aet-work/SKILL.md` now include the archive-deduplication step for both `init-queue` and `sync`.

## Consequences

- Completed work stays archived and does not reappear in the active queue.
- `aet-work sync` is safe to run after queue resets or archive cleanups.
- Re-activating an archived plan requires explicit action (e.g., remove it from the archive or move the plan file back into `docs/plans/` after clearing its archive entry).

## Alternatives Considered

- **Move archived plan files out of `docs/plans/`:** Cleaner in theory, but breaks existing links and complicates historical lookups. Skipping archived plans in-place is less disruptive.
- **Teach `aet-state derive` to ignore archived plans:** Does not solve the problem because the queue still receives the duplicate entry; only the derived status would change.
