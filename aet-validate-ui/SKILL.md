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

## Shared Preamble

Before executing any command in this skill, collect the following context:

- `BRANCH` — current git branch
- `REPO_STATE` — clean / dirty / merge-conflict
- `AGENTS_MD` — presence and last-modified date of AGENTS.md
- `LEARNINGS` — top-3 relevant entries from `.agents/learnings.jsonl` (if exists)
- `ACTIVE_PLAN` — the plan.md or PRD file the user wants to validate
- `ACTIVE_PRD_STAGE` — current `*Stage:` value from the most-recently-modified `docs/prds/*.md` footer (if exists)
- `ACTIVE_PLAN_STAGE` — current `*Stage:` value from the most-recently-modified `docs/plans/*.md` footer (if exists)

Use this context to ground all recommendations. Do not ask the user to provide it manually.

If a stage is found, print at the start of execution: `"📍 Current stage: {stage}."`

## Commands

### `validate`

Run UI/UX gap analysis against a planning document.

**Input:** Path to PRD or plan.md

**Procedure:**

1. Read the source document
2. Check for the "no UI" marker — if present, print skip reason and exit
3. Run the 7 category checks (see Categories Checked below)
4. Assign PASS / FAIL / UNKNOWN per category using keyword maps
5. Assign severity per finding (`blocking` or `warning`)
6. Produce a markdown gap report
7. Print the report to stdout and optionally save to `docs/ui-reports/{plan-name}-ui-report.md`

**Output:** Markdown gap report with:

- Per-category rating (PASS / FAIL / UNKNOWN)
- Relevant quotes from the source document
- Severity (`blocking` or `warning`)
- Brief rationale for each rating

### `validate-pipeline`

Integration entry point for `aet-pipeline-plan`. Runs `validate` with default behavior and appends the report path to the PRD footer.

**Procedure:**

1. Receive the PRD path from the pipeline orchestrator
2. Run `validate` with the same procedure as above
3. Append to the PRD footer:

   ```
   *UI Report:* `docs/ui-reports/{plan-name}-ui-report.md`
   ```

4. Return control to the pipeline

## Categories Checked

Each category uses keyword maps for detection. See [references/category-maps.md](references/category-maps.md) for the full synonym and red-flag lists.

### 1. Accessibility

Checks for WCAG level, screen reader support, keyboard navigation, focus management, and color contrast.

**PASS:** Specific WCAG level stated (e.g., "WCAG 2.1 AA"), or explicit screen reader / keyboard / focus coverage.

**FAIL:** Only generic terms like "accessible" or "a11y-friendly" with no specifics. No mention of accessibility at all.

**UNKNOWN:** Mentions "accessible" alongside some context (e.g., "accessible forms") but no explicit standard or method.

**Severity:** `blocking` if zero accessibility coverage in a user-facing feature; `warning` if partial coverage.

### 2. Responsive Design

Checks for breakpoints, mobile strategy, touch targets, and viewport adaptation.

**PASS:** Explicit breakpoint values, mobile-first or adaptive strategy, or specific device targets.

**FAIL:** Only "responsive" or "works on mobile" with no specifics. No mention of responsive behavior.

**UNKNOWN:** Mentions "mobile-friendly" or "adaptive" without concrete plans.

**Severity:** `blocking` for consumer-facing apps with no responsive plan; `warning` for internal tools.

### 3. Component Library Alignment

Checks for design system choice, component reuse strategy, and UI kit references.

**PASS:** Named design system (e.g., "Material UI", "shadcn/ui", internal design system) or explicit component reuse plan.

**FAIL:** No mention of components, design system, or UI kit. Vague "use consistent UI" without naming the source of consistency.

**UNKNOWN:** Mentions "components" or "reusable UI" without naming a library or system.

**Severity:** `warning` — rarely blocking unless the project already has a mandated design system.

### 4. Form Validation & Error States

Checks for input feedback, error messaging patterns, validation timing, and recovery flows.

**PASS:** Explicit validation strategy (client-side, server-side, or both), error message patterns, and field-level feedback described.

**FAIL:** Forms mentioned with no validation or error state coverage. Only "validate inputs" with no detail.

**UNKNOWN:** Mentions "form validation" without specifying when, how, or what error states look like.

**Severity:** `blocking` if the plan includes user-submitted data with zero validation coverage; `warning` otherwise.

### 5. Motion & Animation

Checks for transitions, loading states, skeleton screens, and performance budget for motion.

**PASS:** Explicit animation patterns (e.g., "fade transitions," "skeleton loaders") or a motion/performance budget.

**FAIL:** Mentions "smooth animations" or "polished feel" with no specifics. No mention of loading states.

**UNKNOWN:** Mentions "micro-interactions" or "transitions" without defining scope or performance constraints.

**Severity:** `warning` — motion gaps are rarely blocking but often cause retrofits.

### 6. Information Architecture / Navigation

Checks for wayfinding, page hierarchy, user flows, and navigation patterns.

**PASS:** Explicit navigation structure, user flow diagrams, or page hierarchy described.

**FAIL:** No navigation or IA coverage. Assumes users will "find their way" without structure.

**UNKNOWN:** Mentions "intuitive navigation" or "clear hierarchy" without concrete structure.

**Severity:** `blocking` for multi-page or multi-step features with no IA coverage; `warning` for single-page features.

### 7. Content Strategy

Checks for empty states, loading copy, error messages, microcopy, and placeholder content.

**PASS:** Explicit empty-state designs, error message copy, loading text, or microcopy guidelines.

**FAIL:** No mention of empty, loading, or error copy. Assumes content is self-evident.

**UNKNOWN:** Mentions "good copy" or "user-friendly text" without examples or guidelines.

**Severity:** `warning` — content gaps are rarely blocking but degrade UX significantly.

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

## Output Format

```markdown
# UI/UX Gap Report: {plan-name}

## Summary

| Category                       | Rating  | Severity |
| ------------------------------ | ------- | -------- |
| Accessibility                  | PASS    | —        |
| Responsive Design              | FAIL    | blocking |
| Component Library Alignment    | UNKNOWN | warning  |
| Form Validation & Error States | PASS    | —        |
| Motion & Animation             | FAIL    | warning  |
| Information Architecture       | PASS    | —        |
| Content Strategy               | UNKNOWN | warning  |

## Findings

### Responsive Design — FAIL (blocking)

> "The app should be responsive."

Vague. No breakpoints, no mobile strategy, no touch target sizes.

### Motion & Animation — FAIL (warning)

> "Smooth transitions between pages."

No mention of loading states, skeleton screens, or performance budget.

## Recommendations

1. Define mobile breakpoints and touch target sizes.
2. Specify loading state patterns and a motion performance budget.
```

## Completion Protocol

After `validate` completes:

1. If any `blocking` findings exist, print:

   ```
   ⛔ UI/UX validation found {N} blocking issue(s).
   Address these before advancing to aet-validate-scope or implementation.
   ```

2. If only `warning` findings exist, print:

   ```
   ⚠ UI/UX validation found {N} warning(s).
   Review the gap report and decide whether to address before implementation.
   ```

3. If all categories pass, print:

   ```
   ✓ UI/UX coverage complete. No gaps found.
   ```

## Key Principles

- **Evaluative, not generative** — identifies gaps; does not write guidelines or pick frameworks
- **Keyword + pattern matching** — sufficient for v1; no YAML parsing required
- **Extensible categories** — new categories can be added by updating keyword arrays in `references/`
- **Agent-agnostic** — any coding agent can run the checklist against any markdown plan
- **Blocking vs warning** — only absence of accessibility or responsive design in user-facing features is blocking by default
