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

1. [x] Create `aet-setup/examples/reference-README.md.example` — S
2. [x] Run `make validate` and fix any markdownlint/prettier issues — S

## Files to Modify

- `aet-setup/examples/reference-README.md.example` (create)
- `docs/upgrades/README.md` (fix broken internal link discovered during `make validate`)

## Validation Steps

- [x] `make lint` passes
- [x] `make format-check` passes
- [x] File renders correctly and contains a load-on-demand table mapping docs to task types

## Rollback Plan

1. Delete `aet-setup/examples/reference-README.md.example`.
2. Re-run `make validate` to confirm clean state.

---

_Stage: qa-complete_
_Next step: run `aet-review`_
