# PRD: aet-validate-ui

## Overview

`aet-validate-ui` is a planning-stage skill that evaluates PRDs and plan.md files for UI/UX coverage gaps before implementation begins. It reads the plan, checks for presence/absence of key UI/UX categories, and produces a structured gap report. The skill is integrated into `aet-pipeline-plan` so that every PRD is automatically validated for UI/UX completeness alongside scope validation.

## Goals

- Prevent plans from shipping with vague or missing UI/UX requirements ("make it responsive," "good UX")
- Provide a repeatable, agent-agnostic checklist that any AI coding agent can run against any plan
- Surface gaps early — while architectural decisions are still fluid — not after `aet-design-system-creation` locks in design direction
- Reduce downstream halts and retrofits during implementation and QA

## Non-Goals

- **Does not generate UI/UX content.** It identifies gaps; it does not write accessibility guidelines, pick component libraries, or design wireframes.
- **Does not replace `aet-design-system-creation`.** Design systems are still the source of truth for visual direction; this skill validates that the plan acknowledges the need for one.
- **Does not enforce a specific design system or framework.** It checks for *presence* of alignment decisions, not *which* design system is chosen.
- **Does not run against application source code.** It evaluates plans and PRDs only.
- **Does not perform automated accessibility audits.** It checks whether the plan *mentions* accessibility targets; axe/Wave/etc. audits happen during implementation/QA.

## User Stories

- As an AI planning agent, I want to validate that a PRD includes UI/UX coverage so that implementation agents don't have to guess or halt for clarification.
- As a product manager reviewing an AI-generated plan, I want a UI/UX gap report so I can see what's missing before approving the plan for implementation.
- As an engineer running `aet-pipeline-plan`, I want UI/UX validation to happen automatically after PRD creation so that no plan advances to implementation with unaddressed interface risks.

## Acceptance Criteria

- [ ] The skill reads a PRD or plan.md and checks at least 7 UI/UX categories: Accessibility, Responsive Design, Component Library Alignment, Form Validation & Error States, Motion & Animation, Information Architecture / Navigation, Content Strategy (empty/loading/error copy).
- [ ] Each category reports one of: `PASS` (explicitly addressed), `FAIL` (missing or vague), `UNKNOWN` (ambiguous language that could go either way).
- [ ] The output is a markdown gap report with per-category findings, specific quotes from the plan (where relevant), and severity ratings (`blocking` vs `warning`).
- [ ] The skill can be invoked manually (`aet-validate-ui on docs/plans/foo-plan.md`) or run automatically as a stage in `aet-pipeline-plan`.
- [ ] The skill directory follows AE Toolkit conventions: `SKILL.md`, `examples/`, `references/`.
- [ ] `SKILL.md` is under 400 lines; deep detail lives in `references/`.
- [ ] `make validate` passes and `make package` produces `aet-validate-ui.skill`.

## Technical Notes

- **Input:** Markdown files (PRD or plan.md). No YAML parsing required; regex + keyword matching is sufficient for v1.
- **Output:** Markdown gap report saved to `docs/ui-reports/{plan-name}-ui-report.md` or printed to stdout.
- **Integration point:** `aet-pipeline-plan` Step 2 (after `aet-plan` creates the PRD, before `aet-validate-scope`). The pipeline should run `aet-validate-ui` and append the report path to the PRD footer.
- **Pattern matching:** Each category has a set of trigger phrases and red flags. For example, Accessibility passes if WCAG level is mentioned; fails if only "accessible" is used without specifics.
- **Extensibility:** Categories are defined as data structures (arrays of keywords, required sub-terms, red flags) so new categories can be added without changing core logic.

## Open Questions

1. Should `FAIL` items block the pipeline (halt at a hard gate) or produce warnings and let the human decide?
2. Should the skill compare against an existing `DESIGN.md` or `CONTEXT.md` glossary, or operate purely on the plan in isolation?
3. Should v1 include a "quick fix" mode that suggests standard boilerplate for missing categories, or stay strictly evaluative?

## Risks

- **False positives:** Overly aggressive keyword matching could flag plans that actually have adequate UI/UX coverage but use different terminology. Mitigation: maintain a synonym map and allow `UNKNOWN` ratings when language is ambiguous.
- **Skill bloat:** If the checklist grows too long, agents may start ignoring it. Mitigation: keep v1 focused to 7 categories; expand via `references/`.
- **Pipeline friction:** Adding a mandatory gate to `aet-pipeline-plan` could slow down planning for backend-only features. Mitigation: allow the pipeline to skip UI validation when the PRD explicitly marks the feature as "no UI" (API-only, CLI-only, etc.).

---
*Stage: scope-validated*
*Next step: run `aet-pipeline-implement` (single task) or `aet-work` (multi-task queue)*
