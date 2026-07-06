---
id: are-03-testing-strategy-template
size: M
blocked_by: []
pipeline: standard
---

# Plan: Add `testing-strategy.md` default template

## Context

Part of [aet-setup reference evolution PRD](../prds/aet-setup-reference-evolution-prd.md). This is the highest-value reference doc; it prevents both undertesting and overtesting by giving agents a reusable decision framework.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [ ] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. Create `aet-setup/examples/testing-strategy.md.example` with the following sections — M:
   - Testing pyramid (unit / integration / E2E)
   - Suite splitting by concern (HTTP, API, MCP, integration, unit)
   - Overtesting rules: do not test presentational components, snapshots of markup, third-party behavior, trivial prop pass-through
   - Validation by change type matrix
   - File upload integration test rule
   - Component testing mocking rules (mock APIs/stores, render real children, stable mock references, API boundary normalization)
2. Keep examples stack-agnostic but include common language runners (PHPUnit, Vitest, pytest) — S
3. Run `make validate` — S

## Files to Modify

- `aet-setup/examples/testing-strategy.md.example` (create)

## Validation Steps

- [ ] `make lint` passes
- [ ] `make format-check` passes
- [ ] Document is loadable on demand and covers overtesting + change-type validation

## Rollback Plan

1. Delete `aet-setup/examples/testing-strategy.md.example`.
2. Re-run `make validate`.

---

_Stage: qa-complete_
_Next step: run `aet-review`_
