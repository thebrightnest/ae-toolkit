---
id: ght-04-aet-state-backend
size: M
blocked_by:
  - ght-01-backend-abstraction
pipeline: standard
---

# Plan: aet-state Transitions Use Backend Abstraction

## Context

Part of [GitHub Issues Task Backend PRD](../prds/aet-github-issues-task-backend-prd.md). This task routes state transitions through the backend abstraction so GitHub issue labels stay in sync with the JSON queue.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [ ] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. Refactor `aet-work/bin/aet-state` to load/save the active queue via the configured backend — M
2. Ensure `transition` subcommand updates the backend (and therefore GitHub labels when enabled) — S
3. Ensure `record-merge` seals terminal tasks and closes the corresponding GitHub issue — S
4. Preserve transition validation, history append, and dependent promotion logic — S
5. Add tests for backend-aware transitions — S
6. Run `make validate` — S

## Files to Modify

- `aet-work/bin/aet-state`
- Tests for backend-aware transitions

## Validation Steps

- [ ] `aet-state transition` still updates the JSON queue when no backend config is set
- [ ] With GitHub backend configured, `aet-state transition` updates the issue label for the task
- [ ] Terminal transitions (`merged`, `abandoned`) close the corresponding GitHub issue
- [ ] `make lint` passes
- [ ] `make format-check` passes
- [ ] `make validate` passes
- [ ] Tests pass
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

1. Revert `aet-work/bin/aet-state` to direct JSON access.
2. Re-run `make validate`.

---

_Stage: reviewed_
