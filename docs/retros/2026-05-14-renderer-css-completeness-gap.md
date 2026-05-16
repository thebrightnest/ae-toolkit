---
date: 2026-05-14
ticket: M1-T1 / M1-T2 (Atelier project)
stage: post-ship
---

# Retro: Renderer CSS Completeness Gap

## What Happened

Two tickets (M1-T1 Global MCP CRUD, M1-T2 Project-Scope MCP) were planned,
implemented, QA'd, reviewed, security-audited, and merged to `main` without a
single line of CSS for their renderer components. Both features were
functionally complete on the backend but completely broken in the UI — form
fields, server list rows, badges, and buttons rendered as unstyled inline text.

The gap was only discovered during manual smoke testing after merge. Two
follow-up fix commits and a second PR were required.

## Why Every Check Missed It

| Gate                     | What it checked          | Why CSS slipped through                                                                    |
| ------------------------ | ------------------------ | ------------------------------------------------------------------------------------------ |
| `aet-plan`               | Plan template tasks      | No renderer/UI styling section in `.agents/templates/plan-template.md`                     |
| `aet-implement`          | Lint, type-check, tests  | TypeScript compiles fine with undefined `className` values                                 |
| `aet-qa` (Standard tier) | Unit + integration tests | No visual regression or CSS class existence checks                                         |
| `aet-review`             | Multi-lens diff review   | No "UI / CSS" review lens; "Completeness" compares against plan, which never mentioned CSS |
| `aet-cso`                | Security audit           | CSS gaps are not a security concern                                                        |

Every gate in the pipeline is optimized for **machine-verifiable correctness**
(types, lint, tests) but has zero coverage for **visual completeness** — a
category of bugs that compile cleanly and pass all tests while rendering
completely broken.

## Root Cause

The AE Toolkit skills have **no concept that renderer components require CSS**.
This is not a single-skill failure — it's a cross-cutting blind spot:

1. **Planning** never generates CSS tasks because the template has no slot for them.
2. **Implementation** never verifies className-to-CSS mappings because validation is limited to compile-time checks.
3. **QA** never tests visual output because the Standard tier defaults to unit/integration only.
4. **Review** never inspects CSS completeness because no review lens covers it.

The pipeline gave us **false confidence** at every stage.

## Broader Pattern: Invisible Dependencies

CSS classes are not the only string references that TypeScript cannot see. The
same failure mode applies to:

- **i18n keys** — referenced in code but missing from locale files
- **Icon names** — referenced but not present in the icon set
- **Image/asset paths** — resolve at build time, fail at runtime
- **Feature flags** — referenced but not defined in config

The toolkit lacks a general concept of **static asset completeness**: any string
reference to an external resource needs mechanical verification.

## Fixes to Apply

### Fix 1 — `.agents/templates/plan-template.md` (planning)

Add a **Renderer / UI** subsection under Tasks:

```markdown
### Renderer / UI Tasks (if applicable)

- [ ] Create/update renderer component(s)
- [ ] Add/update CSS styles for all custom `className` values
- [ ] Verify no unstyled `className` references remain
```

This prevents the issue at the source, but is a prompt-only fix — no enforcement.

### Fix 2 — `aet-review` SKILL.md (review lens)

Add **UI / CSS Completeness** as a new review lens:

> **UI / CSS Completeness** — For every new/modified renderer component, extract
> all `className` values. Filter out known global classes (`btn`, `icon-btn`,
> `spin`, etc.). Verify each remaining custom class exists in the project's
> stylesheet directory. Flag any undefined classes as **fix-now**.

This is the highest-leverage fix because:

- It is a **mandatory gate** (review is a hard stop)
- It catches the issue **regardless of plan quality**
- It turns an agent reasoning problem into a **mechanical check**

### Fix 3 — `aet-implement` SKILL.md (validation strategy)

Expand the validation strategy to include:

> - **Visual / CSS verification** — if the plan includes renderer/UI work, verify
>   that all custom `className` values have corresponding CSS definitions before
>   declaring implementation complete.

The implement agent is where the code is written. It should not be possible to
write `className="mcp-form-row"` without asking "does `.mcp-form-row` exist?"

### Fix 4 — `aet-qa` SKILL.md (Exhaustive tier)

Expand the Exhaustive tier description:

> - **Exhaustive** — + all states/cosmetic: responsive layouts, loading states,
>   empty states, **CSS class existence**, visual regression screenshots

And add a note under browser testing:

> If Playwright is configured, capture screenshots of new/modified UI components.
> Compare against baseline or flag for human review if no baseline exists.

## What Would Have Caught This

Any single Fix 2 or Fix 3 would have caught the CSS gap before merge. Fix 1
prevents the issue at the source but is not a gate. Fix 4 is a safety net but
requires Playwright to be configured.

## Layer to Fix

Multiple skills:

- `.agents/templates/plan-template.md`
- `aet-review/SKILL.md`
- `aet-implement/SKILL.md`
- `aet-qa/SKILL.md`

## Not Yet Applied

This retro documents the problem and proposed fixes. The skills have **not** been
updated. A human should review this retro and apply the changes.
