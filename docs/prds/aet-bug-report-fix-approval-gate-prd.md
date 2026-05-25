# PRD: aet-bug-report Fix Approval Gate

## Overview

The `aet-bug-report` skill currently permits the AI agent to apply fixes immediately after root-cause diagnosis, with human confirmation required only for "high-risk" changes (deletions, auth, data migrations). In practice, this leads to unauthorized implementation on low-risk fixes too — the agent interprets trigger phrases like "fix this bug" as a license to write code without stopping.

This PRD revises the skill to introduce a **mandatory fix-approval gate** between Step 2 (Root-Cause) and Step 3 (Fix). No code is written until the user explicitly approves the diagnosis and proposed fix.

## Goals

- Eliminate all unauthorized implementation during `aet-bug-report` sessions
- Preserve the skill's lightweight character — the gate is a single pause, not a bureaucracy
- Keep the skill self-contained; the gate lives in `SKILL.md`, not in cross-cutting AGENTS.md rules
- Update examples to model the new gate behavior

## Non-Goals

- Does NOT change the reproduction gate (Step 1) or validation gate (Step 4)
- Does NOT add a gate to any other skill (aet-implement, aet-tdd, etc.)
- Does NOT introduce risk-level classification complexity — all fixes pause
- Does NOT require a new `.agents/commands/` file or shared template

## User Stories

- As a developer invoking `aet-bug-report`, I want the agent to pause and show me its diagnosis before writing any code, so that I retain control over what changes are made to my codebase.
- As a developer, I want the approval step to be lightweight (one response: "yes" / "no" / "change X"), so that the skill still feels faster than `aet-plan`.
- As a toolkit maintainer, I want the skill's examples to show the approval gate being used even for trivial fixes, so that the trained behavior is consistent.

## Acceptance Criteria

- [ ] `aet-bug-report/SKILL.md` includes a new Step 2.5: "Fix Approval Gate (Mandatory)"
- [ ] The gate explicitly instructs the agent: "Do not write, modify, or delete any source code until the user explicitly approves"
- [ ] The gate requires presenting: root-cause diagnosis, proposed fix description, files to modify
- [ ] Step 3 (Fix) is updated to state: "Only proceed here after explicit user approval"
- [ ] The old "high-risk changes only" hard gate in Step 3 is removed or folded into the universal gate
- [ ] Example 1 is updated to show the approval gate in action (even for a one-line fix)
- [ ] `make validate` passes after changes
- [ ] `make package` produces a valid `aet-bug-report.skill`
- [ ] `.agents/reference/skill-writing-guide.md` is updated with an interactive-only exemption note
- [ ] `docs/adr/` is updated with an amendment to ADR 005 documenting the interactive-only exemption

## Technical Notes

- SKILL.md must stay under 400 lines; if the gate adds significant length, trim elsewhere
- The approval gate should be framed as a user convenience, not a restriction: "Here's what I found and what I plan to change. Approve to proceed?"
- Keep trigger phrases unchanged; the fix is in workflow behavior, not description
- The existing references (`bug-report-template.md`, `diagnostic-techniques.md`) do not need changes

## Open Questions

- Should the bug report template include an "Approval Record" section? (Leaning: no — keep it lightweight; approval is a session event, not a report artifact.)
- ~~Does the skill need `AET_EXECUTION_MODE` handling?~~ Resolved: No. `aet-bug-report` is interactive-only by design. The validator's literal-string check for `"Approve to proceed?"` is insufficient; we will also update the Skill Writing Guide and ADR 005 to document this exemption.

---

_Stage: scope-validated_
_Next step: run `aet-pipeline-implement` (single task) or `aet-work` (multi-task queue)_
