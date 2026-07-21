# GitHub Issues Task Backend

Reference for the optional GitHub Issues adapter used by aet-work.

## When to Enable It

Use the GitHub backend when the team wants tasks visible as GitHub Issues for non-agent collaborators. Keep the JSON backend for local-only or offline projects.

## Configuration

`aet-setup` writes `.agents/aet-work.json`:

```json
{
  "task_backend": "github",
  "github": {
    "repo": "owner/repo",
    "label_prefix": "aet",
    "labels_created": true
  }
}
```

Valid values for `task_backend` are `json` (default) and `github`.

## Required Tooling

- [GitHub CLI (`gh`)](https://cli.github.com/) installed and authenticated via `gh auth login`.
- `gh` must have permission to create labels and issues in the configured repository.
- No personal access tokens are stored in the repo.

## Label Contract

Each AET state maps to exactly one GitHub label. `aet-setup` creates these labels when GitHub mode is selected; the backend recreates any missing label on first use.

| AET state        | GitHub label         | Color  |
| ---------------- | -------------------- | ------ |
| `planned`        | `aet:planned`        | gray   |
| `ready`          | `aet:ready`          | green  |
| `blocked`        | `aet:blocked`        | red    |
| `in_progress`    | `aet:in-progress`    | yellow |
| `awaiting_merge` | `aet:awaiting-merge` | purple |
| `merged`         | `aet:merged`         | blue   |
| `abandoned`      | `aet:abandoned`      | black  |
| `failed`         | `aet:failed`         | orange |
| `quarantined`    | `aet:quarantined`    | pink   |
| `draft` (plan)   | `aet:draft`          | light green |
| `approved`/`backlog` (plan) | `aet:backlog` | blue |

When a task transitions, the projection removes the old AET label and adds the new one. Terminal tasks (`merged`, `abandoned`) close the corresponding issue.

## Issue Format

Each task maps to one open GitHub issue:

- **Title:** the task title from the plan file.
- **Body:** a short header with the plan file path and an HTML comment marker (`<!-- plan-file: ... -->`) so `aet sync` can correlate issues with plans.
- **Labels:** exactly one `aet:*` label reflecting the current state.
- **Acceptance criteria:** remain in the PRD; the issue links back to the PRD rather than duplicating acceptance criteria.

## GitHub-to-Local Sync

`aet sync` reconciles open issues with local plan files:

- A plan file without a matching open issue gets a new issue.
- An open issue whose plan file is missing is reported as plan drift.
- A manually closed issue is treated as `abandoned`: the task transitions to `abandoned`, is sealed to `.agents/work-history.jsonl`, and the closure reason is captured from the last GitHub comment if one exists.

## Switching Backends

Backend switches are forward-only:

- Only one backend is active at a time.
- Changing `task_backend` does not migrate active tasks or settled history.
- Existing issues or JSON records created under the previous backend are left untouched.
- `aet-setup` warns if active tasks remain in the previous backend and records the warning in `.agents/aet-work.json`.
