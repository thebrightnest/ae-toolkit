---
subject: retire-aet-design-system-creation
relates: [17, 39, 80]
---

# Retire aet-design-system-creation

## Status

Accepted (2026-10-18). Delivered by `RDS-01` (PRD:
`docs/prds/retire-design-system-creation-prd.md`).

## Context

`aet-design-system-creation` produces a `DESIGN.md` (aesthetic direction,
typography, colour, layout, motion) through a guided conversation. It has never
been used in practice: design-system work is done with dedicated external design
skills (e.g. `impeccable`), which cover tokens, critique, and live iteration in
more depth than the toolkit should own.

The skill is not a pipeline step. `aet-pipeline-plan` runs `aet-plan` →
`aet-validate-scope`; `aet-prime` does not route to it; nothing in `src/aet/`,
`.agents/`, `scripts/`, `.agents/doc-rules.yaml`, or any other skill references
it. Its only live mentions were the README skills table and intro paragraph.

Because the toolkit is installed as a whole (ADR-016, ADR-018), an unused skill
is not free: it adds triggers ("design system", "visual design", "brand
guidelines") that compete with external design skills, and costs skill-list
context in every session.

Precedent: ADR-017 (`aet-discover`) and ADR-080 (`aet-work`,
`aet-extract-stack`, `aet-upgrade`). The same history rule applies.

## Decision

1. **Remove the skill.** `skills/aet-design-system-creation/` is deleted
   outright. Git history keeps it recoverable.
2. **Design-system authoring is outside toolkit scope.** The toolkit focuses on
   engineering workflow. `aet-validate-scope`'s UI Coverage Lens continues to
   ask which design system or component library a UI plan builds on, but the
   toolkit does not author them.
3. **History is not rewritten.** CHANGELOG, PRODUCT.md historical notes,
   earlier PRDs (`aet-design-system-prd.md`, `aet-validate-ui-prd.md`),
   archived plans, ADR-017, and ADR-039's inventory stay as written (ADR-080
   §6). The live usage test fixture
   (`tests/fixtures/usage/claude_live_envelope.json`) is not edited.

## Consequences

- `/aet-design-system-creation` stops resolving; requests for design systems
  route cleanly to external design skills.
- `aet setup skills` prunes dangling symlinks (ADR-080 §5).
- Copy-based installs delete the stale directory by hand.
- Existing `DESIGN.md` files in user projects are unaffected.

## Alternatives Considered

- **Keep the skill as optional** — rejected: the toolkit is installed as a
  whole; an unused skill still costs triggers and context.
- **Fold it into `aet-plan`** — rejected: unused in practice; nothing worth
  carrying over.
