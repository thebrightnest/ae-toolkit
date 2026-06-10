# Retro: M1-T1 / M1-T2 — Missing CSS shipped to production

## What Happened

M1-T1 (Global MCP CRUD) and M1-T2 (Project-Scope MCP) were planned, implemented, reviewed, QA'd, security-audited, and merged without a single line of CSS for the renderer components. Both the Global MCP settings tab and the Project MCP tab rendered as unstyled inline text — form fields, server list rows, badges, and action buttons had zero layout, spacing, or visual styling. The feature was functionally complete on the backend but completely broken in the UI.

The CSS gap was only discovered during manual smoke testing after merge. It required two follow-up fix commits and a second PR.

## Root Cause

**The AI layer has no awareness that renderer components require CSS.**

Specifically:

1. **Plan template** (`.agents/templates/plan-template.md`) has no section for renderer/UI work. Tasks jump from "Add IPC handlers" to "Create renderer route" with no mention of styling.
2. **AGENTS.md** has no rule requiring CSS completeness. The "Code Style" section only covers naming conventions, not visual completeness.
3. **aet-review** has no "UI / CSS" review lens. The "Completeness" lens compares code against the plan, but since the plan never mentioned CSS, the review passed.
4. **aet-pipeline-implement** validation gates check lint, type-check, and tests — none of which catch missing CSS classes.
5. **The implement agent** (this session) followed the plan verbatim. The plan said "Create `mcp.tsx`" and the agent created the TSX file with `className` attributes. No step told the agent to verify those classes exist in a stylesheet.

## What Went Well

- Backend tests were comprehensive (44 tests covering CRUD, materialization, global-disable, import, ownership rules)
- DB schema and migrations were correct
- IPC handlers had proper input validation
- Security audit found no critical issues
- The fix was straightforward once identified

## What Could Be Better

- Any renderer feature with custom `className` attributes must have a corresponding CSS task in the plan
- The review process must verify that declared CSS classes are actually defined
- The pipeline's "Completeness" gate should include a UI rendering check, not just functional tests

## Action Items

| Action                                           | Owner | Due        |
| ------------------------------------------------ | ----- | ---------- |
| Update plan template with Renderer/UI section    | Agent | 2026-05-14 |
| Add CSS completeness rule to AGENTS.md           | Agent | 2026-05-14 |
| Add CSS styling guidance to renderer-patterns.md | Agent | 2026-05-14 |
| Record learning in `.agents/learnings.jsonl`     | Agent | 2026-05-14 |

## Rules Updated

- `.agents/templates/plan-template.md` — added "Renderer / UI" section
- `AGENTS.md` — added Critical Rule #7: Renderer CSS Completeness
- `.agents/reference/renderer-patterns.md` — added "CSS Styling Requirements" section

## Learning

**Key insight:** A feature is not "implemented" until its UI is visually complete. TypeScript compilation and unit tests are necessary but not sufficient for renderer work — the CSS layer is equally part of the feature contract. Plans must explicitly include styling tasks, and reviews must verify that every `className` has a matching CSS definition.
