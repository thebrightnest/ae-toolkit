# Plan: ui-01 — Scaffold aet-validate-ui Skill Structure

## Context

- PRD: `docs/prds/aet-validate-ui-prd.md`
- Brief: `docs/product-briefs/ui-validation-brief.md`
- Follows the AE Toolkit skill convention: one directory per skill with `SKILL.md`, `examples/`, `references/`.

## Tasks

1. Create `aet-validate-ui/` directory.
2. Create `aet-validate-ui/SKILL.md` with valid YAML frontmatter (`name: aet-validate-ui`, `description`) and a placeholder body.
3. Create `aet-validate-ui/examples/` directory.
4. Create `aet-validate-ui/references/` directory.
5. Run `make validate` to confirm the scaffold passes structure checks (directory existence, frontmatter validity).

## Dependencies

None — this is the first task.

## Validation Steps

- [ ] `aet-validate-ui/` exists
- [ ] `aet-validate-ui/SKILL.md` exists with valid YAML frontmatter
- [ ] `aet-validate-ui/examples/` exists
- [ ] `aet-validate-ui/references/` exists
- [ ] `make validate` passes structure checks for the new skill

## Rollback Plan

Delete `aet-validate-ui/` directory and re-run `make validate`.

---
*Stage: synced*
*Next step: run `aet-ship`*
