# Plan: CCS-02 — Plan Template Update + Framework ADR + aet-implement Validation

## Context

Part of the Cross-Cutting Completeness framework (PRD:
`docs/prds/cross-cutting-completeness-prd.md`). This ticket delivers the
planning-layer prevention (template update) and the reusable pattern
documentation (ADR), plus the aet-implement validation reminder.

## Tasks

1. **Update `.agents/templates/plan-template.md`** — Add Renderer/UI Tasks (S)

   - Insert a new subsection under Tasks:

     ```markdown
     ### Renderer / UI Tasks (if applicable)

     - [ ] Create/update renderer component(s)
     - [ ] Add/update CSS styles for all custom `className` values
     - [ ] Verify no unstyled `className` references remain
     ```

2. **Create `docs/adr/001-cross-cutting-completeness.md`** — Framework ADR (M)

   - Follow `docs/adr/000-template.md`
   - Define Cross-Cutting Completeness: what it is, why it matters
   - Document the pattern template: "When a diff touches [domain], verify
     [completeness property] by [mechanism]"

   - Include CSS as the first proven example
   - List future domains: i18n, assets, icons, feature flags
   - Reference `aet-review/references/css-completeness-check.md`

3. **Update `aet-implement/SKILL.md`** — Add visual/CSS verification (S)

   - In the Validation strategy section, add:
     > - **Visual / CSS verification** — if the plan includes renderer/UI work,
     >   verify that all custom `className` values have corresponding CSS
     >   definitions before declaring implementation complete.

4. **Validate** — Run `make validate` and fix any issues (S)

## Dependencies

None — can start immediately. CCS-01 (review lens) is not a blocker; the ADR
references the CSS lens as the proven example, but the design is already
defined in the PRD.

## Validation Steps

- [ ] `.agents/templates/plan-template.md` includes Renderer/UI Tasks
- [ ] ADR exists in `docs/adr/` following the ADR template
- [ ] `aet-implement/SKILL.md` mentions visual/CSS verification
- [ ] `make validate` passes (lint, format-check, skill structure)
- [ ] All changed SKILL.md files remain under 400 lines

## Rollback Plan

Revert the commit. All changes are additive.

---

_Stage: merged_
_Next step: —_
