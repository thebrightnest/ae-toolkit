# PRD: aet-bug-report

## Overview

A dedicated skill for bug investigation and fixing within the Agentic Engineering Toolkit. `aet-bug-report` provides a lightweight, structured workflow that sits between `aet-plan` (too heavy for bugs) and raw `aet-implement` (too unstructured for root-cause analysis). It guides the agent through reproduction, diagnosis, fix, and validation — producing a concise bug report as output — without generating PRDs, user stories, or UI mockups.

## Goals

- Provide a repeatable, lightweight process for debugging that prevents both over-planning and under-thinking
- Produce a standardized mini-report capturing symptoms, reproduction steps, root cause, fix, and lessons learned
- Keep the skill self-contained under 400 lines; deep detail lives in `references/`
- Prevent scope creep by hard-gating: if the issue cannot be reproduced as unexpected behavior, redirect to `aet-plan`
- Integrate cleanly with existing skills: `aet-tdd` for test-first fixes, `aet-cso` for security bugs, `aet-evolve` for lessons-learned feedback

## Non-Goals

- Does NOT produce PRDs, user stories, architecture diagrams, or UI mockups
- Does NOT mandate test-first development (TDD is a separate skill)
- Does NOT handle feature requests or "this should work differently" feedback — those belong in `aet-plan`
- Does NOT replace `aet-qa` or `aet-review` (it runs _before_ them, not instead of them)
- Does NOT auto-generate patches without human confirmation on high-risk changes (deletions, auth, data migrations)

## User Stories

- As a developer using the AE Toolkit, I want to hand a bug to an AI agent with a lightweight structured process so that I don't have to write a full PRD for a one-line fix
- As a developer, I want the agent to verify it can reproduce the bug before attempting a fix so that we don't fix symptoms instead of root causes
- As a developer, I want a concise bug report as output so that I can review the reasoning, share it with my team, or feed it into `aet-evolve`
- As a toolkit maintainer, I want the bug skill to stay under 400 lines so that it remains fast to load and easy to maintain

## Acceptance Criteria

- [ ] `aet-bug-report/SKILL.md` exists with valid YAML frontmatter (`name`, `description`)
- [ ] Skill triggers on: "fix this bug," "investigate this error," "something is broken," "debug this," or similar intent
- [ ] Skill defines a 4-step workflow: Reproduce → Root-Cause → Fix → Validate
- [ ] Step 1 (Reproduce) includes a hard gate: if unexpected behavior cannot be demonstrated, abort and redirect to `aet-plan`
- [ ] Step 2 (Root-Cause) requires evidence-based diagnosis, not hypothesis without proof
- [ ] Step 3 (Fix) requires human confirmation before high-risk changes (deletions, auth, data migrations)
- [ ] Step 4 (Validate) confirms the fix resolves the issue without regressions
- [ ] Skill produces a bug report output with sections: Symptoms, Reproduction Steps, Root Cause, Fix Summary, Regression Test, Lessons Learned
- [ ] `examples/` and `references/` subdirectories exist
- [ ] `references/bug-report-template.md` contains the full output template
- [ ] `references/diagnostic-techniques.md` contains investigation patterns (bisect, binary search, logging, etc.)
- [ ] `make validate` passes after skill creation
- [ ] `make package` produces a valid `aet-bug-report.skill` file

## Technical Notes

- Follow existing skill structure: `SKILL.md` + `examples/` + `references/`
- YAML frontmatter must include `name: aet-bug-report` and `description` explaining when to trigger
- Description should explicitly mention "bug," "error," "debug," or "fix"
- Keep `SKILL.md` under 400 lines; move verbose procedures to `references/`
- The bug report output should be saved to a predictable path (e.g., `docs/bugs/{id}-bug-report.md` or printed inline)
- Consider a `severity` tag in the report (critical / high / medium / low) to guide validation depth
- Integration points:
  - `aet-tdd`: call before or after Fix step if user wants test-first
  - `aet-cso`: call during Validate if bug touches auth, data, or boundaries
  - `aet-evolve`: append lessons learned to `.agents/learnings.jsonl`

## Open Questions

- Should the bug report be saved to disk (`docs/bugs/`) or just returned in conversation? (Leaning: saved, for audit trail)
- Should the skill auto-generate a short ID/timestamp for each bug report?
- How should the skill handle bugs that span multiple repositories or services?

---

_Stage: scope-validated_
_Next step: run `aet-pipeline-implement` (single task) or `aet-work` (multi-task queue)_
