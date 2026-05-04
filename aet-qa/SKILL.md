---
name: aet-qa
description: Automated QA with tiered validation. Runs the test suite, optionally tests critical user flows via headless browser, and generates regression tests for found bugs. Use before shipping to replace manual QA bottleneck. Triggers on requests like "run QA," "test this," or "validate before ship."
---

# aet-qa

Automated QA for agentic engineering. Replaces manual QA with agent-driven validation.

## When to Use

- Before shipping any feature
- After implementation but before review
- When manual QA is the bottleneck
- As part of the `aet-ship` gate

## Shared Preamble

Before executing any command in this skill, collect the following context:

- `BRANCH` — current git branch
- `REPO_STATE` — clean / dirty / merge-conflict
- `AGENTS_MD` — presence and last-modified date of AGENTS.md
- `LEARNINGS` — top-3 relevant entries from `.agents/learnings.jsonl` (if exists)
- `ACTIVE_PLAN` — any `docs/plans/*.md` modified in last 7 days
- `LAST_PIV` — date of last completed plan-implement-validate cycle (from git log if available)

Use this context to ground all recommendations. Do not ask the user to provide it manually.

## Commands

### `qa`

Run tiered automated validation.

**Procedure:**

1. Determine tier (default: Standard if not specified):
   - **Quick** — critical paths only: core user flows, auth, payment (if applicable)
   - **Standard** — + medium priority flows: error handling, edge cases, data validation
   - **Exhaustive** — + all states/cosmetic: responsive layouts, loading states, empty states
2. Run automated test suite:
   - Unit tests
   - Integration tests
   - Type checking
   - Linting
3. If browser testing is available (Playwright configured):
   - Launch headless browser
   - Navigate through critical user flows
   - Fill forms, click buttons, verify state changes
   - Capture screenshots for visual regression
4. For any bug found:
   - Fix the bug in source
   - Generate a regression test that would have caught it
   - Commit the fix and test atomically
5. Produce a QA report:
   - Pass/fail status per tier
   - Bugs found and fixed
   - Regression tests added
   - Screenshot diffs (if browser mode used)
   - Coverage delta

**Browser tooling preference:**

- Prefer a compiled CLI browser tool (e.g., Playwright CLI) over MCP-based browser automation
- MCP browsers are often slower (2–3 seconds per action) and cause context bloat
- A compiled binary keeps browser automation fast, reliable, and out of the agent's context window

## Key Principles

- **Automate QA to unlock parallelism** — manual QA is the bottleneck once planning + coding are handled
- **Every bug gets a regression test** — the system gets more robust over time
- **Tiered approach** — Quick for hotfixes, Standard for normal features, Exhaustive for major releases
- **Fail fast** — run unit tests first, integration second, browser last
