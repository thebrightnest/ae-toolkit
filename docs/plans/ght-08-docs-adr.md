---
id: ght-08-docs-adr
size: M
blocked_by:
  - ght-01-backend-abstraction
  - ght-02-github-adapter
  - ght-03-sync-init-backend
  - ght-04-aet-state-backend
  - ght-05-orchestrator-backend
  - ght-06-setup-backend-config
pipeline: standard
status: merged
---

# Plan: Documentation and ADR for GitHub Issues Backend

## Context

Part of [GitHub Issues Task Backend PRD](../prds/aet-github-issues-task-backend-prd.md). This task updates skill documentation and records the architectural decision to support an optional GitHub Issues adapter.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [ ] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. Update `aet-work/SKILL.md` to document the backend abstraction, JSON/GitHub modes, label contract, configuration, and forward-only switching rule — M
2. Update `aet-setup/SKILL.md` and `aet-setup/references/README.md` to document `.agents/aet-work.json` and backend setup — S
3. Add `aet-work/references/github-backend.md` with the label contract, `gh` CLI requirements, and issue body format — S
4. Create a new ADR `docs/adr/013-optional-github-issues-adapter.md` explaining the decision and its relationship to ADR-011 — S
5. Update `aet-work/examples/README.md` if needed — S
6. Run `make validate` and ensure no SKILL.md exceeds 400 lines — S

## Files to Modify

- `aet-work/SKILL.md`
- `aet-setup/SKILL.md`
- `aet-setup/references/README.md`
- `aet-work/references/github-backend.md` (create)
- `docs/adr/013-optional-github-issues-adapter.md` (create)
- `aet-work/examples/README.md` (update if needed)

## Validation Steps

- [ ] `aet-work/SKILL.md` accurately describes the new backend behavior and remains ≤ 400 lines
- [ ] `aet-setup/SKILL.md` accurately describes backend configuration
- [ ] New ADR is numbered sequentially and references ADR-011
- [ ] `make lint` passes
- [ ] `make format-check` passes
- [ ] `make validate` passes
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

1. Revert documentation changes.
2. Remove new ADR and reference file.
3. Re-run `make validate`.

---

_Stage: merged_
