# Work Queue Format

## File Location

`.agents/work-queue.json`

## Design Principle

The queue file stores **persistent facts** about each task. Actionable pickability (`blocked` / `unblocked`) is **derived on read** from those facts, not stored in the JSON.

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

## Derived Statuses

Derived status is computed on read by `aet-state derive`:

1. If `branch` or `merge_commit` is an ancestor of `origin/main` → `merged`.
2. Else if `branch` exists locally → `in-progress`.
3. Else if all `blocked_by` tasks are `merged` or `abandoned` → `unblocked`.
4. Else → `blocked`.

If `plan_file` is missing, the task is reported as plan drift rather than assigned a status.

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
