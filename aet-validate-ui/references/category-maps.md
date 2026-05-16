# Category Keyword Maps

This reference defines the keyword maps, red flags, and synonym lists used by the `validate` command for each of the seven UI/UX categories.

## How Keyword Maps Work

For each category, the skill scans the source document for:

- **Pass signals** — explicit terms that indicate sufficient coverage
- **Fail signals** — vague terms or complete absence
- **Red flags** — language that sounds specific but carries no real meaning
- **Synonyms** — alternative terms that should be treated as equivalent to pass signals

The agent uses these maps as guidance, not as rigid regex rules. Context matters — a term that usually signals PASS may be used vaguely enough to warrant UNKNOWN.

---

## 1. Accessibility

### Pass signals

- WCAG 2.1 / WCAG 2.2 / Section 508
- Specific level: AA, AAA, A
- "screen reader", "screenreader", "JAWS", "NVDA", "VoiceOver"
- "keyboard navigation", "keyboard accessible", "tab order", "focus trap", "focus management"
- "ARIA", "aria-label", "aria-describedby", "role="
- "color contrast", "contrast ratio", "4.5:1", "3:1"
- "alt text", "alternative text", "image descriptions"
- "reduced motion", "prefers-reduced-motion"

### Red flags (vague)

- "accessible" (standalone)
- "a11y-friendly"
- "meets accessibility standards" (no standard named)
- "compliant" (no regulation named)

### Synonyms

- "screen reader" = "screenreader" = "assistive technology"
- "keyboard" = "keystroke" = "tab navigation"
- "contrast" = "color contrast" = "contrast ratio"

---

## 2. Responsive Design

### Pass signals

- Specific breakpoints: "320px", "768px", "1024px", "1440px"
- "mobile-first", "desktop-first", "adaptive design"
- "touch target", "44px", "48px" (minimum touch target sizes)
- "viewport", "media query", "@media"
- "fluid grid", "flexbox", "CSS Grid", "container queries"
- Specific device targets: "iPhone", "Android", "tablet", "desktop"

### Red flags (vague)

- "responsive" (standalone)
- "works on mobile"
- "mobile-friendly"
- "scales to any screen"

### Synonyms

- "responsive" = "adaptive" = "fluid" (but only if context is present)
- "mobile" = "smartphone" = "handheld"
- "breakpoint" = "media query"

---

## 3. Component Library Alignment

### Pass signals

- Named library: "Material UI", "MUI", "shadcn/ui", "Chakra UI", "Ant Design", "Bootstrap", "Tailwind UI"
- Internal design system name
- "component library", "UI kit", "design tokens"
- "reusable components", "component catalog", "Storybook"
- "Figma library", "design system integration"

### Red flags (vague)

- "consistent UI" (no source named)
- "use components" (no library or system named)
- "standard design" (no standard named)

### Synonyms

- "design system" = "component library" = "UI kit"
- "Storybook" = "component catalog" = "component docs"

---

## 4. Form Validation & Error States

### Pass signals

- "client-side validation", "server-side validation", "both client and server"
- "real-time validation", "on-blur validation", "on-submit validation"
- "error message", "field error", "inline error", "error summary"
- "validation rules", "required fields", "input constraints"
- "error state", "success state", "neutral state"
- "retry", "recover from error", "undo"

### Red flags (vague)

- "validate inputs" (no method or timing)
- "good error handling" (no specifics)
- "forms are secure" (not about validation)

### Synonyms

- "client-side" = "frontend validation" = "browser validation"
- "server-side" = "backend validation" = "API validation"
- "inline error" = "field error" = "per-field feedback"

---

## 5. Motion & Animation

### Pass signals

- "transition", "page transition", "fade", "slide", "scale"
- "loading state", "skeleton screen", "skeleton loader", "shimmer"
- "spinner", "progress bar", "loading indicator"
- "motion budget", "animation budget", "60fps"
- "prefers-reduced-motion", "reduced motion support"
- "duration", "easing", "cubic-bezier"

### Red flags (vague)

- "smooth animations" (no type or scope)
- "polished feel" (no animation specifics)
- "delightful interactions" (no specifics)

### Synonyms

- "skeleton" = "shimmer" = "placeholder loading"
- "spinner" = "loader" = "loading indicator"
- "transition" = "animation" (in context of page/element changes)

---

## 6. Information Architecture / Navigation

### Pass signals

- "navigation menu", "nav bar", "sidebar", "breadcrumb", "tabs"
- "user flow", "user journey", "flow diagram"
- "page hierarchy", "information hierarchy", "site map", "sitemap"
- "wayfinding", "orientation", "navigation pattern"
- "primary navigation", "secondary navigation", "footer links"
- "deep linking", "URL structure", "routing"

### Red flags (vague)

- "intuitive navigation" (no structure)
- "easy to find" (no mechanism)
- "clear hierarchy" (no hierarchy described)

### Synonyms

- "navigation" = "wayfinding" = "orienting"
- "user flow" = "user journey" = "flow diagram"
- "site map" = "sitemap" = "page map"

---

## 7. Content Strategy

### Pass signals

- "empty state", "empty screen", "zero state", "blank slate"
- "loading copy", "loading text", "loading message"
- "error message copy", "error copy", "microcopy"
- "placeholder text", "hint text", "helper text"
- "content guidelines", "tone and voice", "content standards"
- "CTA copy", "button text", "link text"

### Red flags (vague)

- "good copy" (no examples or guidelines)
- "user-friendly text" (no specifics)
- "clear messaging" (no message content)

### Synonyms

- "empty state" = "zero state" = "blank slate"
- "microcopy" = "UI copy" = "interface text"
- "helper text" = "hint text" = "placeholder text"

---

## Extending Categories

To add a new category:

1. Define pass signals, red flags, and synonyms
2. Add the category to the `validate` command procedure in `SKILL.md`
3. Document the keyword map in this file
4. Update the output format template if the new category changes report structure
