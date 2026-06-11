# PRD: aet-work Queue Archival and Incremental Sync

## Overview

Redesign the aet-work skill's queue lifecycle so that terminal tasks (merged, done, abandoned) are physically archived out of the active queue, `sync` operates incrementally on new and open tasks only, and `status` presents a clean view of ongoing work without historical noise. This fixes the performance regression where `sync` and `status` grind to a halt as the project history grows.

## Goals

1. **Physical separation:** Terminal tasks live in `.agents/work-archive.json`; the active queue (`.agents/work-queue.json`) contains only open, done, and failed tasks.
2. **Fast sync:** `aet-work sync` derives statuses only for newly added plans and open tasks. It never recomputes ground truth for archived tasks.
3. **Clean status view:** `aet-work status` displays only active tasks (unblocked, blocked, in-progress, failed, done) by default.
4. **Explicit cleanup:** `aet-work cleanup` removes worktrees _and_ archives terminal tasks atomically.
5. **Zero data loss:** All historical metadata (merge_commit, completed_at, branch, worktree) is preserved in the archive.
6. **Backward compatibility:** Existing projects can migrate in one command; the archive file is created on first cleanup.

## Non-Goals

- **Querying the archive:** This PRD does not add an `aet-work history` command. The archive is a JSON artifact for now; querying it is future work.
- **Auto-archive on merge:** Tasks are not moved to archive automatically when marked merged. Archiving is explicit via `cleanup` to prevent accidental loss of context.
- **Compressing or rotating the archive:** The archive is a plain JSON file. Rotation/compression is out of scope.
- **Changing the plan.md footer format:** We keep the existing `*Stage:*` convention; `aet-state` writes it.

## User Stories

- **As a developer running `aet-work sync` after planning,** I want the command to finish in under 1 second so that I don't lose flow state waiting for 65 historical merge commits to be re-checked.
- **As a tech lead checking project health,** I want `aet-work status` to show me only what's currently in flight so I can instantly spot blockers and failures without scrolling through pages of merged tasks.
- **As a release manager,** I want `aet-work cleanup` to both remove stale worktrees and move finished tasks to an archive so the active queue stays lean.
- **As an auditor,** I want all historical task metadata preserved in a separate file so I can trace what was shipped and when.

## Acceptance Criteria

- [ ] `.agents/work-archive.json` exists after the first `cleanup` run and contains only tasks whose status is `merged`, `done`, or `abandoned`.
- [ ] `.agents/work-queue.json` after cleanup contains only tasks whose status is `unblocked`, `blocked`, `in-progress`, `failed`, or `done`.
- [ ] `aet-work sync` runs `aet-state derive` only on tasks that are not in a terminal status. If no new plans were added, sync completes without spawning any `git merge-base` subprocesses for archived tasks.
- [ ] `aet-work status` shows counts and lists for `unblocked`, `blocked`, `in-progress`, `failed`, and `done` only. A note at the bottom indicates how many tasks are archived.
- [ ] `aet-work cleanup` archives terminal tasks before removing their worktrees. If archiving fails, worktree removal is skipped (atomic behavior).
- [ ] `aet-work init-queue` derives only open tasks; terminal tasks that may exist in an old queue are archived during the first post-change cleanup.
- [ ] Existing queue entries with status `merge_verified` are normalized to `merged` and then treated as terminal for archival.
- [ ] The archive file preserves all original fields: `id`, `title`, `plan_file`, `status`, `merge_commit`, `completed_at`, `merged_at`, `branch`, `worktree`, `blocked_by`, `blocks`.
- [ ] A one-time migration path exists for the current 65 merged tasks in the active queue.

## Technical Notes

### Archive file format

`.agents/work-archive.json` uses the same schema as the queue (dict wrapper with `tasks` array). No new fields are introduced.

```json
{
  "source_prd": "...",
  "archived_at": "2026-06-11T14:30:00Z",
  "tasks": [
    { ... preserved task object ... }
  ]
}
```

### Derive scoping

`aet-state derive` should accept an optional `--filter` or task ID list. When invoked from `sync`, it receives only the IDs of newly added tasks plus any tasks whose status is not terminal. Terminal tasks are skipped entirely.

### Status scoping

`status` reads the active queue and ignores the archive unless the user explicitly requests it (future `--archive` flag). The "next 3 unblocked tasks" listing remains unchanged in logic but operates on a smaller dataset.

### Dependency-aware archival

A terminal task is archived **only if no active task lists it in `blocked_by`**. This keeps `promote_dependents` simple — it reads only the active queue, because any blocker that could unblock an active task is guaranteed to still be in the active queue. `init-queue` and `sync` also remain archive-agnostic for initial status assignment.

### Cleanup atomicity

`cleanup` performs these steps in order:

1. Run `derive` on active queue only.
2. Identify terminal tasks.
3. Filter out terminal tasks that still have active dependents (tasks whose `blocked_by` includes the terminal task).
4. Append eligible terminal tasks to `.agents/work-archive.json` (create if missing).
5. Remove archived tasks from `.agents/work-queue.json`.
6. Save both files.
7. Remove worktrees for archived tasks.

If step 4 or 5 fails, step 7 must not run.

### Sync scoping

`sync` steps 8–9 in the skill instructions change from:

> Run `derive` on all entries → update mismatches everywhere

To:

> Run `derive` only on newly added tasks and tasks whose status is not terminal → update mismatches only among those tasks.

## Open Questions

1. Should `aet-work status` support a `--all` flag that shows active + archived tasks in one view?
2. Should `failed` tasks ever be auto-archived, or do they remain active until explicitly marked `abandoned`?
3. Should the archive support multiple archive files (e.g., per-release) or a single ever-growing file?

---

_Stage: scope-validated_
_Next step: run `aet-work` (single-plan or multi-task queue)_
