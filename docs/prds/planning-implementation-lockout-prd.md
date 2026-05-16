# PRD: Planning Implementation Lockout

## Overview

Add explicit implementation-lockout guardrails to all planning-phase skills (`aet-discover`, `aet-plan`, `aet-pipeline-plan`, `aet-validate-scope`) so that when users invoke them with imperative requests ("remove X", "adapt Y", "change Z"), the agent reframes the input as a planning target and never drifts into editing application source code, running tests, or creating implementation branches.

## Goals

- Eliminate implementation drift during planning sessions
- Make planning vs. implementation boundaries explicit in skill instructions
- Ensure imperative user language is reframed as planning goals, not execution directives

## Non-Goals

- Changing implementation skills (`aet-implement`, `aet-pipeline-implement`, `aet-work`)
- Adding tool-level restrictions (e.g., disabling WriteFile globally)
- Changing the skill trigger descriptions or activation logic

## User Stories

- As a toolkit user, when I say "plan how to remove the global Timeline page," the agent produces a PRD and plan instead of deleting files.
- As a toolkit maintainer, I want planning skills to contain explicit "do not implement" language so future skill edits preserve the boundary.

## Acceptance Criteria

- [ ] `aet-plan/SKILL.md` contains a "Planning Lockout" section that forbids editing application source files
- [ ] `aet-pipeline-plan/SKILL.md` contains a "What This Skill Does NOT Do" section with the same constraints
- [ ] `aet-discover/SKILL.md` and `aet-validate-scope/SKILL.md` contain equivalent lockout language
- [ ] Each planning skill prints a visible planning-mode banner at the start of execution
- [ ] Each planning skill explicitly reframes imperative input ("Do X") as a planning target ("Plan how to do X")
- [ ] `make validate` passes after all changes
- [ ] `make package` regenerates all `.skill` files

## Technical Notes

- Skills must remain agent-agnostic: no tool-specific syntax (e.g., "do not use WriteFile")
- Planning skills may still create/edit files in `docs/` and `.agents/` (PRDs, plans, briefs, work-queue)
- Changes should be minimal and fit within the 400-line SKILL.md limit
- An ADR should document this as a reusable pattern for future skills

## Open Questions

- None — scope was clarified in goal-alignment step.

---

_Stage: scope-validated_
_Next step: run `aet-pipeline-implement` (single task) or `aet-work` (multi-task queue)_
