# Examples for aet-validate-ui

## Example 1: Full PRD check (web app with gaps)

**Input:** A PRD for a customer dashboard with mixed coverage.

```markdown
# Customer Dashboard Redesign

## Overview

Rebuild the customer dashboard with modern UX.

## Accessibility

The dashboard will be accessible to all users.

## Responsive Design

Responsive layout for mobile and desktop.

## Component Library

Use the internal Acme Design System.

## Forms

All forms validate inputs before submission.

## Motion

Smooth animations for a polished feel.

## Navigation

Intuitive navigation between dashboard sections.

## Content

Good copy and user-friendly text throughout.
```

**Command:**

```
aet-validate-ui on docs/prds/customer-dashboard-prd.md
```

**Output:**

```
# UI/UX Gap Report: customer-dashboard-prd

## Summary

| Category                       | Rating  | Severity |
| ------------------------------ | ------- | -------- |
| Accessibility                  | FAIL    | blocking |
| Responsive Design              | FAIL    | blocking |
| Component Library Alignment    | PASS    | —        |
| Form Validation & Error States | FAIL    | blocking |
| Motion & Animation             | FAIL    | warning  |
| Information Architecture       | FAIL    | blocking |
| Content Strategy               | FAIL    | warning  |

## Findings

### Accessibility — FAIL (blocking)

> "The dashboard will be accessible to all users."

Vague. No WCAG level, no screen reader plan, no keyboard navigation strategy.

### Responsive Design — FAIL (blocking)

> "Responsive layout for mobile and desktop."

No breakpoints, no touch target sizes, no mobile-first vs. adaptive strategy.

### Form Validation & Error States — FAIL (blocking)

> "All forms validate inputs before submission."

No validation timing, no error message patterns, no recovery flow.

### Motion & Animation — FAIL (warning)

> "Smooth animations for a polished feel."

No animation types, no loading states, no performance budget.

### Information Architecture — FAIL (blocking)

> "Intuitive navigation between dashboard sections."

No navigation structure, user flows, or page hierarchy described.

### Content Strategy — FAIL (warning)

> "Good copy and user-friendly text throughout."

No empty states, loading copy, error messages, or microcopy guidelines.

## Recommendations

1. Specify WCAG 2.1 AA target and keyboard/screen-reader coverage.
2. Define breakpoints and touch target minimums.
3. Add validation timing (on-blur / on-submit) and error message patterns.
4. Describe navigation structure and user flows.
```

---

## Example 2: Plan check (API-only feature that skips UI validation)

**Input:** A plan for a backend API endpoint with no user interface.

```markdown
# Payment Webhook Handler

## Overview

Implement a Stripe webhook endpoint to process async payment events.

## Scope

- Receive `payment_intent.succeeded` and `payment_intent.payment_failed` events
- Update order status in the database
- Emit internal `PaymentProcessed` event to the message bus

## No UI

This is a backend API-only feature with no user interface.
```

**Command:**

```
aet-validate-ui on docs/plans/payment-webhook-plan.md
```

**Output:**

```
⏭ Skipping UI validation — PRD is marked as "no UI."
```

---

## Example 3: All-pass scenario (comprehensive PRD)

**Input:** A thoroughly specified PRD with explicit UI/UX coverage.

```markdown
# Checkout Flow Redesign

## Accessibility

- WCAG 2.1 AA compliance
- Full keyboard navigation with visible focus states
- Screen reader tested with NVDA and VoiceOver
- ARIA labels on all interactive elements
- Color contrast ratio 4.5:1 minimum

## Responsive Design

- Mobile-first: 320px, 768px, 1024px breakpoints
- Touch targets minimum 44×44px
- Fluid grid with CSS Grid and flexbox

## Component Library

- Acme Design System v3.2
- Reuse checkout components from the shared library
- Storybook documentation at /storybook

## Form Validation & Error States

- Real-time client-side validation on blur
- Server-side validation on submit
- Inline field errors with red border + helper text
- Error summary panel at top of form
- Recovery: clear field, retry button

## Motion & Animation

- Page transitions: 200ms fade
- Skeleton loaders for async content
- prefers-reduced-motion support
- Motion budget: max 300ms per transition

## Information Architecture

- Step indicator: Cart → Shipping → Payment → Confirmation
- Breadcrumb: Home > Cart > Checkout
- Primary nav collapses to hamburger on mobile
- Deep linking to each checkout step via URL

## Content Strategy

- Empty cart: "Your cart is empty. Start shopping →"
- Loading: "Securing your payment..."
- Error: "We couldn't process your card. Check details and try again."
- CTA buttons: "Pay {amount}", "Back to cart"
```

**Command:**

```
aet-validate-ui on docs/prds/checkout-redesign-prd.md
```

**Output:**

```
# UI/UX Gap Report: checkout-redesign-prd

## Summary

| Category                       | Rating | Severity |
| ------------------------------ | ------ | -------- |
| Accessibility                  | PASS   | —        |
| Responsive Design              | PASS   | —        |
| Component Library Alignment    | PASS   | —        |
| Form Validation & Error States | PASS   | —        |
| Motion & Animation             | PASS   | —        |
| Information Architecture       | PASS   | —        |
| Content Strategy               | PASS   | —        |

✓ UI/UX coverage complete. No gaps found.
```

---

## Example 4: Nothing-found scenario (plan has no UI mentions at all)

**Input:** A backend infrastructure plan with zero UI/UX references.

```markdown
# Database Migration Plan

## Overview

Migrate the orders table from PostgreSQL 13 to 15.

## Steps

1. Create read replica on PG 15
2. Run schema validation script
3. Switchover application connection strings
4. Decommission PG 13 instance

## Rollback

- Snapshot taken before migration
- Connection strings revertible within 5 minutes
```

**Command:**

```
aet-validate-ui on docs/plans/db-migration-plan.md
```

**Output:**

````
# UI/UX Gap Report: db-migration-plan

## Summary

| Category                       | Rating | Severity |
| ------------------------------ | ------ | -------- |
| Accessibility                  | FAIL   | blocking |
| Responsive Design              | FAIL   | blocking |
| Component Library Alignment    | FAIL   | warning  |
| Form Validation & Error States | FAIL   | blocking |
| Motion & Animation             | FAIL   | warning  |
| Information Architecture       | FAIL   | blocking |
| Content Strategy               | FAIL   | warning  |

## Findings

No UI/UX coverage detected in this plan. All categories are unaddressed.

If this is a user-facing feature, add UI/UX specifications before proceeding.
If this is intentionally non-interface work, add a "no UI" marker to skip validation.

## Recommendations

1. If this plan has a user-facing surface, add Accessibility, Responsive Design,
   and Information Architecture coverage.
2. If this is backend-only infrastructure, add the following to the plan:

   ```markdown
   ## No UI
   This is an infrastructure task with no user interface.
````

```

```
