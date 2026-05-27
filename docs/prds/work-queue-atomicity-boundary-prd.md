# PRD: Work Queue Plan Atomicity Boundary

## Overview

The `aet-work` skill treats every `.md` file in `docs/plans/` as an executable task, with no guardrail to distinguish atomic implementation plans from roadmaps, audits, or meta-plans. This breaks the 1:1 mapping between queue entries and plan files that `aet-pipeline-implement` expects, causing pipeline mis-routing, context bloat, and worktree confusion. This PRD defines a structural boundary: separate atomic task plans from non-atomic planning artifacts, and teach `aet-work sync` to respect that boundary.

## Goals

- Ensure `aet-work init-queue` and `sync` only add atomic, implementable task plans to the work queue
- Codify a directory convention so users know where to save different types of planning documents
- Preserve the 1:1 mapping between queue entries and `docs/plans/*.md` files
- Update skill documentation to prevent future atomicity violations

## Non-Goals

- Modifying the `.skill` packaging format or build pipeline
- Implementing content heuristics to auto-detect non-atomic plans (overkill for this fix)
- Rewriting existing plan files in consumer repos (migration is documented but not enforced)
- Changing the work queue JSON schema or task state machine
- Adding UI validation (this is a structural/docs change with no interface)

## User Stories

- As an agentic engineer, I want `aet-work sync` to only pick up atomic task plans so that roadmaps and audits don't pollute my execution queue.
- As a skill user, I want clear guidance on where to save roadmaps and audits so that I don't accidentally place them where the queue scanner will ingest them.
- As an AFK loop operator, I want confidence that every task in the queue is implementable in a single agent session.

## Acceptance Criteria

- [ ] `aet-work/SKILL.md` specifies that `init-queue` and `sync` scan `docs/plans/*.md` for atomic plans only, and defines what happens when non-atomic documents are encountered
- [ ] `aet-plan/SKILL.md` instructs agents to save atomic plans to `docs/plans/` and non-atomic documents to `docs/roadmaps/` or `docs/audits/`
- [ ] `aet-pipeline-plan/SKILL.md` references the directory constraint in its `aet-work sync` step
- [ ] `docs/CONVENTIONS.md` documents the directory convention for planning artifacts
- [ ] An ADR (`docs/adr/NNN-work-queue-atomicity-boundary.md`) records the structural boundary decision
- [ ] `make validate` passes after all skill edits

## Technical Notes

- **Recommended approach:** Directory separation (Option A from the bug report).
  - `docs/plans/` → Atomic, implementable task plans ONLY
  - `docs/roadmaps/` → Multi-phase roadmaps, completion trackers
  - `docs/audits/` → Testing audits, strategy reviews, gap analyses
  - `docs/prds/` → Product Requirements Documents (already exists)
- `aet-work sync` currently validates task sizes against the dual-limit model. The same scanning logic can be extended with a lightweight filename/content sanity check: if a plan references other plan files or contains multiple "Phase" sections, emit a warning and skip it.
- The skill files themselves are the "source code" for this repo. Changes are markdown edits; no runtime code is written.
- The `aet-pipeline-implement` skill input spec already expects "Path to `docs/plans/{ticket}-plan.md`" — this PRD tightens the contract rather than changing it.

## Open Questions

- Should `aet-work` create `docs/roadmaps/` and `docs/audits/` directories if they don't exist during `init-queue`? (Decision: no — the skill documents the convention; directory creation is the user's responsibility.)
- Should the filename convention `-plan.md` be enforced, or is directory location sufficient? (Decision: directory location is the primary gate; filename convention is advisory.)

---

_Stage: scope-validated_
_Next step: run `aet-pipeline-implement` (single task) or `aet-work` (multi-task queue)_
