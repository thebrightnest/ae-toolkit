# Plan: ui-02 — Write aet-validate-ui SKILL.md

## Context

- PRD: `docs/prds/aet-validate-ui-prd.md`
- Scaffold is in place from `ui-01`.
- SKILL.md must be under 400 lines; deep detail moves to `references/`.

## Tasks

1. Write YAML frontmatter with `name`, `description`, and trigger phrases.
2. Write `## When to Use` section.
3. Write `## Shared Preamble` — context to collect before executing.
4. Write `## Commands`:
   - `validate` — main command: read plan, check 7 categories, output gap report.
   - `validate-pipeline` — integration command for `aet-pipeline-plan` (same logic, different entry point).
5. Write the 7 category check procedures with keyword maps, pass/fail/unknown criteria, and severity rubric.
6. Write `## Key Principles`.
7. Keep SKILL.md under 400 lines.

## Dependencies

- Blocked by `ui-01-scaffold-skill`

## Validation Steps

- [ ] SKILL.md is under 400 lines
- [ ] YAML frontmatter has `name` and `description`
- [ ] `name` matches directory name
- [ ] All relative internal markdown links resolve
- [ ] `make validate` passes

## Rollback Plan

Revert `aet-validate-ui/SKILL.md` to the scaffold state.

---
*Stage: synced*
*Next step: run `aet-ship`*
