# Plan: CCS-01 — aet-review UI/CSS Completeness Lens

## Context

Part of the Cross-Cutting Completeness framework (PRD:
`docs/prds/cross-cutting-completeness-prd.md`). This ticket delivers the
highest-leverage fix: a mechanical UI/CSS Completeness review lens that
prevents undefined CSS classes from reaching `main`.

## Tasks

1. **Update `aet-review/SKILL.md`** — Add the UI/CSS Completeness lens (M)

   - Insert after the existing "Tests" lens in the `review` command procedure
   - Document the mechanical procedure: extract `className` values from
     new/modified renderer components, filter known global classes, verify each
     remaining custom class exists in the project's stylesheet directory

   - Classify findings as **fix-now** (undefined custom classes)
   - Keep the lens description concise; move deep detail to
     `aet-review/references/` if needed

2. **Create `aet-review/references/css-completeness-check.md`** — Reference doc
   with the detailed procedure (S)

   - Step-by-step shell commands for extracting classNames
   - Example filter list of known global classes
   - Guidance on adapting to different CSS flavors (CSS modules, SCSS, Less)

3. **Validate** — Run `make validate` and fix any issues (S)

## Dependencies

None — can start immediately.

## Validation Steps

- [ ] `aet-review/SKILL.md` includes the UI/CSS Completeness lens
- [ ] Reference doc exists with detailed procedure
- [ ] `make validate` passes (lint, format-check, skill structure)
- [ ] SKILL.md remains under 400 lines

## Rollback Plan

Revert the commit. The change is additive (new lens + reference doc) with no
modifications to existing behavior.

---

_Stage: done_
_Next step: ccs-02 is unblocked, ready to start_
