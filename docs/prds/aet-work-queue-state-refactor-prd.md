# PRD: `aet-work` Queue State Refactor — Store Facts, Derive Action

## Overview

Redesign the `aet-work` skill's queue lifecycle so that `.agents/work-queue.json` stores only persistent facts, while actionable statuses (`blocked`, `unblocked`, `in-progress`, `merged`) are derived on read by a single ground-truth helper. This removes the current overlap between `init-queue`, `sync`, and `derive`, eliminates false mismatch warnings, and makes the queue robust against manual edits and drift.

## Goals

1. **Single source of truth for queue facts.** The queue JSON stores `plan_file`, `blocked_by`, `blocks`, `branch`, `worktree`, `merge_commit`, and terminal human decisions (`abandoned`/`failed` + reason). It does not store `blocked` or `unblocked` as persistent statuses.
2. **`init-queue` is a real, idempotent rebuild command.** It scans `docs/plans/*.md`, builds the dependency DAG, and writes a queue of facts. It is used once at setup or after a major reorganization.
3. **`sync` is append-only.** It adds newly created plan files to the existing queue and recomputes `blocks`. It does not derive status, promote dependents, or mutate existing statuses.
4. **`derive` is blocker-aware.** It returns `unblocked` when a task has no local branch, its plan exists, and all blockers are terminal; `blocked` when blockers are not terminal; `in-progress` when a branch exists; `merged` when the branch or merge commit is on `origin/main`.
5. **`status` / `next` / orchestrator use derived state.** No more stored-vs-derived mismatch warnings for ordinary pickable tasks.
6. **Orphan detection is reported, not stored.** Missing plan files are reported as drift; the queue entry is not overwritten with an `orphaned` status.
7. **No PRD scanning.** `init-queue` and `sync` continue to read only `docs/plans/*.md`. PRDs are pre-planning artifacts and must not appear in the work queue.

## Non-Goals

- Do not change the plan file format or the `*Stage:*` footer convention.
- Do not add GitHub/GitLab issue integration.
- Do not change the archive format or the `cleanup` command's behavior beyond removing stale promotion logic.
- Do not introduce a mandatory `aet-work status` run after every queue edit.
- Do not scan `docs/prds/` for queue intake.

## Root Causes

1. **`sync` re-implements `init-queue`.** It scans every plan, rebuilds the DAG, normalizes statuses, promotes dependents, and calls `derive` — work that belongs to separate helpers.
2. **`derive` ignores `blocked_by`.** It reports `planned` for any task without a branch, even when all blockers are merged. This conflicts with `sync`, which promotes such tasks to `unblocked`.
3. **Actionable state is stored and derived in multiple places.** `init-queue`, `sync`, and `status` all derive status and mutate or compare the stored `status` field.
4. **`promote_dependents` is duplicated** in `lib/queue.py` and `sync`.
5. **Orphan handling mutates workflow status.** A missing plan file changes the stored `status` to `orphaned`, conflating drift detection with workflow state.

## User Stories

- **As a developer running `aet-work sync` after planning,** I want the command to finish instantly because it only appends new plans and updates the dependency graph.
- **As a developer running `aet-work status`,** I want to see the real pickable tasks without warning spam for every `unblocked` item.
- **As an agent maintaining the queue,** I want to edit `blocked_by` or add a new plan file without worrying that the next `sync` will re-derive or reclassify everything.
- **As a project lead,** I want `aet-work next` to pick a task only when its dependencies are actually finished and no branch exists yet.

## Acceptance Criteria

- [ ] `aet-work/bin/init-queue` exists and rebuilds `.agents/work-queue.json` from `docs/plans/*.md` using only persistent facts.
- [ ] `aet-work/bin/sync` appends new plans, recomputes `blocks`, and does not call `derive` or mutate existing non-terminal statuses.
- [ ] `aet-work/bin/aet-state derive` returns `unblocked` for tasks whose blockers are terminal and whose plan exists and have no local branch.
- [ ] `aet-work/bin/aet-state derive` returns `blocked` for tasks whose blockers are not terminal.
- [ ] `aet-work/bin/status` reports derived actionable state without stored-vs-derived mismatch warnings for `unblocked` or `blocked` tasks.
- [ ] `aet-work/bin/status` still reports plan drift for `docs/plans/*.md` files missing from the queue or archive.
- [ ] `aet-work/bin/next` derives pickable tasks and transitions the chosen task to `in-progress`.
- [ ] `aet-work/bin/orchestrator` derives pickable tasks instead of relying on stored `unblocked`.
- [ ] `lib/queue.py` no longer contains `promote_dependents`.
- [ ] `aet-work/SKILL.md` instructions for `init-queue`, `sync`, `status`, `next`, and `run` are updated to match the new flow.
- [ ] `aet-plan/references/work-queue-format.md` is updated to reflect that `blocked`/`unblocked` are derived and only `planned`, `in-progress`, `merged`, `abandoned`, `failed` are stored statuses.
- [ ] `docs/adr/010-queue-derived-state.md` is created and records the structural decision.
- [ ] `CONTEXT.md` is created with the queue-state glossary.
- [ ] `make validate` passes and `make package` produces updated `.skill` files.

## Technical Notes

### Stored fact schema

Each queue entry stores:

```json
{
  "id": "e26-02-foo",
  "title": "...",
  "plan_file": "docs/plans/e26-02-foo.md",
  "blocked_by": ["e26-01-bar"],
  "blocks": [],
  "branch": null,
  "worktree": null,
  "merge_commit": null,
  "status": "planned",
  "completed_at": null,
  "merged_at": null
}
```

Allowed stored statuses:

- `planned` — initial state; no branch yet.
- `in-progress` — a branch/worktree has been created (set by `next` / orchestrator).
- `merged` — verified on `origin/main`.
- `abandoned` — explicitly cancelled with a reason.
- `failed` — pipeline failed, needs inspection.

`blocked` and `unblocked` are **derived only**.

### Derivation rules

For a task with a valid `plan_file`:

1. If `branch` or `merge_commit` is an ancestor of `origin/main` → `merged`.
2. Else if `branch` exists locally → `in-progress`.
3. Else if all `blocked_by` tasks are `merged` or `abandoned` → `unblocked`.
4. Else → `blocked`.

If `plan_file` is missing, report drift; do not return a status.

### `init-queue` behavior

1. Read all `docs/plans/*.md`.
2. Extract `id`, `title`, `blocked_by`.
3. Build `blocks` inverse mappings.
4. Preserve existing metadata (`branch`, `worktree`, `merge_commit`, terminal statuses) if the queue file already exists.
5. Set any new or non-terminal task to `planned`.
6. Set `source_prd` wrapper metadata to the most recent `docs/prds/*.md` if one exists.
7. Write `.agents/work-queue.json`.

`init-queue` does **not** call `derive`.

### `sync` behavior

1. Load existing queue.
2. Load archive for deduplication.
3. List `docs/plans/*.md`.
4. For each plan not already in the queue or archive:
   - Validate atomicity (no references to other plans, no multiple Phase sections).
   - Validate size (optional; may warn).
   - Append a new task with `status: planned`.
5. Recompute `blocks` for the entire queue.
6. Report any plan files missing from the queue as drift.
7. Write `.agents/work-queue.json`.

`sync` does **not** call `derive`, normalize statuses beyond `merge_verified` → `merged`, or promote dependents.

### `derive` behavior

1. Load queue.
2. For each task, compute derived status using the rules above.
3. Return JSON mapping task IDs to derived facts + status.
4. Do not modify the queue file.

### `status` behavior

1. Run plan-drift check (queue vs. archive vs. `docs/plans/*.md`).
2. Derive statuses.
3. Print counts: `unblocked`, `blocked`, `in-progress`, `failed`, `merged`, `abandoned`.
4. List next unblocked tasks (topological order).
5. List failed tasks.
6. Validate worktree directories.

No mismatch-warning column for ordinary `planned`/`blocked`/`unblocked` tasks.

### `next` behavior

1. Run plan-drift check; refuse if drift exists.
2. Derive statuses.
3. Pick the first `unblocked` task in topological order.
4. Transition it to `in-progress` and set `branch` / `worktree`.

### Orchestrator behavior

Derive pickable tasks before selecting the next task to run. Do not rely on stored `unblocked`.

## Decisions

1. `init-queue` will be a new script, `aet-work/bin/init-queue`. A separate command makes the “full rebuild” boundary explicit and keeps `sync` strictly incremental.
2. `derive` will continue to warn about `done` without merge verification during the transition, but `done` is deprecated and normalized to `merged` by `init-queue` and `sync`.
3. `sync` will keep atomicity/size validation. Moving it to a separate helper is future work and out of scope.

## Open Questions

None.

## Divergence Summary

_Recorded: 2026-06-17 — Branch: aet-work-state-refactor-derive_

### Changed from plan

- `aet-work/bin/aet-state derive_status`: implemented blocker inspection via a recursive `blocker_status_fn` callback rather than passing the full queue or a static blocker map. The derivation behavior matches the plan; only the internal interface differed.

### Added (unplanned)

- `aet-work/lib/cli_adapter.py`: changed the Kimi adapter's `headless_flag` from `None` to `--yolo`. This was not listed in the derive plan.
- `aet-work/bin/sync`: removed the blocker-promotion loop and moved ground-truth derivation after the queue write so `sync` no longer stores `unblocked` statuses. This aligns with the broader PRD but was outside the derive plan's explicit tasks.

### Deferred

- None.

---

_Stage: synced_
_Next step: run `aet-ship`_
