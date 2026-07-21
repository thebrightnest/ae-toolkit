---
version: alpha
name: TaskFlow
description: Design system for a productivity SaaS focused on serious work without distractions.
colors:
  primary: "#1A1D21"
  secondary: "#6B7280"
  tertiary: "#0F172A"
  neutral: "#F8F9FA"
  on-primary: "#FFFFFF"
  on-secondary: "#FFFFFF"
  on-tertiary: "#FFFFFF"
  error: "#DC2626"
  warning: "#F59E0B"
  success: "#059669"
typography:
  display:
    fontFamily: "Space Grotesk"
    fontSize: "2.5rem"
    fontWeight: 700
    lineHeight: 1.1
    letterSpacing: "-0.02em"
  heading:
    fontFamily: "Space Grotesk"
    fontSize: "1.5rem"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "-0.01em"
  body:
    fontFamily: "Inter"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.6
  label:
    fontFamily: "Inter"
    fontSize: "0.75rem"
    fontWeight: 500
    lineHeight: 1.4
    letterSpacing: "0.02em"
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
    backgroundColor: "{colors.tertiary}"
    textColor: "{colors.on-tertiary}"
  button-primary-active:
    backgroundColor: "{colors.secondary}"
    textColor: "{colors.on-secondary}"
  button-secondary:
    backgroundColor: "{colors.neutral}"
    textColor: "{colors.primary}"
    rounded: "{rounded.md}"
    padding: "{spacing.md}"
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
  input-error:
    backgroundColor: "{colors.neutral}"
    textColor: "{colors.error}"
    rounded: "{rounded.sm}"
    padding: "{spacing.md}"
---

## Overview

> Memorable thing: "This is serious software for serious work. No fluff, no distractions."

Clinical precision with warmth. Like a well-designed hospital, not a spaceship. Every element has a job. Nothing decorative exists without purpose. The UI recedes so the user's work takes center stage.

## Colors

The palette is rooted in high-contrast neutrals and a single dark accent.

- **Primary (#1A1D21)** is deep ink for headlines, buttons, and core UI chrome. It anchors the "serious work" feeling.
- **Secondary (#6B7280)** is a sophisticated slate for borders, captions, and metadata. It creates hierarchy without competing for attention.
- **Tertiary (#0F172A)** is an even deeper ink reserved for hover states and emphasis. It adds depth to the primary layer.
- **Neutral (#F8F9FA)** is a warm off-white foundation. Softer than pure white, it reduces eye strain during long sessions.
- **Error, Warning, Success** follow conventional semantic meanings so users intuit meaning without learning a new language.

## Typography

Space Grotesk provides geometric confidence for headings. Its slightly quirky letterforms prevent the UI from feeling generic or corporate. Inter handles body text with neutral legibility at small sizes. The combination feels engineered but not cold.

The scale uses a Major Third ratio (1.25x), which produces compact but readable steps ideal for dense dashboards. Line heights are generous for body (1.6) and tight for display (1.1) to maximize information density without sacrificing readability.

## Layout

12-column grid with 24px gutters. Max content width: 1200px. Breakpoints: 640px, 768px, 1024px, 1280px. Density is high — this is a tool people use for hours, not a billboard they glance at.

## Elevation & Depth

Flat by default. Depth is earned, not given. Cards sit on the neutral surface with a 1px border (not a shadow) to define boundaries. Shadows appear only on hover for interactive cards, and they are subtle (0 1px 3px rgba(0,0,0,0.08)). No floating panels, no glassmorphism.

## Shapes

Corners are intentionally restrained. Small radius (4px) for inputs and buttons keeps them precise. Large radius (12px) for cards softens the grid without feeling playful. The rule: interactive elements are sharper; containers are softer.

## Components

**Button Primary** — `{colors.primary}` background with `{colors.on-primary}` text. Used for the single most important action on any screen. Hover shifts to `{colors.tertiary}` for depth. Active shifts to `{colors.secondary}` as a pressed state.

**Button Secondary** — `{colors.neutral}` background with `{colors.primary}` text. For secondary actions that still need emphasis. No hover state token is defined; rely on a subtle background darkening.

**Card** — `{colors.neutral}` background, `{rounded.lg}` corners, `{spacing.lg}` padding. The workhorse container. No shadow at rest; border-only.

**Input** — `{colors.neutral}` background with `{rounded.sm}` corners. Focus state is identical in structure but should receive a 2px outline in `{colors.primary}` via the consuming framework. Error state swaps text color to `{colors.error}`.

## Do's and Don'ts

- **Do** use generous whitespace between sections. Dense does not mean cramped.
- **Don't** introduce additional accent colors. The palette is intentionally limited.
- **Do** prefer border over shadow for elevation. Shadows are reserved for hover feedback.
- **Don't** use display typography for body text. The tight line height will break readability.
- **Do** respect `prefers-reduced-motion`. All transitions should be instant for users who request it.
