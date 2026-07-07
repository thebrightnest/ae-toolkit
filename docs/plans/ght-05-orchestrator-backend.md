---
id: ght-05-orchestrator-backend
size: M
blocked_by:
  - ght-01-backend-abstraction
  - ght-04-aet-state-backend
pipeline: standard
---

# Plan: Orchestrator Reads Queue via Backend Abstraction

## Context

Part of [GitHub Issues Task Backend PRD](../prds/aet-github-issues-task-backend-prd.md). The orchestrator currently reads `.agents/work-queue.json` directly. This task makes it read through the backend abstraction so it works with GitHub Issues when configured.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [ ] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. Refactor `aet-work/bin/orchestrator` to load the active queue via the configured backend — M
2. Ensure worktree/branch metadata writes go through the backend's `save()` path — S
3. Ensure the orchestrator still skips done/in-progress tasks correctly — S
4. Preserve parallel execution, concurrency cap, and telemetry behavior — S
5. Add tests or dry-run verification for orchestrator backend loading — S
6. Run `make validate` — S

## Files to Modify

- `aet-work/bin/orchestrator`
- Orchestrator tests if present

## Validation Steps

- [ ] `aet-work run` works unchanged when no backend config is set
- [ ] With GitHub backend configured, the orchestrator schedules tasks from open issues
- [ ] `make lint` passes
- [ ] `make format-check` passes
- [ ] `make validate` passes
- [ ] Tests pass
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

1. Revert `aet-work/bin/orchestrator` to direct JSON access.
2. Re-run `make validate`.

---

_Stage: implemented_
_Next step: run `aet-qa`_
