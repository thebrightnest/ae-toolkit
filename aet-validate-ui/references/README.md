# References for aet-validate-ui

This directory contains detailed reference material for the `aet-validate-ui` skill.

## Files

| File                    | Purpose                                                                       |
| ----------------------- | ----------------------------------------------------------------------------- |
| `category-maps.md`      | Keyword maps, pass/fail signals, red flags, and synonyms for all 7 categories |
| `README.md` (this file) | Category definitions, severity rubric, and pipeline integration notes         |

---

## Category Definitions

The `validate` command checks planning documents against seven UI/UX categories. Each category represents a common source of interface risk in software projects.

### 1. Accessibility

Coverage for users with disabilities: visual, motor, auditory, and cognitive. Includes WCAG conformance, screen reader support, keyboard navigation, focus management, and color contrast.

**Why it matters:** Accessibility gaps are the most expensive to retrofit. Fixing them after implementation typically costs 10× more than planning for them upfront.

**Blocking trigger:** Any user-facing feature with zero accessibility coverage.

### 2. Responsive Design

Coverage for multiple viewport sizes and input methods. Includes breakpoints, mobile strategy, touch targets, and viewport adaptation.

**Why it matters:** Mobile traffic dominates most consumer applications. A plan that assumes "desktop only" without explicit justification is a liability.

**Blocking trigger:** Consumer-facing application with no responsive plan.

### 3. Component Library Alignment

Coverage for design system choice and component reuse strategy. Includes named libraries, internal design systems, and UI kit references.

**Why it matters:** Inconsistent UI increases development time, maintenance burden, and user confusion. Knowing the source of components early prevents ad-hoc decisions during implementation.

**Blocking trigger:** Rarely blocking unless the project mandates a specific design system.

### 4. Form Validation & Error States

Coverage for input feedback, error messaging, validation timing, and recovery flows. Includes client-side, server-side, and real-time validation strategies.

**Why it matters:** Form errors are the #1 source of user frustration and support tickets. Plans that mention "forms" without validation coverage will ship broken user experiences.

**Blocking trigger:** User-submitted data with zero validation coverage.

### 5. Motion & Animation

Coverage for transitions, loading states, skeleton screens, and motion performance. Includes animation types, durations, and reduced-motion support.

**Why it matters:** Motion gaps don't block shipping, but they cause expensive retrofit sprints when stakeholders ask "why does this feel unfinished?"

**Blocking trigger:** None by default (warning only).

### 6. Information Architecture / Navigation

Coverage for wayfinding, page hierarchy, user flows, and navigation patterns. Includes menus, breadcrumbs, tabs, and deep linking.

**Why it matters:** Users cannot use features they cannot find. IA gaps manifest as "where do I go to do X?" questions during UAT.

**Blocking trigger:** Multi-page or multi-step feature with no IA coverage.

### 7. Content Strategy

Coverage for empty states, loading copy, error messages, microcopy, and placeholder content. Includes tone guidelines and content standards.

**Why it matters:** Engineers writing copy in the moment produces inconsistent, confusing interfaces. Content gaps degrade UX silently.

**Blocking trigger:** None by default (warning only).

---

## Red Flags and Ambiguous Language

Red flags are terms that sound specific but carry no real meaning. They warrant an `UNKNOWN` or `FAIL` rating depending on context.

| Category                 | Red Flag                        | Why it's problematic                    |
| ------------------------ | ------------------------------- | --------------------------------------- |
| Accessibility            | "accessible" (standalone)       | No standard, no method, no verification |
| Accessibility            | "a11y-friendly"                 | Jargon without specifics                |
| Accessibility            | "meets accessibility standards" | Which standard? WCAG? Section 508?      |
| Responsive Design        | "responsive" (standalone)       | No breakpoints, no strategy             |
| Responsive Design        | "works on mobile"               | Which devices? Which orientations?      |
| Responsive Design        | "scales to any screen"          | Impossible to verify                    |
| Component Library        | "consistent UI"                 | No source of consistency named          |
| Component Library        | "use components"                | Which components? From where?           |
| Form Validation          | "validate inputs"               | No timing, no method, no error pattern  |
| Form Validation          | "good error handling"           | Subjective, not actionable              |
| Motion                   | "smooth animations"             | No type, no scope, no budget            |
| Motion                   | "polished feel"                 | Cannot be verified or implemented       |
| Motion                   | "delightful interactions"       | No definition of delight                |
| Information Architecture | "intuitive navigation"          | Intuition varies by user                |
| Information Architecture | "easy to find"                  | No mechanism described                  |
| Information Architecture | "clear hierarchy"               | Hierarchy not described                 |
| Content Strategy         | "good copy"                     | No examples, no guidelines              |
| Content Strategy         | "user-friendly text"            | Subjective, not actionable              |
| Content Strategy         | "clear messaging"               | No message content provided             |

**Rule of thumb:** If an engineer cannot implement the requirement from the description alone, the language is ambiguous.

---

## Synonym Map

The skill treats these terms as equivalent during keyword detection. Context still matters — a synonym used vaguely remains a red flag.

| Concept                | Synonyms                                                  |
| ---------------------- | --------------------------------------------------------- |
| Screen reader          | screenreader, assistive technology, JAWS, NVDA, VoiceOver |
| Keyboard               | keystroke, tab navigation, keyboard accessible            |
| Contrast               | color contrast, contrast ratio, 4.5:1, 3:1                |
| Responsive             | adaptive, fluid, mobile-first (if context present)        |
| Mobile                 | smartphone, handheld, tablet, touch device                |
| Breakpoint             | media query, viewport threshold                           |
| Design system          | component library, UI kit, pattern library                |
| Storybook              | component catalog, component docs                         |
| Client-side validation | frontend validation, browser validation                   |
| Server-side validation | backend validation, API validation                        |
| Inline error           | field error, per-field feedback, form error               |
| Skeleton               | shimmer, placeholder loading, content loader              |
| Spinner                | loader, loading indicator, progress indicator             |
| Transition             | animation, page change effect                             |
| Navigation             | wayfinding, orienting, menu structure                     |
| User flow              | user journey, flow diagram, interaction flow              |
| Site map               | sitemap, page map, information hierarchy                  |
| Empty state            | zero state, blank slate, no-data state                    |
| Microcopy              | UI copy, interface text, label text                       |
| Helper text            | hint text, placeholder text, field guidance               |

For the complete per-category keyword lists, see [category-maps.md](category-maps.md).

---

## Severity Rubric

Every finding receives a severity of `blocking` or `warning`.

### blocking

The plan should not advance to scope validation or implementation without addressing this gap.

**Criteria:**

- Zero coverage in a category that is critical for the feature type
- User-facing feature with no accessibility plan
- Consumer-facing app with no responsive design plan
- Form-heavy feature with no validation strategy
- Multi-page feature with no navigation structure

### warning

Surface the gap for human decision. The plan may advance if the team consciously accepts the risk.

**Criteria:**

- Partial coverage or ambiguous language in a non-critical category
- Component library not named (unless mandated)
- Motion/animation not specified
- Content strategy not documented
- Single-page feature with thin IA coverage

---

## Integration Notes for aet-pipeline-plan

The `validate-pipeline` command is the integration point between `aet-validate-ui` and `aet-pipeline-plan`.

### Trigger Point

Run `validate-pipeline` after PRD creation and before `aet-validate-scope`. This ensures UI/UX gaps are surfaced before scope validation locks the plan.

### Pipeline Flow

```
aet-discover → aet-plan → aet-validate-ui → aet-validate-scope → implementation
                ↑                              ↓
              PRD created              Scope validated
```

### Behavior

1. `aet-pipeline-plan` passes the PRD path to `aet-validate-ui`
2. `aet-validate-ui` runs `validate` with default behavior
3. The gap report is saved to `docs/ui-reports/{plan-name}-ui-report.md`
4. The report path is appended to the PRD footer:

   ```markdown
   _UI Report:_ `docs/ui-reports/checkout-redesign-prd-ui-report.md`
   ```

5. Control returns to `aet-pipeline-plan`

### Hard Gate

If any `blocking` findings exist, `aet-pipeline-plan` should pause and surface the gap report to the user. Do not auto-advance to `aet-validate-scope` until blocking issues are resolved or explicitly overridden.

### Skip Conditions

If the PRD contains a "no UI" marker, `aet-validate-ui` skips validation and `aet-pipeline-plan` continues without pause. Valid skip markers include:

- "no UI"
- "no user interface"
- "API-only"
- "backend only"
- "infrastructure — no interface"
