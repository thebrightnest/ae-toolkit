# Work Queue Format

## File Location

`.agents/work-queue.json`

## Design Principle

The queue file stores **persistent facts** about each task, including the task's canonical `state`. Reads (`aet-work status`, `aet-work next`, the orchestrator) project the stored `state` directly; they do not derive pickability from git on every read. A separate `aet-state audit` command reconciles stored state against git ground truth on demand.

## Schema

```json
{
  "source_prd": "docs/prds/feature-prd.md",
  "queue_updated_at": "2026-06-17T19:00:00Z",
  "tasks": [
    {
      "id": "T1",
      "title": "User can register",
      "plan_file": "docs/plans/T1-register-plan.md",
      "status": "planned",
      "blocked_by": [],
      "blocks": ["T2"],
      "branch": null,
      "worktree": null,
      "merge_commit": null,
      "completed_at": null,
      "merged_at": null
    }
  ]
}
```

## Fields

| Field                  | Type     | Description                                                              |
| ---------------------- | -------- | ------------------------------------------------------------------------ |
| `source_prd`           | string   | Path to the PRD that generated this queue (metadata only)                |
| `queue_updated_at`     | string   | ISO-8601 timestamp of the last queue update                              |
| `tasks`                | array    | List of all tasks in the queue                                           |
| `tasks[].id`           | string   | Unique task identifier (e.g., T1, T2, auth-01)                           |
| `tasks[].title`        | string   | Human-readable task title                                                |
| `tasks[].plan_file`    | string   | Path to the plan.md for this task                                        |
| `tasks[].status`       | enum     | Stored status: `planned`, `in-progress`, `merged`, `abandoned`, `failed` |
| `tasks[].blocked_by`   | string[] | IDs of tasks that must complete before this task                         |
| `tasks[].blocks`       | string[] | IDs of tasks that depend on this task                                    |
| `tasks[].branch`       | string   | Local git branch for this task, if any                                   |
| `tasks[].worktree`     | string   | Path to git worktree for this task, if any                               |
| `tasks[].merge_commit` | string   | Merge commit SHA once the branch is on `origin/main`                     |
| `tasks[].completed_at` | string   | ISO-8601 timestamp when the task reached a terminal state                |
| `tasks[].merged_at`    | string   | ISO-8601 timestamp when the task was marked `merged`                     |

## Stored Statuses

These are the only values written to `tasks[].status`:

- `planned` — The plan file exists. No local branch has been created yet.
- `in-progress` — A branch/worktree has been created and the task is being implemented.
- `merged` — The branch or `merge_commit` is an ancestor of `origin/main`.
- `abandoned` — The task was explicitly cancelled with a documented reason.
- `failed` — Implementation failed and requires human inspection.

Legacy statuses:

- `done` and `merge_verified` are normalized to `merged` during queue sync.
- `blocked` and `unblocked` are **not stored**; they are derived from `blocked_by`, git state, and branch existence.

## Stored States

The canonical `tasks[].state` field is the source of truth for reads. The orchestrator and `aet-work` commands use `current_state()` from `aet-work/lib/queue.py`, which prefers `state` and falls back to the legacy `status` field during the fods-02..fods-05 coexistence window.

Valid states:

- `planned` — Initial state after queue sync. No branch yet.
- `ready` — Task is pickable (all blockers terminal).
- `blocked` — Task has pending blockers.
- `in_progress` — Task has been picked and a worktree/branch exists.
- `awaiting_merge` — Implementation finished; waiting for merge to `origin/main`.
- `merged` — Branch or `merge_commit` is an ancestor of `origin/main`.
- `abandoned` — Task was explicitly cancelled.
- `failed` — Implementation or transition failed; requires human inspection.

## Auditing Stored State

To reconcile stored state against git ground truth, run:

```bash
python3 aet-work/bin/aet-state audit [.agents/work-queue.json]
```

`audit` reports every task whose stored state disagrees with the state derived from `branch`, `merge_commit`, `blocked_by`, and `plan_file` existence. It never mutates the queue.

## Transition Rules

- `planned` → `in-progress` — when `aet-work next` picks the task and creates a branch/worktree.
- `in-progress` → `merged` — when the branch is verified on `origin/main`.
- `in-progress` → `abandoned` — when the task is explicitly cancelled.
- `in-progress` → `failed` — when the pipeline fails.
- `blocked` → `unblocked` — derived automatically when all blockers become terminal.

## Example

```json
{
  "source_prd": "docs/prds/auth-system-prd.md",
  "tasks": [
    {
      "id": "T1",
      "title": "User can register",
      "plan_file": "docs/plans/T1-register-plan.md",
      "status": "merged",
      "blocked_by": [],
      "blocks": ["T2", "T3"],
      "branch": "T1-register",
      "worktree": null,
      "merge_commit": "a1b2c3d"
    },
    {
      "id": "T2",
      "title": "User can log in",
      "plan_file": "docs/plans/T2-login-plan.md",
      "status": "planned",
      "blocked_by": ["T1"],
      "blocks": ["T3"],
      "branch": null,
      "worktree": null,
      "merge_commit": null
    },
    {
      "id": "T3",
      "title": "User can reset password",
      "plan_file": "docs/plans/T3-reset-plan.md",
      "status": "planned",
      "blocked_by": ["T1", "T2"],
      "blocks": [],
      "branch": null,
      "worktree": null,
      "merge_commit": null
    }
  ]
}
```

In this example:

- `T1` is stored as `merged`; derived status is `merged`.
- `T2` is stored as `planned`; because `T1` is terminal, derived status is `unblocked`.
- `T3` is stored as `planned`; because `T2` is not terminal, derived status is `blocked`.
