---
id: are-05-security-guidelines-template
size: S
blocked_by: []
pipeline: standard
---

# Plan: Add `security-guidelines.md` default template

## Context

Part of [aet-setup reference evolution PRD](../prds/aet-setup-reference-evolution-prd.md). Security conversations should start from a concrete threat model, not generic advice.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [ ] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. Create `aet-setup/examples/security-guidelines.md.example` with Shary-style format — S:
   - Threat Model
   - Controls
   - Forbidden Patterns
2. Include starter threats relevant to most projects (secrets leakage, dependency CVEs, injection, auth bypass) — S
3. Run `make validate` — S

## Files to Modify

- `aet-setup/examples/security-guidelines.md.example` (create)

## Validation Steps

- [ ] `make lint` passes
- [ ] `make format-check` passes
- [ ] Document includes threat model + controls + forbidden patterns

## Rollback Plan

1. Delete `aet-setup/examples/security-guidelines.md.example`.
2. Re-run `make validate`.

---

_Stage: implemented_
_Next step: run `aet-qa`_
