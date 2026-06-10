# UI Coverage Lens

UI/UX coverage validation for planning documents. Use this lens during `validate` when the plan or PRD describes any user-facing interface (web, mobile, CLI with interactive elements, or API with documented consumer UI).

## When to Apply

- The PRD or plan mentions UI components, pages, screens, or user flows
- The feature includes forms, navigation, or visual feedback
- The plan does NOT explicitly mark the feature as "no UI" (API-only, CLI-only, pure backend)

Skip this lens for infrastructure, DevOps, data pipeline, or backend-only work.

## Categories

For each category, ask the question against the source document. Rate the answer and surface gaps.

### 1. Accessibility

**Question:** Does the plan explicitly address how people with disabilities will use this interface?

**What to look for:**

- WCAG level claimed (AA, AAA) and how it is verified
- Screen reader support (ARIA labels, roles, alt text)
- Keyboard navigation paths and focus management
- Color contrast ratios or verification method
- Reduced motion support (`prefers-reduced-motion`)

**Red flags:** Standalone words like "accessible", "a11y-friendly", or "meets accessibility standards" without naming a standard or verification method.

### 2. Responsive Design

**Question:** Does the plan describe how the interface adapts across device sizes and input methods?

**What to look for:**

- Specific breakpoints or a mobile-first/desktop-first strategy
- Touch target sizes (minimum 44px–48px)
- Viewport or container query strategy
- Specific device targets (phone, tablet, desktop)

**Red flags:** "responsive" used alone, "works on mobile", "mobile-friendly", or "scales to any screen" without mechanism.

### 3. Component Library Alignment

**Question:** Does the plan state which design system or component library the UI builds on?

**What to look for:**

- Named library or internal design system
- Reusable components or design tokens referenced
- Storybook, Figma library, or component catalog linkage

**Red flags:** "consistent UI", "use components", or "standard design" without naming the source.

### 4. Form Validation & Error States

**Question:** Does the plan describe how invalid input is detected, displayed, and recovered from?

**What to look for:**

- Validation timing (real-time, on-blur, on-submit)
- Error message location (inline, summary, per-field)
- Success, error, and neutral states for inputs
- Recovery paths (retry, undo, clear)

**Red flags:** "validate inputs", "good error handling", or "forms are secure" without specifics on timing, location, or recovery.

### 5. Motion & Animation

**Question:** Does the plan describe transitions, loading states, and motion budgets?

**What to look for:**

- Loading state type (skeleton, spinner, progress bar)
- Page or element transition definitions
- Animation performance budget (target frame rate)
- Reduced motion support

**Red flags:** "smooth animations", "polished feel", or "delightful interactions" without type, scope, or performance constraints.

### 6. Information Architecture / Navigation

**Question:** Does the plan describe how users orient themselves and move through the feature?

**What to look for:**

- Navigation structure (menu, sidebar, breadcrumbs, tabs)
- User flow or journey description
- Page hierarchy or sitemap reference
- Deep linking and URL/routing strategy

**Red flags:** "intuitive navigation", "easy to find", or "clear hierarchy" without describing the structure or mechanism.

### 7. Content Strategy

**Question:** Does the plan account for all text the user sees, including empty and error states?

**What to look for:**

- Empty state copy and design
- Loading copy (not just spinners)
- Error message copy and tone guidelines
- Helper text, placeholder text, and CTA copy
- Content standards or tone-and-voice reference

**Red flags:** "good copy", "user-friendly text", or "clear messaging" without examples or guidelines.

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

## Reporting

Present findings as a concise per-category list:

- Category name, rating, and severity
- Specific quote from the source document (or "not mentioned")
- One-sentence explanation of the gap

Do not generate new UI guidelines or pick frameworks. This lens is evaluative, not generative.
