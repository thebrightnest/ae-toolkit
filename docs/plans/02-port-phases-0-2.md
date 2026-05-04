# Ticket 2: Port Phases 0–2 (Pre-checks, Context, Research)

## Parent

[PRD: aet-design-system-creation Skill](../prds/aet-design-system-creation-prd.md)

## What to Build

Port the first three phases of gstack's design-consultation skill into AET-native form:

- **Phase 0: Pre-checks** — Check for existing DESIGN.md; gather product context from README/package.json; soft gate for PRD existence
- **Phase 1: Product Context** — Single question + "memorable thing" forcing question
- **Phase 2: Research** (optional) — Competitive landscape analysis via WebSearch

Remove all gstack-specific infrastructure: no binaries, no telemetry, no brain sync, no upgrade checks, no proactive prompts, no routing injection.

## Acceptance Criteria

- [ ] Phase 0: Skill detects existing DESIGN.md and offers update/start-fresh/cancel
- [ ] Phase 0: Skill reads PRD from `docs/prds/*.md` if available (soft gate, not hard block)
- [ ] Phase 0: Skill gathers product context from README.md, package.json, directory structure
- [ ] Phase 1: Skill asks the single product context question with pre-filled inference
- [ ] Phase 1: Skill asks the "memorable thing" forcing question
- [ ] Phase 2: Skill offers competitive research via WebSearch (user can decline)
- [ ] Phase 2: If research enabled, skill searches for 5-10 products in the space
- [ ] Phase 2: Skill synthesizes findings into Layer 1/2/3 analysis
- [ ] No gstack binaries, telemetry, brain sync, or routing prompts anywhere in the skill

## Blocked by

- Ticket 1: Scaffold the skill structure

## Technical Notes

- Use native `WebSearch` tool for research
- Use standard file I/O for reading README.md, package.json, etc.
- The "memorable thing" question is critical — every subsequent design decision must reference back to it
- Phase 2 is optional: if user declines research, skip to Phase 3 using agent's built-in design knowledge
