---
id: ght-06-setup-backend-config
size: M
blocked_by:
  - ght-01-backend-abstraction
  - ght-02-github-adapter
pipeline: standard
---

# Plan: aet-setup Configures Task Backend and Creates Labels

## Context

Part of [GitHub Issues Task Backend PRD](../prds/aet-github-issues-task-backend-prd.md). This task adds a configuration step to `aet-setup` that lets the user choose the task backend and ensures the required GitHub labels exist.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [ ] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. Update `aet-setup/SKILL.md` to describe the `task_backend` configuration step and `.agents/aet-work.json` schema — S
2. Add logic to `aet-setup` execution that prompts for `task_backend` (`json` or `github`) and writes `.agents/aet-work.json` — M
3. When `github` is selected, detect the repo from `git remote` and prompt for confirmation/override — S
4. When `github` is selected, run the label creation helper to ensure `aet:ready` and other `aet:*` labels exist — S
5. Document that switching backends is forward-only and does not migrate history — S
6. Update `aet-setup/checklist.md` with backend-configuration verification items — S
7. Update `aet-setup/examples/AGENTS.md.example` to mention `.agents/aet-work.json` and backend choice — S
8. Run `make validate` — S

## Files to Modify

- `aet-setup/SKILL.md`
- `aet-setup/checklist.md`
- `aet-setup/examples/AGENTS.md.example`
- Add `aet-setup/lib/` or inline config helper if needed

## Validation Steps

- [ ] `aet-setup` produces `.agents/aet-work.json` with the chosen backend
- [ ] `aet-setup` creates `aet:ready` label when GitHub backend is selected and `gh` is authenticated
- [ ] `aet-setup` falls back gracefully when `gh` is unavailable and documents the gap
- [ ] `make lint` passes
- [ ] `make format-check` passes
- [ ] `make validate` passes
- [ ] Merge verified: `git merge-base --is-ancestor origin/main HEAD`

## Rollback Plan

1. Revert changes to `aet-setup/SKILL.md`, `aet-setup/checklist.md`, and `aet-setup/examples/AGENTS.md.example`.
2. Remove any new setup helper files.
3. Re-run `make validate`.

---

_Stage: reviewed_
_Next step: run `aet-sync-docs`_
