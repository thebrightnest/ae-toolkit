# PRD: GitHub Issues Task Backend for AET Work Queue

## Overview

Make the AET work queue pluggable so projects can optionally use GitHub Issues as the task backend instead of the local `.agents/work-queue.json` file. The JSON file remains the canonical, infra-agnostic default; GitHub Issues is implemented as an optional adapter. When enabled, `aet-work` reads open issues as the active task list, uses the `aet:ready` label to identify pickable work, and writes state transitions back to issue labels. `aet-setup` gains a configuration step that chooses the backend and ensures the required labels exist. Only one backend is active at a time; switching backends is forward-looking and does not migrate settled history.

## Goals

1. Introduce a backend abstraction in `aet-work` so queue reads and writes go through a pluggable interface.
2. Implement a JSON backend that preserves today's behavior exactly.
3. Implement a GitHub Issues backend that maps open issues to active tasks and issue labels to AET states.
4. Allow `aet-setup` to configure the backend (`json` or `github`) and create the `aet:ready` label when GitHub is selected.
5. Keep plan files (`docs/plans/*.md`) as the durable content source; issues mirror task metadata, not replace plans.

## Non-Goals

- This PRD does not replace `.agents/work-queue.json` as the default; GitHub Issues is opt-in.
- It does not implement a generic issue-tracker adapter (GitLab, Jira, etc.); only GitHub Issues is in scope.
- It does not store plan markdown bodies inside issue descriptions; issues reference plan files by path/link.
- It does not remove or bypass the forward-only state model (ADR-011); state transitions remain deterministic and recorded.
- It does not require GitHub for local-only projects; the toolkit stays agent- and infra-agnostic by default.

## Conflict with ADR-011 and Resolution

[ADR-011](../adr/011-forward-only-deterministic-work-state.md) rejected "Move the queue to GitHub issues / an external tracker" to preserve infra-agnosticism and because GitHub has poor native DAG support. This PRD does not move the queue to GitHub. It adds an optional adapter while keeping the JSON file as the canonical default and the single source of truth for scheduling. The DAG continues to live in the JSON queue and plan frontmatter; GitHub issues mirror task state and expose it where teams already track work. A new ADR will record the decision to offer an optional external adapter without changing the default architecture.

## User Stories

- As a project lead, I want tasks to appear as GitHub Issues so non-agent collaborators can see and discuss upcoming work in a familiar UI.
- As a solo developer, I want to keep using `.agents/work-queue.json` so I can work offline and avoid GitHub dependency.
- As a user running `aet-setup`, I want to choose the task backend and have the right labels created automatically.
- As a user running `aet-work next`, I want the command to pick the next open GitHub issue labeled `aet:ready` when GitHub mode is enabled.
- As a maintainer switching backends, I want the change to apply only to future work so existing settled history remains untouched.

## Acceptance Criteria

- [ ] `aet-work/lib/backends/` contains a backend base class, a JSON backend, and a GitHub Issues backend.
- [ ] `aet-work/bin/status`, `next`, `init-queue`, `sync`, `aet-state`, and `orchestrator` route queue I/O through the configured backend.
- [ ] JSON backend behavior is unchanged from today; existing projects see no difference when `task_backend` is unset or `json`.
- [ ] GitHub backend lists only open issues, maps labels like `aet:ready` to AET states, and creates missing `aet:*` labels on first use.
- [ ] `aet-setup` prompts for `task_backend` (`json` or `github`) and writes `.agents/aet-work.json`.
- [ ] `aet-setup` creates the `aet:ready` label in the configured repository when GitHub mode is selected and `gh` is authenticated.
- [ ] Switching backends does not migrate active tasks or settled history; the new backend only manages work created after the switch.
- [ ] Terminal tasks (`merged`, `abandoned`) are closed as GitHub issues and sealed to `.agents/work-history.jsonl`.
- [ ] Manually closing a GitHub issue is detected by `aet-work sync` and transitions the task to `abandoned` in local history.
- [ ] `aet-setup` warns when active tasks remain in the previous backend after a switch.
- [ ] `aet-work/SKILL.md` and `aet-setup/SKILL.md` document the backend option, configuration, label contract, forward-only switching rule, and GitHub-to-local sync behavior.
- [ ] A new ADR records the decision to support an optional GitHub Issues adapter without changing the default JSON queue architecture.
- [ ] `make validate` passes after all changes.

## Technical Notes

### Backend Abstraction

All queue reads and writes go through `aet-work/lib/backends/base.py`:

```python
class TaskBackend(ABC):
    def load(self) -> list[dict]: ...
    def save(self, tasks: list[dict]) -> None: ...
    def transition(self, task_id: str, from_state: str, to_state: str, evidence: dict | None = None) -> None: ...
    def plan_drift(self, plans_dir: Path) -> list[str]: ...
    def close(self) -> None: ...
```

`load()` returns the active task list in the existing queue format. `save()` writes the full active list. `transition()` records a state change and, for GitHub, updates labels. `plan_drift()` returns orphaned plan files. Backends are configured from `.agents/aet-work.json`. Valid values for `task_backend` are `json` and `github`:

```json
{
  "task_backend": "json",
  "github": {
    "repo": "owner/repo",
    "label_prefix": "aet"
  }
}
```

### GitHub Label Contract

| AET state        | GitHub label         |
| ---------------- | -------------------- |
| `planned`        | `aet:planned`        |
| `ready`          | `aet:ready`          |
| `blocked`        | `aet:blocked`        |
| `in_progress`    | `aet:in-progress`    |
| `awaiting_merge` | `aet:awaiting-merge` |
| `merged`         | `aet:merged`         |
| `abandoned`      | `aet:abandoned`      |
| `failed`         | `aet:failed`         |

The `aet:ready` label is created by `aet-setup` and recreated on first use if missing. Issue titles are derived from plan titles. Issue bodies mirror the plan file content (context, task list, files to modify, validation steps) and link back to the PRD for acceptance criteria; acceptance criteria live in the PRD, not in the issue.

### Switching Backends Is Forward-Only

Only one backend is active at a time. The active backend is read from `.agents/aet-work.json` at the start of every `aet-work` command. Changing `task_backend` from `json` to `github` (or vice versa) does not:

- Migrate active tasks from the old backend to the new one.
- Re-import settled history into the new backend.
- Close, reopen, or modify issues or JSON records created under the previous backend.

After a switch, `init-queue` and `sync` ingest only plan files that exist on disk into the newly active backend. Existing `.agents/work-history.jsonl` remains the durable record of completed work regardless of backend. This keeps the switching logic stateless and prevents accidental bulk mutations.

`aet-setup` warns the user if active tasks remain in the previous backend and records the warning in `.agents/aet-work.json` so future sessions understand why older tasks are not visible.

### Authentication

The GitHub backend shells out to the `gh` CLI. If `gh` is not installed or not authenticated, commands fail with a clear error pointing to `gh auth login`. No personal access tokens are stored in the repo.

### Plan Files Remain Canonical Content

The issue body does not replace the plan. Each issue corresponds to exactly one `docs/plans/{id}.md` file and mirrors the plan's content (summary, context, task list, files to modify, validation steps). Acceptance criteria remain in the PRD, which the issue links to. The plan markdown is still what agents read during implementation.

### GitHub-to-Local Sync

When the GitHub backend is active, `aet-work sync` reads the current state of open issues and reconciles it with the local record:

- A plan file without a matching open issue gets a new issue.
- An open issue whose plan file is missing is reported as plan drift.
- An issue closed manually in GitHub is treated as `abandoned`: the task is transitioned to `abandoned`, sealed to `.agents/work-history.jsonl`, and the closure reason is captured from the last GitHub comment if one exists.

This keeps the local history accurate even when humans edit issues directly.

### Single Writer for State

`aet-state transition` remains the only code path that mutates state. The backend adapter makes the transition durable on the configured storage; it does not introduce a second writer or bypass transition validation.

## Open Questions (Resolved)

1. **Issue body content:** The issue mirrors the plan file (summary, context, task list, files, validation); acceptance criteria stay in the PRD and are linked from the issue.
2. **Manual issue closure:** Yes — `aet-work sync` detects a closed GitHub issue and transitions the task to `abandoned`, sealing it to `.agents/work-history.jsonl`.
3. **Switching backend warning:** Yes — `aet-setup` warns when active tasks remain in the previous backend and records the warning in `.agents/aet-work.json`.

---

_Intake triage: This is a feature or enhancement, not a reproducible defect._

_Stage: scope-validated_
_Next step: run `aet-work` (single-plan or multi-task queue)_
