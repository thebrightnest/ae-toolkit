---
id: 01-scaffold-skill-structure
blocked_by: []
size: M
---

# Ticket 1: Scaffold the aet-design-system-creation Skill Structure

## Parent

[PRD: aet-design-system-creation Skill](../prds/aet-design-system-prd.md)

## What to Build

Create the `aet-design-system-creation/` directory with the standard AET skill structure. Add YAML frontmatter, shared preamble, when-to-use section, and command definitions. Update README.md to include the new skill in the skills table.

This is foundational scaffolding — no actual design logic yet, just the skill container and AET-native structure.

## Acceptance Criteria

- [x] `aet-design-system-creation/SKILL.md` exists with:
  - [x] YAML frontmatter (`name`, `description`)
  - [x] AET shared preamble (BRANCH, REPO_STATE, AGENTS_MD, LEARNINGS, ACTIVE_PLAN, LAST_PIV)
  - [x] `## When to Use` section
  - [x] `## Commands` section with `design-system`, `design-review`, `design-check`
- [x] `aet-design-system-creation/examples/README.md` exists
- [x] `aet-design-system-creation/references/design-principles.md` exists
- [x] `aet-design-system-creation/references/typography-guide.md` exists
- [x] README.md skills table updated with `aet-design-system-creation` row
- [x] `make add-skill NAME=aet-design-system-creation` produces correct structure (test by running it)

_Stage: implemented_
_Merged: 79ad754feaea6d5c19af4d6e25eb7818b2132305_

## Blocked by

None — can start immediately.

## Technical Notes

- Use existing skills (aet-plan, aet-review) as reference for AET voice and structure
- Frontmatter description should explicitly mention triggers: "design system", "create DESIGN.md", "brand guidelines", "visual design"
- The skill should be opinionated in its description to match the chosen posture
