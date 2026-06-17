# Audit: `aet-work` queue state flow

**Date:** 2026-06-17
**Scope:** `aet-work/` skill, its `bin/` helpers, and `lib/queue.py`
**Question:** Why do `init-queue`, `sync`, and `derive` feel overlapping, and what would a clean, robust flow look like?

---

## 1. Quick clarification: atomic plan vs. multi-phase plan

A normal, atomic plan file **should** contain many steps in its task list. That is not what `aet-work` calls a “multi-phase” plan.

- **Atomic plan:** one unit of work, one queued task, many implementation steps inside.
- **Multi-phase plan:** one markdown file containing `## Phase 1`, `## Phase 2`, etc., where each phase should really be a separate queued task. `aet-work sync` rejects these because they should have been split into separate `docs/plans/*.md` files.

So the rule stays: **one task = one plan file = one queue entry.** A plan file with many steps is fine; a plan file with many phases is not.

---

## 2. What each helper is supposed to do

| Helper                        | Intended job                                                                       | Current reality                                                                                                                                                                          |
| ----------------------------- | ---------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `init-queue`                  | First-time / full-rebuild queue creation from `docs/plans/*.md`.                   | Defined in `SKILL.md` but the heavy lifting is duplicated by `sync`.                                                                                                                     |
| `sync`                        | Incrementally append new plan files to the existing queue.                         | Re-implements most of `init-queue`: scans every plan, rebuilds DAG, normalizes statuses, promotes dependents, calls `derive`, patches statuses, handles wrapper metadata, flags orphans. |
| `derive` (`aet-state derive`) | Read-only ground-truth probe: plan exists? branch exists? merged to `origin/main`? | Ignores satisfied blockers, so it conflicts with `sync`’s blocker-promotion logic.                                                                                                       |
| `status`                      | Show actionable queue state and drift.                                             | Compares stored vs. derived status and warns on every `unblocked` task because `derive` calls it `planned`.                                                                              |
| `next` / orchestrator         | Pick the next pickable task.                                                       | Reads stored `unblocked` status, which may not match `derive`.                                                                                                                           |

The confusion is real: **`sync` is doing recovery, rebuild, and derivation work that should be owned by separate, simpler helpers.**

---

## 3. Specific overlaps and anti-patterns found

### 3.1 `sync` and `init-queue` do almost the same work

Both:

- scan all `docs/plans/*.md`;
- build `blocked_by` / `blocks`;
- normalize legacy statuses;
- promote blocker-satisfied tasks to `unblocked`;
- call `derive` and patch `in-progress` / `merged` mismatches.

`sync` should be a thin incremental wrapper. Instead, it is a second full-queue builder with extra orphan/size/atomicity checks.

### 3.2 `derive` and `sync` disagree on what “unblocked” means

In `aet-work/bin/sync` (lines 313–319):

```python
terminal = {"merged", "done", "abandoned"}
for task in final_queue:
    if task.get("status") == "blocked":
        blockers = task.get("blocked_by", [])
        if all(task_by_id.get(b, {}).get("status") in terminal for b in blockers):
            task["status"] = "unblocked"
```

In `aet-work/bin/aet-state` (`derive_status`):

```python
if plan_file and Path(plan_file).exists():
    derived["derived_status"] = "planned"
if branch and branch_exists(branch, cwd=cwd):
    derived["derived_status"] = "in-progress"
if on_main:
    derived["derived_status"] = "merged"
```

`derive` never checks blockers. So a task whose blockers are merged gets stored as `unblocked` by `sync`, but `derive` (and therefore `status`) reports it as `planned`. Every such task shows a mismatch warning, which trains the user to ignore warnings.

### 3.3 Three different places derive status

- `sync` calls `derive_statuses` and patches stored status.
- `init-queue` (per `SKILL.md`) calls `aet-state derive` and patches stored status.
- `status` calls `aet-state derive` again to compare against stored status.

There is no single place that owns “what is the actionable state right now.”

### 3.4 `promote_dependents` exists in both `lib/queue.py` and `sync`

`lib/queue.py` has a helper to promote blocked tasks when dependencies finish, but `sync` also inlines the same logic. If unblocked status is derived at read time, this duplication disappears entirely.

### 3.5 Wrapper-metadata handling is scattered

`lib/queue.py` preserves wrapper metadata via a module-level cache, but `sync` also manually adds `queue_updated_at` after writing. This is fragile: two writers with two different ideas of what the queue file should look like.

### 3.6 `sync` mutates stored status for orphan detection

When a plan file disappears, `sync` changes `status` to `orphaned`. That mixes “state derived from filesystem” with “status meant to drive workflow.” Orphan detection should be reported separately, not by overwriting a workflow status.

---

## 4. What a clean flow should look like

### 4.1 Core principle

**Store only persistent facts. Derive actionable state on read.**

Persistent facts:

- `plan_file`, `blocked_by`, `blocks`, `branch`, `worktree`, `merge_commit`.
- Terminal human decisions: `abandoned` + reason, `failed` + reason.

Derived actionable state:

- `merged` — branch or `merge_commit` is ancestor of `origin/main`.
- `in-progress` — local branch exists (or worktree exists).
- `unblocked` — plan exists, no local branch, all blockers are `merged`/`abandoned`.
- `blocked` — plan exists, no local branch, at least one blocker is not terminal.
- `orphaned` — plan file is missing (reported, not stored as a status).

### 4.2 Simplified helpers

- **`init-queue`**
  Full rebuild from `docs/plans/*.md`. Use once when the queue is missing or after a major reorganization. Output: queue with facts only, every task stored as `planned` (or `in-progress`/`merged` if ground truth says so), DAG built, no promotion.

- **`sync`**
  Thin incremental append. Input: existing queue + new plan files. Output: existing entries untouched; new entries appended as `planned`; `blocks` inverse recomputed for the whole graph. No derive, no promotion, no orphan mutation. If a plan file is gone, report it as drift; do not change status.

- **`derive`**
  Pure read-only query used by `status`, `next`, and the orchestrator. Computes the actionable state from stored facts + git/filesystem. This is the only place that decides whether a task is `unblocked`.

- **`status`**
  Reports the derived actionable state. No stored-vs-derived mismatch warnings because stored status is no longer the source of truth for pickability.

- **`next` / orchestrator**
  Derive pickable tasks dynamically, then pick the first in topological order and transition it to `in-progress`.

### 4.3 What changes in the code

1. Remove `promote_dependents` from `lib/queue.py` and from `sync`.
2. Make `sync` stop calling `derive` and stop patching stored statuses.
3. Make `derive` aware of `blocked_by` terminal status so it can return `unblocked` / `blocked`.
4. Make `status` derive state without comparing to a stored “unblocked” label.
5. Keep stored status only for terminal/decided states (`in-progress`, `merged`, `abandoned`, `failed`). `planned`, `blocked`, `unblocked` become derived.
6. Move orphan detection out of status mutation and into a drift report.
7. Consolidate wrapper-metadata handling in `lib/queue.py`.

### 4.4 Why this is better

- **No overlap.** `init-queue` rebuilds; `sync` appends; `derive` reads.
- **No false mismatch warnings.** `unblocked` is computed consistently in one place.
- **Robust to drift.** If a plan file disappears, it is reported as drift, not silently reclassified.
- **Cheaper.** `sync` no longer shells out to `aet-state derive` or walks git for every task.

---

## 5. What is **not** a toolkit problem

- E23 having a PRD but no plans is a project planning gap, not a queue-intake gap. PRDs are pre-planning; the queue correctly reflects `docs/plans/*.md`.
- Reprioritizing E22/E23/E24/E25 vs. picking E26-02 is a project decision.
- The aborted E24-01 cleanup is a one-off execution mistake in that session.

---

## 6. Recommended next step

Write a focused PRD for the `aet-work` queue-state refactor sketched in section 4, then implement it in small vertical slices:

1. Make `derive` blocker-aware.
2. Simplify `sync` to an append-only DAG updater.
3. Remove promotion logic and false mismatch warnings.
4. Update `status` / `next` / orchestrator to use derived state.
