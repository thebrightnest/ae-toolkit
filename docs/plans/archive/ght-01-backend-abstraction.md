---
id: ght-01-backend-abstraction
size: M
blocked_by: []
pipeline: standard
---

# Plan: Backend Abstraction for AET Work Queue

## Context

Part of [GitHub Issues Task Backend PRD](../prds/aet-github-issues-task-backend-prd.md). This task introduces a pluggable backend interface and moves the existing JSON queue behavior behind it. No GitHub-specific code is added yet.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [ ] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. Create `aet-work/lib/backends/base.py` with `TaskBackend` abstract class covering `load`, `save`, `transition`, `plan_drift`, and `close` — S
2. Create `aet-work/lib/backends/json_backend.py` implementing the interface using existing `queue.py` helpers — S
3. Create `aet-work/lib/backends/factory.py` to instantiate a backend from `.agents/aet-work.json` (`task_backend: json|github|both`) — S
4. Refactor `aet-work/bin/status` and `aet-work/bin/next` to load tasks via the backend instead of direct `queue.read_queue` — M
5. Add unit tests for the JSON backend and factory — S
6. Run `make validate` — S

## Files to Modify

- `aet-work/lib/backends/base.py` (create)
- `aet-work/lib/backends/json_backend.py` (create)
- `aet-work/lib/backends/factory.py` (create)
- `aet-work/lib/backends/__init__.py` (create)
- `aet-work/bin/status`
- `aet-work/bin/next`

## Validation Steps

- [x] `aet-work status` still shows the current queue correctly with no backend config
- [x] `aet-work next` still picks the first ready task with no backend config
- [x] `make lint` passes
- [x] `make format-check` passes
- [x] `make validate` passes
- [x] New backend tests pass
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main` (post-merge check)

## Rollback Plan

1. Remove `aet-work/lib/backends/` directory.
2. Revert changes to `aet-work/bin/status` and `aet-work/bin/next`.
3. Re-run `make validate`.

---

_Stage: reviewed_
