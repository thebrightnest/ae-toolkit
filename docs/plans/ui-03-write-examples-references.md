# Plan: ui-03 — Write examples/ and references/ for aet-validate-ui

## Context

- PRD: `docs/prds/aet-validate-ui-prd.md`
- SKILL.md core is written from `ui-02`.
- Examples and references must align with the final SKILL.md content.

## Tasks

1. Write `aet-validate-ui/examples/README.md` with:
   - Full PRD check (web app with gaps)
   - Plan check (API-only feature that skips UI validation)
   - All-pass scenario (comprehensive PRD)
   - Nothing-found scenario (plan has no UI mentions at all)
2. Write `aet-validate-ui/references/README.md` with:
   - Category definitions and keyword maps
   - Red flags and ambiguous language guide
   - Synonym map for terminology variation
   - Severity rubric (blocking vs warning)
   - Integration notes for `aet-pipeline-plan`

## Dependencies

- Blocked by `ui-02-write-skill-core` (examples must match final skill instructions)

## Validation Steps

- [ ] `examples/README.md` covers all 4 scenarios
- [ ] `references/README.md` documents all 7 categories in depth
- [ ] All internal links from SKILL.md to examples/references resolve
- [ ] `make validate` passes

## Rollback Plan

Delete `examples/README.md` and `references/README.md`, re-create from SKILL.md.

---
*Stage: synced*
*Next step: run `aet-ship`*
