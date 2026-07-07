---
id: are-08-update-skill-and-checklist
size: M
blocked_by: []
pipeline: standard
---

# Plan: Update `aet-setup/SKILL.md` and `aet-setup/checklist.md`

## Context

Part of [aet-setup reference evolution PRD](../prds/aet-setup-reference-evolution-prd.md). The skill instructions and master checklist must describe and verify the new `docs/references/` scaffolding.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [ ] If a reproducible defect was described, redirected to `aet-bug-report`

## Task List

1. Read current `aet-setup/SKILL.md` and `aet-setup/checklist.md` — S
2. Update `aet-setup/SKILL.md` "Generated Artifacts" and "Agentic Workflow Infrastructure" sections to list the new reference templates and their `docs/references/` copy destination — M
3. Update `aet-setup/checklist.md` with verification items for reference docs (existence, load-on-demand README, no bloat) — S
4. Ensure `aet-setup/SKILL.md` remains under 400 lines; move overflow to `aet-setup/references/README.md` if needed — S
5. Run `make validate` — S

## Files to Modify

- `aet-setup/SKILL.md`
- `aet-setup/checklist.md`
- `aet-setup/references/README.md` (only if overflow is needed)

## Validation Steps

- [ ] `make lint` passes
- [ ] `make format-check` passes
- [ ] `make validate` passes
- [ ] `aet-setup/SKILL.md` line count ≤ 400
- [ ] Checklist includes reference-doc verification items

## Rollback Plan

1. Revert changes to `aet-setup/SKILL.md` and `aet-setup/checklist.md`.
2. Re-run `make validate`.

---

_Stage: reviewed_
