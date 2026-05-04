# Design System: TaskFlow

> Memorable thing: "This is serious software for serious work. No fluff, no distractions."

## Aesthetic Direction

Clinical precision with warmth. Like a well-designed hospital, not a spaceship. Every element has a job. Nothing decorative exists without purpose. The UI recedes so the user's work takes center stage.

## Typography

### Font Stack

- **Display/Headings**: Space Grotesk, -apple-system, BlinkMacSystemFont, sans-serif
- **Body**: Inter, -apple-system, BlinkMacSystemFont, sans-serif
- **Mono**: JetBrains Mono, SF Mono, monospace

### Scale

| Token     | Size | Line Height | Weight | Usage                          |
| --------- | ---- | ----------- | ------ | ------------------------------ |
| text-xs   | 12px | 1.4         | 400    | Captions, metadata, timestamps |
| text-sm   | 14px | 1.5         | 400    | Secondary text, labels         |
| text-base | 16px | 1.6         | 400    | Body text, descriptions        |
| text-lg   | 20px | 1.4         | 500    | Lead paragraphs, subheadings   |
| text-xl   | 25px | 1.2         | 600    | Section headings               |
| text-2xl  | 31px | 1.1         | 600    | Page headings                  |
| text-3xl  | 39px | 1.1         | 700    | Hero headings                  |

## Color System

### Base

| Token         | Hex     | Usage                        | Contrast Ratio |
| ------------- | ------- | ---------------------------- | -------------- |
| bg            | #FFFFFF | Page background              | -              |
| surface       | #F8F9FA | Cards, panels, inputs        | -              |
| surface-hover | #F1F3F5 | Hover states                 | -              |
| text          | #1A1D21 | Primary text                 | 15.8:1         |
| text-muted    | #6B7280 | Secondary text, placeholders | 5.2:1          |
| border        | #E5E7EB | Dividers, outlines           | -              |

### Accent

| Token            | Hex     | Usage                             |
| ---------------- | ------- | --------------------------------- |
| accent           | #0F172A | Primary CTA, active states, links |
| accent-hover     | #1E293B | CTA hover                         |
| accent-secondary | #3B82F6 | Secondary emphasis, highlights    |

### Semantic

| Token   | Hex     | Usage                                  |
| ------- | ------- | -------------------------------------- |
| error   | #DC2626 | Validation errors, destructive actions |
| warning | #F59E0B | Caution states, pending                |
| success | #059669 | Confirmation, completion               |

## Layout & Spacing

### Grid

12-column grid with 24px gutters. Max content width: 1200px. Breakpoints: 640px, 768px, 1024px, 1280px.

### Spacing Scale

| Token   | Value | Usage                         |
| ------- | ----- | ----------------------------- |
| space-1 | 4px   | Tight padding, icon gaps      |
| space-2 | 8px   | Inline elements, tight groups |
| space-3 | 12px  | Button padding, form fields   |
| space-4 | 16px  | Card padding, section gaps    |
| space-5 | 24px  | Component separation          |
| space-6 | 32px  | Section separation            |
| space-7 | 48px  | Major section breaks          |
| space-8 | 64px  | Page-level spacing            |

## Motion & Animation

### Easing

| Name    | Curve                        | Usage                |
| ------- | ---------------------------- | -------------------- |
| default | cubic-bezier(0.4, 0, 0.2, 1) | Standard transitions |
| enter   | cubic-bezier(0, 0, 0.2, 1)   | Elements appearing   |
| exit    | cubic-bezier(0.4, 0, 1, 1)   | Elements leaving     |

### Durations

| Context           | Duration |
| ----------------- | -------- |
| Micro-interaction | 150ms    |
| Transition        | 200ms    |
| Page transition   | 300ms    |

### Principles

1. Motion implies hierarchy. Parent elements move slower than children.
2. Every animation answers a question: what changed and why?
3. No decorative motion. If it doesn't guide attention or confirm action, remove it.
4. Respect `prefers-reduced-motion`. All animations degrade to instant state changes.

## Component Patterns

### Button

**Primary:**

- Background: accent (#0F172A)
- Text: #FFFFFF
- Padding: space-3 (12px) vertical, space-4 (16px) horizontal
- Border radius: 6px
- Font weight: 500
- Hover: background shifts to accent-hover (#1E293B), 200ms default easing
- Active: scale(0.98), 150ms

**Secondary:**

- Background: transparent
- Border: 1px solid border (#E5E7EB)
- Text: text (#1A1D21)
- Hover: background surface-hover (#F1F3F5)

### Card

- Background: surface (#F8F9FA)
- Border radius: 8px
- Padding: space-4 (16px)
- Shadow: none (flat design)
- Hover: border color darkens to #D1D5DB, 200ms transition

### Input

- Height: 40px
- Background: surface (#F8F9FA)
- Border: 1px solid border (#E5E7EB)
- Border radius: 6px
- Padding: 0 space-3 (12px)
- Font: text-base (16px) Inter
- Focus: border accent-secondary (#3B82F6), ring 2px rgba(59, 130, 246, 0.2)
- Error: border error (#DC2626), ring 2px rgba(220, 38, 38, 0.2)

## Asset Guidelines

### Icons

- Style: Outlined, 1.5px stroke, 24px default size
- Source: Heroicons or Lucide
- Rules: No filled icons. No decorative icons. Every icon must have a functional purpose.

### Imagery

- No stock photos. No illustrations. This is a tool, not a brand story.
- If avatars are needed: initials in a circle with accent background.
- If empty states need visuals: simple geometric shapes, monochrome.

## Accessibility

### Color Contrast

- All text meets WCAG AA (4.5:1 minimum)
- Large text (18px+ bold, 24px+ normal) meets WCAG AA (3:1 minimum)
- Interactive elements have visible focus states

### Motion

- Respect `prefers-reduced-motion: reduce` — disable all transitions
- No auto-playing animations
- No parallax

### Focus

- Focus ring: 2px solid accent-secondary (#3B82F6)
- Focus ring offset: 2px
- All interactive elements must have visible focus states
