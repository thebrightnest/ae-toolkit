---
id: retire-design-system-creation
status: scope-validated
---

# PRD: Retire aet-design-system-creation

## Overview

`aet-design-system-creation` produces a `DESIGN.md` (aesthetic direction, typography,
colour, layout, motion) through a guided conversation. It has never been used in
practice: design-system work is done with dedicated external design skills
(e.g. `impeccable`), which cover DESIGN.md, tokens, critique and live iteration in
more depth than the toolkit should own.

The skill is not a pipeline step. `aet-pipeline-plan` runs `aet-plan` →
`aet-validate-scope`; `aet-prime` does not route to it; nothing in `src/aet/`,
`.agents/`, `scripts/`, `.agents/doc-rules.yaml`, or any other skill references it.
Its only live mentions are the README skills table and the README intro paragraph,
which describes it as a pipeline stage it never was.

Because the toolkit is installed as a whole (ADR-016, ADR-018), an unused skill is not
free: it adds triggers ("design system", "visual design", "brand guidelines") that
compete with the user's preferred design skills, and it costs skill-list context in
every session.

Precedent: ADR-017 (`aet-discover`) and ADR-080 (`aet-work`, `aet-extract-stack`,
`aet-upgrade`). The same history rule applies.

## Intake Triage

Enhancement, not a defect. No existing behaviour misbehaves reproducibly; the skill is
unused. Classified `normal`.

## Goals

- **G1**: The distributed skill set no longer contains `aet-design-system-creation`.
- **G2**: No live documentation describes DESIGN.md creation as a toolkit pipeline step.
- **G3**: The decision is recorded so it is not re-litigated or silently reversed.

## Non-Goals

- Replacing the skill with another toolkit skill, or vendoring/naming `impeccable` as a
  dependency. Design-system authoring is out of the toolkit's scope.
- Changing `aet-validate-scope`'s UI Coverage Lens. Its "which design system or
  component library" question is generic and stays.
- Rewriting history: `CHANGELOG.md` release sections, `PRODUCT.md` "What's New in
  v0.7.0", ADR-017, ADR-039's inventory, `docs/prds/aet-design-system-prd.md`,
  `docs/prds/aet-validate-ui-prd.md`, and `docs/plans/archive/` stay as written
  (ADR-080 §6).
- Editing `tests/fixtures/usage/claude_live_envelope.json`. It is a captured live
  envelope (it already lists the retired `aet-extract-stack`), not an inventory.
- Changing `aet setup skills`; dangling-link pruning already exists (ADR-080 §5).
- Editing `CHANGELOG.md` or `PRODUCT.md`. Both belong to `aet-release-prep` at release
  time (ADR-007); the commit message carries the user-facing note (removed skill, run
  `aet update`, `aet setup skills` prunes the link).

## Requirements

- **R-1**: `skills/aet-design-system-creation/` no longer exists.
- **R-2**: `README.md` no longer lists the skill in the skills table, and its intro
  paragraph no longer names `/aet-design-system-creation` or says
  `/aet-validate-scope` checks "the plan and design".
- **R-3**: ADR-081 records the retirement (context, decision, consequences, rejected
  alternatives) and is indexed in `docs/adr/README.md`.
- **R-4**: `git grep -n aet-design-system-creation` matches only the historical
  locations listed in Non-Goals, ADR-081, and this PRD.

## Stories

1. As a toolkit user, I no longer see `aet-design-system-creation` in my agent's skill
   list after updating, so "design system" requests go to the design skills I chose.
   (R-1)
2. As a reader of the README, I see the pipeline as it actually runs, with no design
   stage that the toolkit does not provide. (R-2)
3. As a maintainer, I can find why the skill was removed and what replaced it. (R-3)

## Tasks

- **RDS-01** — Retire the skill, update README, add ADR-081.
  Size S. Covers R-1…R-4.

## Acceptance Criteria

- [ ] `test -d skills/aet-design-system-creation` fails.
- [ ] `make validate` passes.
- [ ] R-4 grep result matches the allowed set.
- [ ] ADR-081 exists and is listed in `docs/adr/README.md`.

## Risks

- **Copy-based installs** keep a stale directory until deleted by hand. Documented in
  ADR-081 consequences and, at release, the CHANGELOG upgrade note.
- **A project's existing DESIGN.md** is unaffected; nothing in the toolkit reads it.

---

*Stage: synced*

*Next step: run `aet-ship`*
