# Context Budget for aet-prime

## prime Command

- **Expected consumption:** 5–15k tokens
- **Strategy:** Load only what's needed. No full codebase scans.
- **Breakdown:**
  - AGENTS.md: 1–3k tokens
  - plan.md or PRD: 2–5k tokens
  - Recent commits (5–10): 1–3k tokens
  - On-demand reference: 1–3k tokens (only if relevant)

## What to Skip

- ❌ Full directory tree listings
- ❌ All test files (load only if the task is testing-related)
- ❌ Dependency lockfiles
- ❌ Build artifacts, node_modules, etc.
- ❌ Old plans and PRDs not related to current work

## Keeping Prime Lean

1. If AGENTS.md is >200 lines, the project has violated the context budget. Flag it.
2. If the plan.md is >100 lines, focus on the summary and task list sections.
3. If recent commits are verbose, read only the commit messages, not full diffs.
4. Use sub-agents for any exploration beyond "read these 3 files."

## Warning Signs

- Agent asks clarifying questions that were answered in the plan.md → plan wasn't loaded properly
- Agent proposes solutions that contradict existing patterns → recent commits weren't read
- Agent is unsure what to build next → PRD wasn't referenced

**Action:** Re-run prime with explicit file paths.
