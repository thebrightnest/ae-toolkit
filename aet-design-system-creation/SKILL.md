---
name: aet-design-system-creation
version: 1.0.0
description: |
  Create a complete design system for your project: aesthetic direction, typography,
  color palette, layout principles, spacing, and motion. Produces DESIGN.md as your
  project's design source of truth. Use after aet-plan (PRD exists) and before
  aet-validate-scope. Triggers on requests like "design system", "create DESIGN.md",
  "brand guidelines", or "visual design". Opinionated: proposes specific fonts,
  colors, and layouts. Expect pushback. This is a conversation, not a form.
triggers:
  - design system
  - create DESIGN.md
  - brand guidelines
  - visual design
  - design from scratch
---

# aet-design-system-creation

Create a complete design system for your project. This skill produces DESIGN.md as the source of truth for how your product looks and feels — before a single line of UI code is written.

Design that tries to be memorable for everything is memorable for nothing. This skill forces a single "memorable thing" and builds every decision around it.

## When to Use

- You have a PRD and need to define how the product looks and feels before building
- Starting a new project's UI with no existing design system or DESIGN.md
- Your existing DESIGN.md is stale and needs a refresh
- You want competitive design research for your product category

## Before You Start

If you have an **unvalidated idea** — no PRD, no product context — run `aet-discover` first, then `aet-plan`. This skill assumes the problem is real and the user is known.

## Shared Preamble

Before executing any command in this skill, collect the following context:

- `BRANCH` — current git branch
- `REPO_STATE` — clean / dirty / merge-conflict
- `AGENTS_MD` — presence and last-modified date of AGENTS.md
- `LEARNINGS` — top-3 relevant entries from `.agents/learnings.jsonl` (if exists)
- `ACTIVE_PLAN` — any `docs/plans/*.md` or `docs/prds/*.md` modified in last 7 days
- `LAST_PIV` — date of last completed plan-implement-validate cycle (from git log if available)

Use this context to ground all recommendations. Do not ask the user to provide it manually.

## Workflow

The skill flows through phases. The agent progresses through them naturally based on context and user input.

### Phase 0: Pre-checks

**Step 0.1 — Check for existing DESIGN.md:**

```bash
ls DESIGN.md design-system.md 2>/dev/null || echo "NO_DESIGN_FILE"
```

- If DESIGN.md exists: Read it. Ask the user: "You already have a design system. Want to **update** it, **start fresh**, or **cancel**?"
  - If update: Read the existing DESIGN.md and use it as context. Skip to Phase 3 with "review mode" context.
  - If start fresh: Continue with full workflow.
  - If cancel: Exit with status DONE.
- If no DESIGN.md: Continue.

**Step 0.2 — Gather product context from codebase:**

```bash
cat README.md 2>/dev/null | head -50
cat package.json 2>/dev/null | head -20
ls src/ app/ pages/ components/ 2>/dev/null | head -30
```

Use this to pre-fill the product context question in Phase 1.

**Step 0.3 — Check for PRD:**

```bash
ls docs/prds/*.md 2>/dev/null | head -5
```

- If PRD exists: Read the most recently modified one for product context.
- If no PRD: Soft gate. Say: "I don't see a PRD yet. Want me to run `/aet-plan` first, or should I work from what I can infer?" Proceed if user declines.

**Step 0.4 — Check for taste profile:**

```bash
cat docs/designs/taste-profile.json 2>/dev/null || echo "NO_TASTE_PROFILE"
```

- If exists: Read it. Summarize the strongest signals (top 3 approved per dimension). Include in design brief.
- If not: Continue without taste bias.

### Phase 1: Product Context

**Step 1.1 — The single question:**

Ask one AskUserQuestion that covers everything needed. Pre-fill what you inferred from the codebase.

Question format:

- Confirm what the product is, who it's for, what space/industry
- What project type: web app, dashboard, marketing site, editorial, internal tool, etc.
- "Want me to research what top products in your space are doing for design, or should I work from my design knowledge?"
- **Explicitly say:** "At any point you can just drop into chat and we'll talk through anything — this isn't a rigid form, it's a conversation."

If the README or PRD gives you enough context, pre-fill and confirm: "From what I can see, this is [X] for [Y] in the [Z] space. Sound right? And would you like me to research what's out there in this space, or should I work from what I know?"

**Step 1.2 — Memorable thing forcing question:**

Before moving on, ask: "What's the one thing you want someone to remember after they see this product for the first time?"

One sentence answer. Could be a feeling, a visual, a claim, or a posture. Write it down. Every subsequent design decision serves this memorable thing.

### Phase 2: Research (optional)

Only run if the user said yes to research in Phase 1.

**Step 2.1 — Identify competitors via WebSearch:**

Search for:

- "[product category] website design"
- "[product category] best websites 2025"
- "best [industry] web apps"

Find 5-10 products in the space.

**Step 2.2 — Synthesize findings:**

Present a three-layer synthesis:

**Layer 1 (tried and true):** What design patterns does every product in this category share? These are table stakes.

**Layer 2 (new and popular):** What are search results and current design discourse saying? What's trending?

**Layer 3 (first principles):** Given what we know about THIS product's users and positioning — is there a reason the conventional design approach is wrong? Where should we deliberately break from category norms?

**Eureka check:** If Layer 3 reveals a genuine design insight, name it: "EUREKA: Every [category] product does X because they assume [assumption]. But this product's users [evidence] — so we should do Y instead."

Present conversationally:

> "I looked at what's out there. Here's the landscape: they converge on [patterns]. Most of them feel [observation]. The opportunity to stand out is [gap]. Here's where I'd play it safe and where I'd take a risk..."

### Phase 3: The Complete Proposal

This is the soul of the skill. Propose EVERYTHING as one coherent package. Do not present a menu of options — propose a specific system and defend it.

**Before proposing, factor in:**

- The memorable thing from Phase 1
- Research findings from Phase 2 (if done)
- Taste profile signals (if present)
- Product type and audience

**Step 3.1 — Build the proposal:**

Propose a complete design system with these dimensions. Be specific. Name files, fonts, hex values, spacing values.

**Aesthetic Direction**
One sentence describing the mood, material, and energy. Example: "Clinical precision with warmth. Like a well-designed hospital, not a spaceship."

**Decoration Level**
How much visual noise? Options: minimal (form follows function), balanced (subtle texture and depth), expressive (bold shapes, strong personality). Pick one and justify it against the memorable thing.

**Layout Approach**
Composition-first, not component-first. Describe:

- Grid system (e.g., 12-column, 8pt baseline)
- First viewport treatment (poster vs. document)
- Density (airy vs. information-dense)
- Navigation pattern

**Typography Stack**
Specific font names, not generics. Reference `references/typography-guide.md` for pairing patterns. Propose:

- Display/heading font
- Body font
- Mono font (if applicable)
- Scale system (e.g., Major Third 1.25x)
- Line heights per level

Example: "Space Grotesk for headings (geometric, confident), Inter for body (legible, neutral), JetBrains Mono for code/data. Scale: Major Third starting at 16px."

**Color System**
Specific hex values. Propose:

- Background (primary surface)
- Surface (cards, panels)
- Primary text
- Muted text
- Accent (one dominant, one secondary)
- Border/divider
- Error, warning, success states

Use a tool or your knowledge to ensure WCAG AA contrast ratios. State the contrast ratios explicitly.

**Motion & Animation**
Purposeful motion, not decoration. Propose:

- Easing curves (e.g., cubic-bezier(0.4, 0, 0.2, 1))
- Durations (e.g., 150ms for micro-interactions, 300ms for transitions)
- Principles (e.g., "motion implies hierarchy. Parent elements move slower than children.")

**Step 3.2 — SAFE/RISK breakdown:**

Label each major choice:

- **SAFE**: Conventional, expected, low risk if wrong. Category standard.
- **RISK**: Bold, differentiated, high reward if right. Deliberate departure from norms.

Present 2-3 RISK choices maximum. Too many risks cancel each other out.

**Step 3.3 — Present and confirm:**

Present the complete proposal conversationally. Then use AskUserQuestion:

> Here's my proposal. Every choice serves the memorable thing: [memorable thing].
>
> AESTHETIC: [direction] — SAFE/RISK
> DECORATION: [level] — SAFE/RISK
> LAYOUT: [approach] — SAFE/RISK
> TYPOGRAPHY: [stack] — SAFE/RISK
> COLOR: [palette] — SAFE/RISK
> MOTION: [principles] — SAFE/RISK
>
> A) Looks good, generate DESIGN.md
> B) Let me adjust [specific aspect]
> C) Start over with a different direction

If B: Ask specifically what's wrong. Revise only that aspect. Keep everything else locked.

If taste profile contradicts the proposal (e.g., taste profile strongly prefers minimal but you're proposing expressive), flag it: "Your taste profile strongly prefers minimal. You're asking for expressive this time — I'll proceed, but want me to update the taste profile, or treat this as a one-off?"

### Phase 4: DESIGN.md Generation

Generate the structured DESIGN.md file only after the user has accepted the proposal.

**Procedure:**

Write DESIGN.md to project root with this exact structure:

```markdown
# Design System: [Project Name]

> Memorable thing: [the one thing from Phase 1]

## Aesthetic Direction

[One-sentence direction plus 2-3 sentences of rationale tied to the memorable thing]

## Typography

### Font Stack

- **Display/Headings**: [font name], [fallbacks]
- **Body**: [font name], [fallbacks]
- **Mono**: [font name], [fallbacks]

### Scale

| Token   | Size | Line Height | Weight | Usage              |
| ------- | ---- | ----------- | ------ | ------------------ |
| text-xs | 12px | 1.4         | 400    | Captions, metadata |
| ...     | ...  | ...         | ...    | ...                |

## Color System

### Base

| Token      | Hex  | Usage              | Contrast Ratio |
| ---------- | ---- | ------------------ | -------------- |
| bg         | #... | Page background    | -              |
| surface    | #... | Cards, panels      | -              |
| text       | #... | Primary text       | [ratio]:1      |
| text-muted | #... | Secondary text     | [ratio]:1      |
| border     | #... | Dividers, outlines | -              |

### Accent

| Token            | Hex  | Usage              |
| ---------------- | ---- | ------------------ |
| accent           | #... | Primary CTA, links |
| accent-secondary | #... | Secondary emphasis |

### Semantic

| Token   | Hex  | Usage               |
| ------- | ---- | ------------------- |
| error   | #... | Validation errors   |
| warning | #... | Caution states      |
| success | #... | Confirmation states |

## Layout & Spacing

### Grid

[Grid system description]

### Spacing Scale

| Token   | Value | Usage         |
| ------- | ----- | ------------- |
| space-1 | 4px   | Tight padding |
| ...     | ...   | ...           |

## Motion & Animation

### Easing

| Name    | Curve             | Usage                |
| ------- | ----------------- | -------------------- |
| default | cubic-bezier(...) | Standard transitions |
| enter   | cubic-bezier(...) | Elements appearing   |
| exit    | cubic-bezier(...) | Elements leaving     |

### Durations

| Context           | Duration |
| ----------------- | -------- |
| Micro-interaction | 150ms    |
| Transition        | 300ms    |
| Page transition   | 500ms    |

### Principles

[3-5 motion principles, each one sentence]

## Component Patterns

### Button

[Specific guidance: padding, border-radius, typography, states]

### Card

[Specific guidance: shadow, border, padding, hover state]

### Input

[Specific guidance: height, border, focus state, error state]

## Asset Guidelines

### Icons

[Icon style, size, stroke width, source recommendations]

### Imagery

[Photo style, illustration style, or abstract — be specific]

## Accessibility

### Color Contrast

[Minimum contrast ratios enforced]

### Motion

[Respect prefers-reduced-motion]

### Focus

[Focus ring style and behavior]
```

Write DESIGN.md using WriteFile. Do not present it in chat as a code block — write the actual file.

### Phase 5: Preview

Generate a self-contained HTML preview page so the user can see the design system applied to real elements.

**Procedure:**

1. Create `docs/designs/` if it doesn't exist
2. Generate `docs/designs/DESIGN-preview.html` using WriteFile
3. The HTML must be self-contained (inline CSS, no external dependencies except web font CDN links)
4. Include these sections in the preview:

**HTML Structure:**

```html
<!doctype html>
<html>
  <head>
    <title>[Project Name] — Design System Preview</title>
    <style>
      /* Inline all CSS. Use the exact values from the design system. */
    </style>
  </head>
  <body>
    <h1>Design System: [Project Name]</h1>
    <p class="memorable-thing">"[The memorable thing]"</p>

    <section>
      <h2>Typography</h2>
      <!-- Show each scale step with sample text -->
    </section>

    <section>
      <h2>Color Palette</h2>
      <!-- Show each color as a swatch with hex value -->
    </section>

    <section>
      <h2>Spacing Scale</h2>
      <!-- Show each spacing step as a visual bar -->
    </section>

    <section>
      <h2>Components</h2>
      <!-- Button, Card, Input styled with the design system -->
    </section>
  </body>
</html>
```

**Required Content:**

- **Typography section**: Show every size in the scale (xs through display) with real text. Label each with token name, size, line-height, weight.
- **Color section**: Show each color as a rectangle swatch (80px × 80px minimum). Label with token name and hex value. Show text on both light and dark backgrounds to demonstrate contrast.
- **Spacing section**: Show each spacing step as a horizontal bar with width = spacing value. Label with token name and pixel value.
- **Components section**: At minimum show:
  - Primary button (default, hover, active states)
  - Card with sample content
  - Text input (default, focus, error states)
  - Heading + paragraph combination

**CSS Rules:**

- Use the exact font names, hex values, spacing values, and easing curves from the design system
- Apply the actual easing curve to button hover transitions so the user feels the motion
- Make the page responsive (max-width container, padding on mobile)
- Keep it clean and minimal — the design system itself is the star, not the preview chrome

1. After writing the file, tell the user: "Preview generated at `docs/designs/DESIGN-preview.html`. Open it in your browser to see the design system applied."

If the user has a browse/screenshot tool available, offer to open it for them. Otherwise, they open it manually.

### Phase 6: Taste Profile Update

Update `docs/designs/taste-profile.json` with approvals and rejections from this session.

**Schema:**

```json
{
  "version": 1,
  "dimensions": {
    "fonts": { "approved": [], "rejected": [] },
    "colors": { "approved": [], "rejected": [] },
    "layouts": { "approved": [], "rejected": [] },
    "aesthetics": { "approved": [], "rejected": [] }
  },
  "sessions": []
}
```

Each entry: `{ "value": "...", "confidence": 0.8, "approved_count": 3, "rejected_count": 0, "last_seen": "2026-05-03" }`

**Procedure:**

1. Read existing taste profile if present
2. For each design dimension, record what the user approved and rejected
3. Update counts and confidence scores
4. Apply decay: `confidence *= 0.95 ^ (weeks_since_last_seen)`
5. Save updated profile to `docs/designs/taste-profile.json`
6. Log a brief summary: "Recorded N approvals, M rejections. Top signals: [fonts: X], [colors: Y]"

## Integration Points

This skill sits between `aet-plan` and `aet-validate-scope` in the AET workflow:

```
aet-discover → aet-plan → aet-design-system-creation → aet-validate-scope → aet-implement
```

**aet-plan (input):**

- Read `docs/prds/*.md` for product context, target users, and scope
- Use the PRD's user stories to ground design decisions in real behavior
- If no PRD exists, soft gate: recommend `/aet-plan` but proceed if user declines

**aet-validate-scope (output):**

- DESIGN.md becomes an input for scope validation
- `aet-validate-scope` checks whether the design system contradicts existing code or domain model
- If DESIGN.md proposes a color system but the codebase already has a conflicting theme, the validator flags it

**aet-implement (output):**

- The implementer references DESIGN.md for all visual decisions
- Fonts, colors, spacing, and component patterns come from DESIGN.md, not the agent's defaults
- If DESIGN.md and the implementer's assumptions conflict, the implementer follows DESIGN.md and flags the discrepancy

## Key Principles

- **Memorable thing first** — Every design decision serves the one thing the user wants remembered
- **Opinionated proposals** — Propose specific fonts, colors, layouts. Do not hedge. Users can push back
- **Research optional** — The skill works with or without competitive research
- **Project-local artifacts** — DESIGN.md, preview, and taste profile live in the repo, versioned with git
- **No external binaries** — Works with native agent capabilities only
