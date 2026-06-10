# PRD: Cross-Cutting Completeness Framework

## Overview

The AE Toolkit pipeline validates compilation, types, lint, and tests — but has
zero awareness of **domain-specific completeness gaps**. A feature can pass
every gate while being completely broken in its target domain. This PRD ships
Phase 1: a UI/CSS Completeness lens in `aet-review` that mechanically catches
undefined CSS classes, plus a documented Cross-Cutting Completeness framework
that skill authors can reuse for future domains (i18n, assets, flags, etc.).

## Goals

1. **Prevent renderer CSS gaps from reaching `main`.** When `aet-review` runs on
   a diff that touches renderer components, it mechanically verifies that every
   custom `className` value has a corresponding CSS definition.

2. **Establish a reusable pattern.** Document the Cross-Cutting Completeness
   framework so that adding a completeness check for a new domain (i18n, assets)
   does not require redesigning the wheel.

3. **Update the planning template.** Ensure `docs/plans/` created by the toolkit
   include a reminder to consider UI/styling completeness when renderer work is
   involved.

## Non-Goals

- **i18n completeness** — out of scope for this PRD. The framework will be
  designed to generalize to i18n, but no i18n lens or check ships now.

- **Asset / icon / feature-flag completeness** — out of scope. Listed as future
  applications of the framework.

- **Automated CSS generation** — out of scope. The toolkit checks for missing
  CSS; it does not generate CSS for you.

- **Visual regression testing infrastructure** — out of scope. Browser-based
  screenshot comparison is valuable but requires Playwright setup that not all
  projects have. This PRD focuses on static analysis.

## Target Users

- **Primary:** Toolkit users running `aet-review` before merge. They need the
  pipeline to catch completeness gaps without relying on manual smoke testing.

- **Secondary:** AE Toolkit skill authors. They need a documented pattern for
  adding completeness checks to new or existing skills.

## User Stories

- **As a** toolkit user implementing a renderer feature, **I want**
  `aet-review` to flag undefined CSS classes **so that** I don't merge broken
  UI that requires follow-up fix PRs.

- **As a** toolkit user planning a feature with UI work, **I want** the plan
  template to remind me to include CSS/styling tasks **so that** completeness
  gaps are planned for, not discovered after implementation.

- **As a** toolkit maintainer adding a completeness check for a new domain
  (e.g., i18n), **I want** a documented pattern and checklist **so that** I can
  implement it consistently without redesigning the abstraction.

## Acceptance Criteria

- [ ] `aet-review/SKILL.md` includes a **UI / CSS Completeness** review lens
      with a mechanical procedure: extract `className` values from new/modified
      renderer components, filter known global classes, verify each remaining
      custom class exists in the project's stylesheet directory.

- [ ] `.agents/templates/plan-template.md` includes a **Renderer / UI Tasks**
      subsection under Tasks with a checkbox for CSS style verification.

- [ ] `docs/CONVENTIONS.md` (or a new `docs/adr/`) documents the
      **Cross-Cutting Completeness** framework: definition, when to apply,
      pattern template, and examples of domains it generalizes to.

- [ ] `aet-implement/SKILL.md` validation strategy mentions visual/CSS
      verification as part of self-validation when renderer work is involved.

- [ ] All changes pass `make validate` (lint, format-check, skill structure).

## Technical Notes

- The CSS completeness check is **static analysis**, not runtime. It compares
  `className` strings in TSX/JSX files against CSS/SCSS/Less class definitions.

- The check should be **project-agnostic**: it works whether the project uses
  CSS modules, SCSS, Less, or plain CSS. The agent inspects the actual
  stylesheet files in `src/renderer/styles/` (or equivalent).

- Known global classes (e.g., `btn`, `icon-btn`, `spin`, `container`) should be
  filterable so the lens does not flag framework-provided classes.

- The framework pattern should be **skill-agnostic**: any skill (plan,
  implement, review, QA) can adopt a completeness check by following the
  documented template.

## Architecture Decisions

- **Static analysis over browser testing:** Browser tests (Playwright) catch
  visual issues but are slow, optional, and not universally configured. Static
  className-to-CSS verification is fast, mechanical, and requires no extra
  infrastructure.

- **Review lens over pipeline gate:** Adding a new hard gate to
  `aet-pipeline-implement` adds friction to every pipeline run. The review lens
  is the right layer because review is _already_ a mandatory human-judgment
  stop, and completeness checks fit naturally alongside other review lenses.

- **Pattern-first over framework-first:** The framework is extracted from a
  proven implementation (CSS lens), not designed upfront. This avoids
  architecture astronautics and ensures the abstraction is grounded in reality.

## Open Questions

1. Should the CSS lens attempt to resolve CSS module imports (e.g.
   `import styles from './Component.module.css'`) or only global stylesheet
   references? **Tentative:** Start with global stylesheet references only;
   CSS module resolution adds significant complexity and may be addressed in a
   follow-up.

2. Should `aet-qa`'s Exhaustive tier also mention CSS completeness, or is the
   review lens sufficient? **Tentative:** Mention it in `aet-qa` as a note
   ("if Playwright is configured, visual regression may catch CSS gaps that
   static analysis misses"), but do not add a new QA gate.

3. Where does the framework documentation live? `docs/CONVENTIONS.md` or a new
   ADR? **Tentative:** A new ADR in `docs/adr/` because this is a structural
   pattern addition to the toolkit, not a coding convention.

## Risks

| Risk                                                                | Likelihood | Impact | Mitigation                                                                                      |
| ------------------------------------------------------------------- | ---------- | ------ | ----------------------------------------------------------------------------------------------- |
| CSS lens produces false positives (flags legitimate global classes) | Medium     | Low    | Maintain a filter list of known global classes; agent can adjust per-project.                   |
| Framework doc is too abstract to be actionable                      | Medium     | Medium | Ground the framework in the concrete CSS lens implementation; include copy-pasteable template.  |
| Scope creep to i18n/assets mid-implementation                       | High       | Medium | Explicitly list i18n/assets as non-goals in PRD; reference this PRD if scope creep is proposed. |
| Review lens adds friction and gets ignored                          | Low        | High   | Lens is mechanical (extract → filter → verify); agent does not need to reason, just execute.    |

---

_Stage: scope-validated_
_Next step: run `aet-pipeline-implement` (single task) or `aet-work` (multi-task queue)_
