---
id: are-06-ui-conventions-template
size: S
blocked_by: []
pipeline: standard
---

# Plan: Add `ui-conventions.md` default template

## Context

Part of [aet-setup reference evolution PRD](../prds/aet-setup-reference-evolution-prd.md). For frontend projects, this doc prevents reinventing accessible UI primitives and keeps design tokens consistent.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [ ] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. Create `aet-setup/examples/ui-conventions.md.example` with Personica-style content — S:
   - Component source priority (shadcn/ui → custom)
   - Rationale
   - How to add/customize shadcn/ui components
   - Design-token alignment
2. Run `make validate` — S

## Files to Modify

- `aet-setup/examples/ui-conventions.md.example` (create)

## Validation Steps

- [ ] `make lint` passes
- [ ] `make format-check` passes
- [ ] Document is referenced from `aet-setup/examples/AGENTS.md.example`

## Rollback Plan

1. Delete `aet-setup/examples/ui-conventions.md.example`.
2. Re-run `make validate`.

---

_Stage: plan-approved_
_Next step: run `aet-work`_
