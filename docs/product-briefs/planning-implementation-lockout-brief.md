---
name: planning-implementation-lockout
date: 2026-05-16
---

# Planning Implementation Lockout — Product Brief

## Problem Statement

When users invoke `aet-plan` or `aet-pipeline-plan` with imperative requests (e.g., "remove the global Timeline page", "adapt this to project scope"), the agent frequently drifts into implementation mode. It edits source files, runs tests, and creates branches instead of producing PRDs and plans.

This happened today in a live session: the user asked what could be done about the drift, and the agent immediately edited two SKILL.md files, created an ADR, and ran `make validate` — exactly the bug being reported.

## Evidence

- Direct user report: "a very common error"
- Live reproduction: agent edited `aet-pipeline-plan/SKILL.md`, `aet-plan/SKILL.md`, created `docs/adr/002-planning-implementation-lockout.md`, and ran Make targets without producing a plan first
- Example prompt that triggered implementation drift:
  > "run /skill:aet-pipeline-plan i want the global/top level Timeline page to not exist anymore. We should only have the Project Timeline page/level. The page should be adapted to only work in project scope. Review the http api as well."

## Target Users

- Toolkit users (engineers using AE Toolkit skills in their projects)
- Toolkit maintainers (authors of skills who need stronger guardrails)

## Proposed Solution

Add explicit "implementation lockout" guardrails to planning skills:

1. A visible planning-mode banner at the start of every planning session
2. Explicit negative constraints (what the skill does NOT do)
3. Imperative-input reframing: "Do X" → "Plan how to do X"

## Scope

- In scope: `aet-plan/SKILL.md`, `aet-pipeline-plan/SKILL.md`
- Out of scope: `aet-implement`, `aet-pipeline-implement`, `aet-work`

## Verdict

BUILD
