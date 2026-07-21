# DESIGN.md Template

Use this template when generating `DESIGN.md` in Phase 4.

## Dual-Layer Structure

```markdown
---
version: alpha
name: <Project Name>
description: <One-sentence summary>
colors:
  primary: "#..."
  secondary: "#..."
  tertiary: "#..."
  neutral: "#..."
  on-primary: "#..."
  on-secondary: "#..."
  on-tertiary: "#..."
  error: "#..."
  warning: "#..."
  success: "#..."
typography:
  display:
    fontFamily: "..."
    fontSize: "..."
    fontWeight: ...
    lineHeight: ...
  heading:
    fontFamily: "..."
    fontSize: "..."
    fontWeight: ...
    lineHeight: ...
  body:
    fontFamily: "..."
    fontSize: "..."
    fontWeight: ...
    lineHeight: ...
  label:
    fontFamily: "..."
    fontSize: "..."
    fontWeight: ...
    lineHeight: ...
rounded:
  sm: 4px
  md: 8px
  lg: 12px
spacing:
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 32px
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    rounded: "{rounded.md}"
    padding: "{spacing.md}"
  button-primary-hover:
    backgroundColor: "{colors.secondary}"
    textColor: "{colors.on-secondary}"
  button-primary-active:
    backgroundColor: "{colors.tertiary}"
    textColor: "{colors.on-tertiary}"
  card:
    backgroundColor: "{colors.neutral}"
    rounded: "{rounded.lg}"
    padding: "{spacing.lg}"
  input:
    backgroundColor: "{colors.neutral}"
    textColor: "{colors.primary}"
    rounded: "{rounded.sm}"
    padding: "{spacing.md}"
  input-focus:
    backgroundColor: "{colors.neutral}"
    textColor: "{colors.primary}"
    rounded: "{rounded.sm}"
    padding: "{spacing.md}"
---

## Overview

> Memorable thing: [the one thing from Phase 1]

[2-3 sentences tying aesthetic direction to the memorable thing]

## Colors

[Human-readable rationale for each color choice. Reference tokens by name.]

## Typography

[Human-readable rationale for font choices and scale. Reference tokens by name.]

## Layout

[Grid system, density, max-width, breakpoints. Reference spacing tokens where relevant.]

## Elevation & Depth

[Shadows, layering, z-index philosophy. When to use depth vs. flat surfaces.]

## Shapes

[Border radius philosophy. When to use each rounded token. Relationship to overall aesthetic.]

## Components

[Usage guidance for each component token defined in frontmatter. Do not repeat raw values — reference tokens. Describe behavior, states, and when to use each variant.]

## Do's and Don'ts

[3-5 concrete design rules with examples. Tie each to the memorable thing.]
```

## Frontmatter Rules

- Always emit valid YAML. Quote all hex colors: `"#1A1C1E"`. Unquoted hex may be parsed as YAML comments.
- Use token references in components: `"{colors.primary}"`, `"{rounded.md}"`, `"{spacing.lg}"`.
- Never hardcode hex values inside component tokens; always reference a color token.
- Include `version: alpha` in frontmatter.
- Include `name` and optional `description`.
- Define at minimum: `colors`, `typography`, `rounded`, `spacing`, `components`.

## Body Rules

- Sections must follow canonical order: Overview → Colors → Typography → Layout → Elevation & Depth → Shapes → Components → Do's and Don'ts.
- Omit a section only if it is truly irrelevant to the product. Never reorder sections.
- The Overview must repeat the memorable thing and connect it to aesthetic direction.
- Colors and Typography sections must explain rationale, not just list values (values live in frontmatter).
