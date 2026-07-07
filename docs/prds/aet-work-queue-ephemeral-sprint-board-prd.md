# PRD: Ephemeral Sprint Board for aet-work

## Overview

Change `aet-work` so that `.agents/work-queue.json` is a gitignored, ephemeral sprint board rather than a tracked source-of-truth file. Plan files (`docs/plans/*.md`) become the durable source of truth for intent, current stage, and terminal closure. The execution log remains an optional, gitignored file for project-management reporting. This eliminates the dirty-working-tree and auto-sync problems that currently block `aet-work run`, while preserving the orchestration and reporting value of the queue and log.

## Goals

1. Gitignore `.agents/work-queue.json` so runtime sprint state no longer pollutes the working tree.
2. Make `docs/plans/*.md` the source of truth for whether a task is open or closed.
3. Replace implicit auto-sync with explicit `aet-work add` so the user curates the sprint.
4. Add `aet-work review` to scan plans and show approved / queued / in-progress / closed without mutating the queue.
5. Keep `.agents/work-history.jsonl` as an optional, gitignored execution log for transition history and timing.
6. Make `aet-ship` the single owner of task closure after merge verification.
7. Update `aet-work/SKILL.md` and `aet-ship/SKILL.md` to reflect the new model.
8. Preserve the forward-only state model within the sprint board.

## Non-Goals

- This PRD does not remove plan files or change their role as intent documents.
- It does not add a new external backend (GitHub Issues, database, etc.).
- It does not change the orchestrator's stage grouping or isolation model.
- It does not alter the skill packaging format.
- It does not retroactively migrate old `.agents/work-history.jsonl` entries; existing history files remain readable but optional.

## Conflict with ADR-011 and Resolution

[ADR-011](../adr/011-forward-only-deterministic-work-state.md) made `.agents/work-queue.json` and `.agents/work-history.jsonl` durable, tracked artifacts. This PRD revises that: the queue becomes ephemeral and gitignored, terminal truth moves into plan files, and the history file becomes optional and gitignored.

The forward-only state principle itself is preserved: while a task is in the queue, transitions are still recorded deterministically by code and trusted on read. Only the lifetime and authority of the files change. A new ADR (013) records this revision.

## User Stories

- As a developer running `aet-work run`, I want the orchestrator to keep running after it writes queue state, instead of halting on a dirty-tree check.
- As a maintainer, I want to keep approved plans in `docs/plans/` without them automatically appearing in my active sprint.
- As a project lead, I want to choose which plans to work on by explicitly adding them to the queue.
- As a shipper, I want `aet-ship` to mark a task closed after it verifies the merge, so I don't run a separate queue command.
- As a consultant, I want the execution log to be gitignored so clients don't see internal timing and transition data.
- As a reviewer, I want `aet-work status` to show only the current sprint, not a mix of settled and active work.

## Acceptance Criteria

- [ ] `.agents/work-queue.json` is added to `.gitignore` and removed from the repository index.
- [ ] `.agents/work-history.jsonl` is added to `.gitignore` and remains optional.
- [ ] `aet-work add <plan-file>` adds a single approved plan to the queue as `planned`.
- [ ] `aet-work add --interactive` (or similar) lists approved plans not yet queued and lets the user select which to add.
- [ ] `aet-work review` scans `docs/plans/*.md`, reads each plan's status, and prints: draft / approved / queued / in-progress / awaiting-merge / closed.
- [ ] `aet-work status` reads only `.agents/work-queue.json` and reports active tasks; it no longer reports settled history.
- [ ] `aet-work next` and `aet-work run` no longer perform a plan-drift gate based on all `docs/plans/*.md`.
- [ ] The orchestrator's main-hygiene check ignores `.agents/work-queue.json` and `.agents/work-history.jsonl`.
- [ ] `aet-ship`, after verifying a merge commit is on `origin/main`, updates the plan file to terminal status, appends to the execution log, and removes the task from the queue.
- [ ] Plan files gain a `status` frontmatter field with values: `draft`, `approved`, `queued`, `in_progress`, `awaiting_merge`, `merged`, `abandoned`.
- [ ] Plan footer `*Stage:*` remains the human-readable stage breadcrumb and is updated by the orchestrator during the sprint.
- [ ] `aet-work sync` is removed or repurposed: it no longer auto-adds all plans to the queue. A replacement command (e.g., `aet-work add-all-approved`) may be provided for bulk curation.
- [ ] `aet-work/SKILL.md` is rewritten to describe the sprint-board model, explicit add, review, and the plan-as-source-of-truth rule.
- [ ] `aet-ship/SKILL.md` is updated to describe closure as its responsibility after merge verification.
- [ ] `aet-plan/SKILL.md` is updated so `create-stories` no longer auto-runs `aet-work sync`; instead it documents how to add plans to the sprint.
- [ ] `aet-setup/SKILL.md` is updated if it references queue-file tracking or drift checks.
- [ ] A new ADR records the architectural revision.
- [ ] `make validate` passes after all changes.

## Technical Notes

### File roles

| File                         | Role                                                    | Tracked         |
| ---------------------------- | ------------------------------------------------------- | --------------- |
| `docs/plans/{id}.md`         | Source of truth for intent, stage, and terminal closure | Yes             |
| `.agents/work-queue.json`    | Ephemeral sprint board: active tasks only               | No (gitignored) |
| `.agents/work-history.jsonl` | Optional execution log for transitions and timing       | No (gitignored) |

### Plan frontmatter contract

```yaml
---
id: are-01-reference-readme
size: S
status: approved
blocked_by: []
pipeline: standard
---
```

- `status` is added to the existing contract. Valid values: `draft`, `approved`, `queued`, `in_progress`, `awaiting_merge`, `merged`, `abandoned`.
- `stage` remains a runtime sub-state and is not added to frontmatter.

### Queue lifecycle

1. Plan is authored with `status: approved`.
2. User runs `aet-work add docs/plans/are-01-reference-readme.md` → task appears in queue as `planned`.
3. `aet-work next` or `aet-work run` transitions it through `in_progress` and its stage sub-states.
4. Task reaches `awaiting_merge`.
5. PR is opened and merged.
6. `aet-ship` verifies the merge commit is on `origin/main`.
7. `aet-ship` sets plan `status: merged`, appends closure to `.agents/work-history.jsonl`, and removes the task from `.agents/work-queue.json`.

### Execution log

The log is append-only and written by `aet-ship` and the orchestrator during the sprint. A representative entry:

```json
{
  "id": "are-01-reference-readme",
  "event": "closed",
  "at": "2026-07-07T10:13:55Z",
  "by": "aet-ship",
  "merge_commit": "3f31e88423c3bddd520aada6a02bf8f7fec70bfa",
  "merge_strategy": "squash"
}
```

If the file is missing, the toolkit creates it on first write. If a project chooses not to keep it, it can be deleted or ignored; plan files still hold terminal truth.

### aet-ship closure flow

`aet-ship` already verifies merges. After verification succeeds, it performs the close sequence:

1. Update plan frontmatter `status` to `merged`.
2. Update plan footer `*Stage:*` to `merged` and `*Next step:*` to `None`.
3. Append closure event to `.agents/work-history.jsonl`.
4. Remove task from `.agents/work-queue.json` (or invoke `aet-work close <task-id>` if such a command exists).

### Removed behavior

- `init-queue` no longer scans all plans and auto-builds the queue on first use. It may be kept as a rebuild utility for when the queue file is lost.
- `aet-work sync` no longer auto-adds new plans. If retained, it only reconciles state for plans already in the queue.
- Plan-drift as a hard gate is removed. `aet-work review` replaces it as a human-readable report.

## Open Questions

1. **Should `aet-work add` accept a plan file path, a task ID, or both?** — Accept both; path is more explicit, ID is more convenient.
2. **Should `aet-work review` also offer to add approved plans interactively?** — Yes, as an optional `--add` flag so a single command can review and populate the sprint.
3. **Should the execution log be JSONL or a single JSON array?** — Keep JSONL; it matches the existing format and is append-only friendly.
4. **How do we handle a plan whose status is `merged` but whose branch was never run through the queue?** — `aet-work review` reports it as closed; no queue action needed.

---

_Intake triage: This is a feature or enhancement, not a reproducible defect._

_Stage: scope-validated_
_Next step: run `aet-work` (single-plan or multi-task queue)_
