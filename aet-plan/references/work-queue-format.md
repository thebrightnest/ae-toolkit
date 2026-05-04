# Work Queue Format

## File Location

`.agents/work-queue.json`

## Schema

```json
{
  "source_prd": "docs/prds/feature-prd.md",
  "tasks": [
    {
      "id": "T1",
      "title": "User can register",
      "plan_file": "docs/plans/T1-register-plan.md",
      "status": "unblocked",
      "blocks": ["T2"],
      "blocked_by": []
    }
  ]
}
```

## Fields

| Field                | Type     | Description                                                     |
| -------------------- | -------- | --------------------------------------------------------------- |
| `source_prd`         | string   | Path to the PRD that generated this queue (metadata only)       |
| `tasks`              | array    | List of all tasks in the queue                                  |
| `tasks[].id`         | string   | Unique task identifier (e.g., T1, T2, auth-01)                  |
| `tasks[].title`      | string   | Human-readable task title                                       |
| `tasks[].plan_file`  | string   | Path to the plan.md for this task                               |
| `tasks[].status`     | enum     | One of: `unblocked`, `blocked`, `in-progress`, `done`, `failed` |
| `tasks[].blocks`     | string[] | IDs of tasks that depend on this task                           |
| `tasks[].blocked_by` | string[] | IDs of tasks that must complete before this task                |

## Status Rules

- `unblocked` — no incomplete dependencies; ready to implement
- `blocked` — has incomplete dependencies; cannot start
- `in-progress` — currently being implemented
- `done` — implemented, validated, and committed
- `failed` — implementation failed validation; requires human review

## Transition Rules

1. When a task is picked for implementation → `unblocked` → `in-progress`
2. When a task completes successfully → `in-progress` → `done`
3. When a task fails → `in-progress` → `failed`
4. When a task's `blocked_by` entries all become `done` → `blocked` → `unblocked`

## Example

```json
{
  "source_prd": "docs/prds/auth-system-prd.md",
  "tasks": [
    {
      "id": "T1",
      "title": "User can register",
      "plan_file": "docs/plans/T1-register-plan.md",
      "status": "done",
      "blocks": ["T2", "T3"],
      "blocked_by": []
    },
    {
      "id": "T2",
      "title": "User can log in",
      "plan_file": "docs/plans/T2-login-plan.md",
      "status": "unblocked",
      "blocks": ["T3"],
      "blocked_by": ["T1"]
    },
    {
      "id": "T3",
      "title": "User can reset password",
      "plan_file": "docs/plans/T3-reset-plan.md",
      "status": "blocked",
      "blocks": [],
      "blocked_by": ["T1", "T2"]
    }
  ]
}
```
