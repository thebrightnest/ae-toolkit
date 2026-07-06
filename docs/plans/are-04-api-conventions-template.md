---
id: are-04-api-conventions-template
size: S
blocked_by: []
pipeline: standard
---

# Plan: Add `api-conventions.md` default template

## Context

Part of [aet-setup reference evolution PRD](../prds/aet-setup-reference-evolution-prd.md). Provides a starter for backend+frontend or API-only projects.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [ ] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. Create `aet-setup/examples/api-conventions.md.example` with sections for — S:
   - Auth/session conventions
   - Response envelope (success and error shapes)
   - URL/resource naming
   - Request validation rules
   - Type-sync sequence (backend schema → frontend types)
2. Run `make validate` — S

## Files to Modify

- `aet-setup/examples/api-conventions.md.example` (create)

## Validation Steps

- [ ] `make lint` passes
- [ ] `make format-check` passes
- [ ] Document is referenced from `aet-setup/examples/AGENTS.md.example`

## Rollback Plan

1. Delete `aet-setup/examples/api-conventions.md.example`.
2. Re-run `make validate`.

---

_Stage: implemented_
_Next step: run `aet-qa`_
