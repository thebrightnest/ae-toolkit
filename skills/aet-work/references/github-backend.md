# GitHub Issues Projection

Reference for the optional GitHub Issues projection used by the work queue.

## When to Enable It

Use the GitHub projection when the team wants tasks visible as GitHub Issues
for non-agent collaborators. The local queue remains the source of truth; the
projection is a one-way mirror.

## Configuration

Add a `projections` entry to `.agents/aet-config.json` (team mode) or
`~/.aet/{config-slug}/config.json` (shadow mode). The `task_backend` key selects
storage (`git-refs` or `json`), not GitHub:

```json
{
  "task_backend": "git-refs",
  "integration_mode": "pr-per-task",
  "projections": [
    {
      "type": "github",
      "repo": "owner/repo",
      "label_prefix": "aet",
      "labels_created": true
    }
  ]
}
```

Use `aet configure --guided` to create the base config, then edit the file to
add the projection.

## Required Tooling

- [GitHub CLI (`gh`)](https://cli.github.com/) installed and authenticated via `gh auth login`.
- `gh` must have permission to create labels and issues in the configured repository.
- No personal access tokens are stored in the repo.

## Label Contract

Each AET state maps to exactly one GitHub label. `aet-setup` creates these
labels when the projection is configured; the projection recreates any missing
label on first use.

| AET state        | GitHub label         | Color       |
| ---------------- | -------------------- | ----------- |
| `planned`        | `aet:planned`        | gray        |
| `ready`          | `aet:ready`          | green       |
| `blocked`        | `aet:blocked`        | red         |
| `in_progress`    | `aet:in-progress`    | yellow      |
| `awaiting_merge` | `aet:awaiting-merge` | purple      |
| `merged`         | `aet:merged`         | blue        |
| `abandoned`      | `aet:abandoned`      | black       |
| `failed`         | `aet:failed`         | orange      |
| `quarantined`    | `aet:quarantined`    | pink        |
| `draft` (plan)   | `aet:draft`          | light green |
| `approved`/`backlog` (plan) | `aet:backlog` | blue |

When a task transitions, the projection removes the old AET label and adds the
new one. Terminal tasks (`merged`, `abandoned`) close the corresponding issue.

## Issue Format

Each task maps to one open GitHub issue:

- **Title:** the task title from the plan file.
- **Body:** a short header with the plan file path and an HTML comment marker
  (`<!-- plan-file: ... -->`) so `aet queue sync` can correlate issues with
  plans.
- **Labels:** exactly one `aet:*` label reflecting the current state.
- **Acceptance criteria:** remain in the PRD; the issue links back to the PRD
  rather than duplicating acceptance criteria.

## GitHub-to-Local Sync

`aet queue sync` reconciles open issues with local plan files:

- A plan file without a matching open issue gets a new issue.
- An open issue whose plan file is missing is reported as plan drift.
- A manually closed issue is treated as `abandoned`: the task transitions to
  `abandoned`, is sealed to `.agents/work-history.jsonl`, and the closure reason
  is captured from the last GitHub comment if one exists.

## Switching Projections

Projection changes are forward-only:

- One or more projections can be active at the same time.
- Removing a projection does not close or migrate existing issues.
- `aet-setup` warns if active tasks remain under a removed projection and
  records the warning in `.agents/aet-config.json`.
