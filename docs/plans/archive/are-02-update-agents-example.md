---
id: are-02-update-agents-example
size: M
blocked_by: []
pipeline: standard
---

# Plan: Update `AGENTS.md.example` to list reference docs

## Context

Part of [aet-setup reference evolution PRD](../prds/aet-setup-reference-evolution-prd.md). The default `AGENTS.md` template must tell agents which `docs/references/` docs exist and when to load them.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [ ] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. Read current `aet-setup/examples/AGENTS.md.example` — S
2. Add/update the "Reference Docs (load on demand)" section with a table mapping each new reference doc to its trigger condition — S
3. Ensure the section stays under the overall 200-line AGENTS.md budget guidance — S
4. Run `make validate` — S

## Files to Modify

- `aet-setup/examples/AGENTS.md.example`

## Validation Steps

- [ ] `make lint` passes
- [ ] `make format-check` passes
- [ ] Table includes all reference docs: testing-strategy, api-conventions, security-guidelines, ui-conventions, worktree-ship-hygiene

## Rollback Plan

1. Revert changes to `aet-setup/examples/AGENTS.md.example`.
2. Re-run `make validate`.

---

_Stage: reviewed_
