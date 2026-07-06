---
id: are-01-reference-readme
size: S
blocked_by: []
pipeline: standard
---

# Plan: Add `docs/references/README.md` default template

## Context

Part of [aet-setup reference evolution PRD](../prds/aet-setup-reference-evolution-prd.md). This plan creates the load-on-demand index document that every bootstrapped project will copy into `docs/references/README.md`.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [ ] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. Create `aet-setup/examples/reference-README.md.example` — S
2. Run `make validate` and fix any markdownlint/prettier issues — S

## Files to Modify

- `aet-setup/examples/reference-README.md.example` (create)

## Validation Steps

- [ ] `make lint` passes
- [ ] `make format-check` passes
- [ ] File renders correctly and contains a load-on-demand table mapping docs to task types

## Rollback Plan

1. Delete `aet-setup/examples/reference-README.md.example`.
2. Re-run `make validate` to confirm clean state.

---

_Stage: plan-approved_
_Next step: run `aet-work`_
