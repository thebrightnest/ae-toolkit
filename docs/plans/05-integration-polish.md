# Ticket 5: AET Integration & Polish

## Parent

[PRD: aet-design-system-creation Skill](../prds/aet-design-system-prd.md)

## What to Build

Final integration pass: add AET-specific integration points, ensure consistent voice throughout, create examples and references content, and package the skill.

- Add integration points section (how this connects to aet-plan, aet-validate-scope, aet-implement)
- Review all prose to match AET voice (builder-to-builder, concrete, direct)
- Populate examples/ and references/ with useful content
- Ensure `make package` produces a valid `aet-design-system-creation.skill` file

## Acceptance Criteria

- [ ] SKILL.md includes `## Integration Points` section explaining workflow position
- [ ] SKILL.md voice reviewed: no corporate filler, no AI vocabulary (delve, crucial, robust, etc.), no em dashes
- [ ] `examples/README.md` contains a sample DESIGN.md output (can be a realistic example for a fictional SaaS product)
- [ ] `references/design-principles.md` explains AET design philosophy (opinionated, research-driven, user-outcome focused)
- [ ] `references/typography-guide.md` provides reference material for font pairing and scale systems
- [ ] `make package` succeeds and produces `aet-design-system-creation.skill`
- [ ] Skill installs correctly via `make install-skills`
- [ ] README.md workflow diagram updated to show `aet-design-system-creation` between `aet-plan` and `aet-validate-scope`

## Blocked by

- Ticket 4: Port Phase 5 (Preview)

## Technical Notes

- Voice check: read through entire SKILL.md and flag any gstack-isms or AI-isms
- The examples should be realistic enough to be useful as a reference
- Package test: run `make package` and verify the `.skill` file is created
- Consider adding a simple test: run the skill on this repo (aiskills) and verify it produces output
