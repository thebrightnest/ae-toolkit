# Product Brief: Cross-Cutting Completeness Framework

## Problem

The AE Toolkit pipeline validates compilation, types, lint, and tests — but has
zero awareness of **domain-specific completeness gaps**. A feature can pass every
gate while being completely broken in its target domain.

Concrete example (M1-T1 / M1-T2, Atelier project):

- Renderer components shipped with `className` attributes referencing CSS classes
  that did not exist.
- TypeScript compiled successfully.
- All tests passed.
- Code review passed (no UI/CSS lens).
- Security audit passed.
- Feature merged to `main`.
- UI rendered as unstyled inline text. Two follow-up fix PRs required.

The gap was not a bug in the code — it was a **blind spot in the toolkit's
quality model**.

## Demand Evidence

- **Behavioral:** The reporter (toolkit user) experienced this pain directly.
  Two tickets shipped broken. Required manual smoke testing + follow-up PRs to
  recover.
- **Status quo:** Toolkit users currently rely on manual post-merge smoke
  testing to catch completeness gaps. No skill in the pipeline checks for
  undefined CSS classes, missing i18n keys, unresolvable asset paths, or
  undefined feature flags.
- **Pattern:** This is a general failure mode. The same blind spot applies to
  any string reference to an external resource that TypeScript cannot see:
  CSS classes, i18n keys, icon names, image paths, config flags.

## User

**Primary:** Toolkit users (developers using AE Toolkit skills to build
features). They need the pipeline to catch completeness gaps before merge.

**Secondary:** Skill authors maintaining the AE Toolkit. They need a pattern
for adding completeness checks without reinventing the wheel per skill.

## Wedge

**Phase 1 (this week):** Add a **UI/CSS Completeness** lens to `aet-review`.
Mechanical check: extract all `className` values from new renderer components,
filter known globals, verify each custom class exists in the project's
stylesheet. This is the narrowest, highest-leverage fix.

**Phase 2 (next):** Extract the pattern into a **Cross-Cutting Completeness**
framework — a reusable mental model and checklist that any skill can adopt:
"When a diff touches domain X, verify completeness property Y."

**Phase 3 (later):** Apply the framework to `aet-plan` (plan template),
`aet-implement` (validation strategy), and `aet-qa` (Exhaustive tier).

## Verdict

**BUILD** — Demand is proven (real pain, real recovery cost). Wedge is Phase 1
(CSS lens), which is narrow and shippable this week. The broader framework
emerges from proven patterns, not upfront design.

---

_Stage: brief-validated_
_Next step: run `aet-plan`_
