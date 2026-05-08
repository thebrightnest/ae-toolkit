# DESIGN.md Spec Reference

Condensed reference for the Google `design.md` format. Use this when generating or editing DESIGN.md files.

## File Structure

A DESIGN.md file has two layers:

1. **YAML front matter** — Machine-readable design tokens, delimited by `---` fences at the top of the file.
2. **Markdown body** — Human-readable design rationale organized into `##` sections.

The tokens are the normative values. The prose provides context for how to apply them.

## Token Schema

```yaml
version: <string> # optional, current: "alpha"
name: <string>
description: <string> # optional
colors:
  <token-name>: <Color>
typography:
  <token-name>: <Typography>
rounded:
  <scale-level>: <Dimension>
spacing:
  <scale-level>: <Dimension | number>
components:
  <component-name>:
    <token-name>: <string | token reference>
```

## Token Types

| Type            | Format                                                                                                            | Example                  |
| --------------- | ----------------------------------------------------------------------------------------------------------------- | ------------------------ |
| Color           | `#` + hex (sRGB)                                                                                                  | `"#1A1C1E"`              |
| Dimension       | number + unit (`px`, `em`, `rem`)                                                                                 | `48px`, `-0.02em`        |
| Token Reference | `{path.to.token}`                                                                                                 | `{colors.primary}`       |
| Typography      | object with `fontFamily`, `fontSize`, `fontWeight`, `lineHeight`, `letterSpacing`, `fontFeature`, `fontVariation` | See examples in SKILL.md |

## Typography Object

```yaml
typography:
  heading-lg:
    fontFamily: "Space Grotesk"
    fontSize: "2rem"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "-0.02em"
```

Valid keys: `fontFamily`, `fontSize`, `fontWeight`, `lineHeight`, `letterSpacing`, `fontFeature`, `fontVariation`.

## Section Order

Sections use `##` headings. They can be omitted, but those present must appear in this order:

| #   | Section           | Aliases          |
| --- | ----------------- | ---------------- |
| 1   | Overview          | Brand & Style    |
| 2   | Colors            |                  |
| 3   | Typography        |                  |
| 4   | Layout            | Layout & Spacing |
| 5   | Elevation & Depth | Elevation        |
| 6   | Shapes            |                  |
| 7   | Components        |                  |
| 8   | Do's and Don'ts   |                  |

## Component Tokens

Components map a name to a group of sub-token properties:

```yaml
components:
  button-primary:
    backgroundColor: "{colors.tertiary}"
    textColor: "{colors.on-tertiary}"
    rounded: "{rounded.sm}"
    padding: 12px
  button-primary-hover:
    backgroundColor: "{colors.tertiary-container}"
```

Valid component properties: `backgroundColor`, `textColor`, `typography`, `rounded`, `padding`, `size`, `height`, `width`.

Variants (hover, active, pressed) are expressed as separate component entries with a related key name.

## Token Reference Rules

- Always quote hex colors in YAML: `primary: "#1A1C1E"` (unquoted hex can be parsed as a comment by some YAML parsers).
- Use token references in components rather than repeating raw values.
- Token references use dot notation: `{colors.primary}`, `{typography.body.fontSize}`.

## Consumer Behavior for Unknown Content

| Scenario                      | Behavior                   |
| ----------------------------- | -------------------------- |
| Unknown section heading       | Preserve; do not error     |
| Unknown color token name      | Accept if value is valid   |
| Unknown typography token name | Accept as valid typography |
| Unknown component property    | Accept with warning        |
| Duplicate section heading     | Error; reject the file     |

## CLI Tooling

The `@google/design.md` package provides:

- `npx @google/design.md lint DESIGN.md` — validate structure, broken refs, contrast ratios, section order.
- `npx @google/design.md diff DESIGN.md DESIGN-v2.md` — token-level comparison.
- `npx @google/design.md export --format css-tailwind DESIGN.md` — Tailwind v4 `@theme` CSS block.
- `npx @google/design.md export --format dtcg DESIGN.md` — W3C Design Tokens Format Module JSON.

## Contrast Requirements

- Component `backgroundColor` / `textColor` pairs should meet WCAG AA (4.5:1 minimum).
- The Google linter checks this automatically.
