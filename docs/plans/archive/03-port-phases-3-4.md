---
id: 03-port-phases-3-4
blocked_by:
  - 02-port-phases-0-2
size: M
---

# Ticket 3: Port Phases 3–4 (Proposal + DESIGN.md)

## Parent

[PRD: aet-design-system-creation Skill](../prds/aet-design-system-prd.md)

## What to Build

Port the core design proposal and DESIGN.md generation phases:

- **Phase 3: The Complete Proposal** — Present aesthetic, decoration, layout, typography, color, motion as one coherent package with SAFE/RISK breakdown. Use AskUserQuestion with the AET decision format.
- **Phase 4: DESIGN.md Generation** — Generate the structured `DESIGN.md` file in project root.

Also implement taste profile reading/writing to `docs/designs/taste-profile.json`.

## Acceptance Criteria

- [ ] Phase 3: Skill presents a complete design proposal covering all dimensions (aesthetic, typography, color, layout, spacing, motion)
- [ ] Phase 3: Proposal includes specific font names (not generic defaults) and hex color values
- [ ] Phase 3: SAFE/RISK breakdown clearly labels which choices are conservative vs. bold
- [ ] Phase 3: User can accept, reject, or modify any aspect via conversation
- [ ] Phase 4: Skill generates `DESIGN.md` with all required sections (Aesthetic Direction, Typography, Color System, Layout & Spacing, Motion & Animation, Component Patterns, Asset Guidelines, Accessibility)
- [ ] Taste profile: Skill reads `docs/designs/taste-profile.json` at start if it exists
- [ ] Taste profile: Skill updates `docs/designs/taste-profile.json` with approvals/rejections at end
- [ ] Taste profile: Confidence scores decay 5% per week of inactivity
- [ ] If taste profile contradicts user request, skill flags the conflict and asks how to proceed

## Blocked by

- Ticket 2: Port Phases 0–2

## Technical Notes

- The proposal must be opinionated — no hedging, no "you could choose X or Y". Pick one and defend it.
- DESIGN.md should be markdown, human-readable, and serve as the source of truth for implementation
- Taste profile schema: `{ version: 1, dimensions: { fonts: { approved: [], rejected: [] }, colors: {...}, layouts: {...}, aesthetics: {...} }, sessions: [] }`
- Each taste entry: `{ value, confidence, approved_count, rejected_count, last_seen }`
