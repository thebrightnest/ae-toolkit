---
id: planning-implementation-lockout-plan
blocked_by: []
size: M
---

# Plan: Planning Implementation Lockout

## Summary

Add explicit implementation-lockout guardrails to all planning-phase skills so imperative user requests are reframed as planning targets, not execution directives.

## User Story

As a toolkit user, when I invoke a planning skill with an imperative request, the agent produces PRDs and plans instead of editing application source code.

## Locked-In Architecture Decisions

- Lockout must be agent-agnostic: no tool-specific restrictions
- Planning skills may create/edit `docs/` and `.agents/` files only
- Lockout applies to: `aet-discover`, `aet-plan`, `aet-pipeline-plan`, `aet-validate-scope`

## Files to Create and Modify

- `aet-plan/SKILL.md` — add "Planning Lockout" section + rules + principles
- `aet-pipeline-plan/SKILL.md` — add "What This Skill Does NOT Do" + Step 0 banner + principles
- `aet-discover/SKILL.md` — add equivalent lockout language
- `aet-validate-scope/SKILL.md` — add equivalent lockout language
- `docs/adr/002-planning-implementation-lockout.md` — document the pattern

## Task List

1. [x] Update `aet-plan/SKILL.md` with lockout section, rules, and principles
2. [x] Update `aet-pipeline-plan/SKILL.md` with lockout section, Step 0 banner, and principles
3. [x] Update `aet-discover/SKILL.md` with lockout language
4. [x] Update `aet-validate-scope/SKILL.md` with lockout language
5. [x] Create ADR `docs/adr/002-planning-implementation-lockout.md`
6. [x] Run `make validate`
7. [x] Run `make package`

## Self-Validation Strategy

- `make validate` must pass (lint, format-check, skill structure)
- `make package` must regenerate `.skill` files without errors
- All modified SKILL.md files must remain under 400 lines
- No application source files are modified (only docs and skill definitions)

---

\_Stage: merged
\_Next step: none — pipeline complete
