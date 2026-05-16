---
name: aet-validate-ui
description: Validate PRDs and plan.md files for UI/UX coverage gaps before implementation. Checks for Accessibility, Responsive Design, Component Library Alignment, Form Validation & Error States, Motion & Animation, Information Architecture / Navigation, and Content Strategy. Use during planning to surface interface risks before design direction is locked. Triggers on requests like "validate UI coverage," "check UX completeness," "UI gap analysis," or "does this plan cover the interface?"
---

# aet-validate-ui

UI/UX coverage validation for planning documents. Reads a PRD or plan.md, checks seven core UI/UX categories, and produces a structured gap report so interface risks are surfaced before implementation begins.

## When to Use

- After a PRD or plan.md is drafted, before it advances to `aet-validate-scope` or implementation
- When a plan mentions UI/UX in vague terms ("make it responsive," "good UX") and you need specifics
- As a gate in `aet-pipeline-plan` between PRD creation and scope validation
- When the user explicitly asks for UI/UX completeness checking

## When to Skip

- The PRD explicitly marks the feature as "no UI" (API-only, CLI-only, pure backend)
- The plan is for infrastructure, devops, or other non-interface work

## Categories Checked

1. **Accessibility** — WCAG level, screen reader support, keyboard navigation
2. **Responsive Design** — breakpoints, mobile strategy, touch targets
3. **Component Library Alignment** — design system choice, component reuse
4. **Form Validation & Error States** — input feedback, error messaging, validation patterns
5. **Motion & Animation** — transitions, loading states, performance budget
6. **Information Architecture / Navigation** — wayfinding, hierarchy, user flows
7. **Content Strategy** — empty states, loading copy, error messages, microcopy

## Commands

### `validate-ui`

Run UI/UX gap analysis against a planning document.

**Input:** Path to PRD or plan.md

**Output:** Markdown gap report with per-category findings, severity ratings, and specific quotes from the source document.

## Rating Scale

| Rating    | Meaning                                                 |
| --------- | ------------------------------------------------------- |
| `PASS`    | Category is explicitly addressed with sufficient detail |
| `FAIL`    | Category is missing or described with vague language    |
| `UNKNOWN` | Language is ambiguous — could be adequate or inadequate |

## Severity

| Severity   | Action                                     |
| ---------- | ------------------------------------------ |
| `blocking` | Plan should not advance without addressing |
| `warning`  | Surface for human decision                 |

## Key Principles

- **Evaluative, not generative** — identifies gaps; does not write guidelines or pick frameworks
- **Keyword + pattern matching** — sufficient for v1; no YAML parsing required
- **Extensible categories** — new categories can be added by updating keyword arrays
- **Agent-agnostic** — any coding agent can run the checklist against any markdown plan
