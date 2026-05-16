# Product Brief: aet-validate-ui

## Problem

Agentic planning produces thorough technical specifications — API contracts, data models, auth flows, deployment pipelines — but UI/UX requirements are consistently skipped or reduced to hand-wavy platitudes ("make it responsive," "good UX"). This forces downstream skills (`aet-design-system-creation`, `aet-implement`) to guess, halt for clarification, or ship interfaces that fail accessibility, responsive, or usability standards.

## Status Quo

When agents run `aet-plan` today, there is no dedicated step or skill that evaluates whether the PRD includes adequate UI/UX coverage. Agents either:

1. **Skip it entirely** — UI/UX is treated as an implementation detail that will "sort itself out."
2. **Leave it vague** — Plans mention "responsive design" or "accessible" without specific breakpoints, WCAG targets, component library choices, form validation patterns, motion guidelines, or error-state handling.

The existing `aet-design-system-creation` skill can backfill design direction, but it runs _after_ planning. By that point, architectural decisions (API shape, data fetching patterns, state management) are already locked, making UI/UX retrofit expensive or impossible.

## Wedge

A **checklist validator** skill that scans a PRD or plan.md for UI/UX coverage gaps and outputs a structured gap report. The first version focuses on presence/absence checks — not generating the missing content, but surfacing what's missing so the planner can address it before implementation begins.

**Categories checked (v1):**

- Accessibility (WCAG level, ARIA patterns, keyboard navigation, color contrast)
- Responsive design (breakpoint strategy, mobile-first vs desktop-first)
- Component library / design system alignment
- Form validation and error-state patterns
- Motion and animation guidelines
- Information architecture / navigation structure
- Content strategy (empty states, loading states, error copy)

## Verdict

**BUILD** — The gap is real, the wedge is sharp, and the skill fits cleanly into the existing AET planning pipeline between `aet-plan` and `aet-validate-scope` (or as a lens within `aet-review`).

## Notes

- Name candidate: `aet-validate-ui` (parallel to `aet-validate-scope`)
- Trigger phrases: "check UI coverage," "validate UX requirements," "UI/UX gap analysis," "does this plan cover accessibility?"
- This is an evaluation skill, not a generative one. It reads; it does not write application code.

---

_Stage: brief-validated_
_Next step: run `aet-plan`_
