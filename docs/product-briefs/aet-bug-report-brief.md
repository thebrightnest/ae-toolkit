# Product Brief: aet-bug-report

## Problem

The AE Toolkit lacks a dedicated skill for bug investigation and fixing. Users currently have two bad options:

1. **Run `aet-plan`** — which treats bugs as new features, producing PRDs, user stories, architecture decisions, and UI mockups. This leads to massive overthinking for what is often a one-line fix or a localized logic error.
2. **Skip planning and run `aet-implement` directly** — with a vague prompt like "fix the bug." This risks missing the root cause, introducing side-effects, or fixing symptoms instead of the actual problem.

Both paths waste time or create risk. There is no structured but lightweight middle ground.

## Evidence

- The toolkit author (primary user) reports using both paths inconsistently and being dissatisfied with both.
- `aet-plan` is explicitly designed for "starting a new feature, sprint, or project" — its procedures (clarify-goal → create-prd → create-stories → plan) are mismatched for bug fixes.
- `aet-implement` assumes an approved plan.md exists. When invoked without one, it lacks the investigation rigor bugs require.
- Existing skills like `aet-qa` and `aet-review` catch bugs late; none guide the actual debugging process.

## Target User

- **Primary:** AE Toolkit users (developers using agentic skills) who encounter runtime errors, regressions, logic bugs, or misalignments.
- **Context:** They want a quick, repeatable process to hand a bug to an AI agent without either (a) writing a full PRD or (b) hoping the agent figures it out from a one-liner.

## Status Quo Workaround

Users either:

- Accept the overhead of `aet-plan` and manually ignore the irrelevant artifacts
- Or bypass planning entirely and iterate blindly with `aet-implement`

Neither is satisfactory.

## Narrowest Wedge

A single `SKILL.md` file (`aet-bug-report`) containing:

1. A **4-step workflow**: Reproduce → Root-Cause → Fix → Validate
2. A **bug report template** as output: symptoms, reproduction steps, root cause, fix summary, regression tests, lessons learned
3. **Guardrails**: no PRDs, no user stories, no UI mockups, no architecture decisions unless the bug reveals a structural flaw
4. **Hard line limit**: stays under 400 lines, with deep detail moved to `references/`

The skill triggers on phrases like "fix this bug," "investigate this error," "something is broken," or "debug this."

## Future-Fit

As AI coding agents handle more maintenance work, the ratio of bug-fixing to greenfield building will increase. A dedicated bug skill becomes _more_ essential over time, not less. This skill also creates a natural hook for `aet-evolve` — every bug report ends with a "lessons learned" check that can feed back into rules and templates.

## Risks & Open Questions

- How does this skill interact with `aet-tdd`? Should it require tests before fix, or is that optional?
- Should the skill integrate with `aet-cso` for security-relevant bugs?
- How do we prevent scope creep where a "bug" is actually a missing feature in disguise?

---

_Stage: brief-validated_
_Next step: run `aet-plan`_
