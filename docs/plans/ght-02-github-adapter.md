---
id: ght-02-github-adapter
size: M
blocked_by:
  - ght-01-backend-abstraction
pipeline: standard
---

# Plan: GitHub Issues Backend Adapter

## Context

Part of [GitHub Issues Task Backend PRD](../prds/aet-github-issues-task-backend-prd.md). Builds on the backend abstraction to implement a GitHub Issues adapter that maps open issues to AET tasks and labels to AET states.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [ ] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. Create `aet-work/lib/backends/github_backend.py` implementing `TaskBackend` — M
2. Implement `gh issue list` parsing to load open issues with `aet:*` labels into queue records — S
3. Map AET states to/from GitHub labels (`aet:ready`, `aet:in-progress`, etc.) — S
4. Implement label creation helper that ensures required `aet:*` labels exist in the repo — S
5. Implement issue creation/update/close helpers for `save()` and `transition()` — M
6. Add error handling for missing `gh` CLI or failed authentication — S
7. Add unit tests using mocked `gh` subprocess calls — S
8. Run `make validate` — S

## Files to Modify

- `aet-work/lib/backends/github_backend.py` (create)
- `aet-work/lib/backends/factory.py` (update to instantiate github backend)
- Tests for GitHub backend

## Validation Steps

- [ ] GitHub backend loads open issues and maps labels to states correctly in tests
- [ ] Missing labels are created automatically on first load
- [ ] `gh` CLI errors produce clear, actionable messages
- [ ] `make lint` passes
- [ ] `make format-check` passes
- [ ] `make validate` passes
- [ ] New backend tests pass
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

1. Remove `aet-work/lib/backends/github_backend.py`.
2. Revert factory changes.
3. Re-run `make validate`.

---

_Stage: secure_
_Next step: run `aet-sync-docs`, then `aet-ship`_
