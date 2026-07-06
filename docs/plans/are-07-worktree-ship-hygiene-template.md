---
id: are-07-worktree-ship-hygiene-template
size: S
blocked_by: []
pipeline: standard
---

# Plan: Add `worktree-ship-hygiene.md` default template

## Context

Part of [aet-setup reference evolution PRD](../prds/aet-setup-reference-evolution-prd.md). Captures the worktree/ship hygiene rules that prevent unrelated commits from leaking into PR diffs.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [ ] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. Create `aet-setup/examples/worktree-ship-hygiene.md.example` with Personica-style content — S:
   - Before `aet-work run` checklist
   - Before `aet-ship` checklist
   - Red flags (>50 changed files, unrelated docs, queue file changes)
2. Run `make validate` — S

## Files to Modify

- `aet-setup/examples/worktree-ship-hygiene.md.example` (create)

## Validation Steps

- [ ] `make lint` passes
- [ ] `make format-check` passes
- [ ] Document is referenced from `aet-setup/examples/AGENTS.md.example`

## Rollback Plan

1. Delete `aet-setup/examples/worktree-ship-hygiene.md.example`.
2. Re-run `make validate`.

---

_Stage: reviewed_
_Next step: run `aet-sync-docs`_
