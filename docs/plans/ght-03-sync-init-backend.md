---
id: ght-03-sync-init-backend
size: M
blocked_by:
  - ght-01-backend-abstraction
pipeline: standard
---

# Plan: init-queue and sync Use Backend Abstraction

## Context

Part of [GitHub Issues Task Backend PRD](../prds/aet-github-issues-task-backend-prd.md). This task moves queue writes from direct JSON file access to the backend abstraction so `init-queue` and `sync` can create and update GitHub issues when configured.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [ ] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. Refactor `aet-work/bin/init-queue` to load/save via the configured backend — M
2. Refactor `aet-work/bin/sync` to load/save via the configured backend — M
3. Preserve existing archive-aware deduplication and legacy-status normalization — S
4. When GitHub backend is active, create issues for new tasks and update labels for existing tasks during sync — S
5. Add tests covering backend-aware sync behavior — S
6. Run `make validate` — S

## Files to Modify

- `aet-work/bin/init-queue`
- `aet-work/bin/sync`
- Tests for sync/init-queue with backend

## Validation Steps

- [ ] `aet-work init-queue` still rebuilds the JSON queue correctly when no backend config is set
- [ ] `aet-work sync` still appends only new plans when no backend config is set
- [ ] With GitHub backend configured, sync creates issues for new plans and updates existing issue labels
- [ ] `make lint` passes
- [ ] `make format-check` passes
- [ ] `make validate` passes
- [ ] Tests pass
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

1. Revert `aet-work/bin/init-queue` and `aet-work/bin/sync` to direct JSON access.
2. Re-run `make validate`.

---

_Stage: secure_
_Next step: run `aet-sync-docs` (if plan diverged), then `aet-ship`_
