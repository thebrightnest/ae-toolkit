# Ticket 1: Scaffold the aet-design-system-creation Skill Structure

## Parent

[PRD: aet-design-system-creation Skill](../prds/aet-design-system-prd.md)

## What to Build

Create the `aet-design-system-creation/` directory with the standard AET skill structure. Add YAML frontmatter, shared preamble, when-to-use section, and command definitions. Update README.md to include the new skill in the skills table.

This is foundational scaffolding — no actual design logic yet, just the skill container and AET-native structure.

## Acceptance Criteria

- [ ] `aet-design-system-creation/SKILL.md` exists with:
  - [ ] YAML frontmatter (`name`, `description`)
  - [ ] AET shared preamble (BRANCH, REPO_STATE, AGENTS_MD, LEARNINGS, ACTIVE_PLAN, LAST_PIV)
  - [ ] `## When to Use` section
  - [ ] `## Commands` section with `design-system`, `design-review`, `design-check`
- [ ] `aet-design-system-creation/examples/README.md` exists
- [ ] `aet-design-system-creation/references/design-principles.md` exists
- [ ] `aet-design-system-creation/references/typography-guide.md` exists
- [ ] README.md skills table updated with `aet-design-system-creation` row
- [ ] `make add-skill NAME=aet-design-system-creation` produces correct structure (test by running it)

## Blocked by

None — can start immediately.

## Technical Notes

- Use existing skills (aet-plan, aet-review) as reference for AET voice and structure
- Frontmatter description should explicitly mention triggers: "design system", "create DESIGN.md", "brand guidelines", "visual design"
- The skill should be opinionated in its description to match the chosen posture
