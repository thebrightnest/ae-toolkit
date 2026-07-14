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
- `ACTIVE_PRD_STAGE` — current `*Stage:` value from the most-recently-modified `docs/prds/*.md` footer (if exists)
- `ACTIVE_PLAN_STAGE` — current `*Stage:` value from the most-recently-modified `docs/plans/*.md` footer (if exists)

Use this context to ground all recommendations. Do not ask the user to provide it manually.

If a stage is found, print at the start of execution: `"📍 Current stage: {stage}."`

## Commands

### `qa`

Run tiered automated validation.

**Procedure:**

1. Determine tier (default: Standard if not specified):
   - **Quick** — critical paths only: core user flows, auth, payment (if applicable)
   - **Standard** — + medium priority flows: error handling, edge cases, data validation
   - **Exhaustive** — + all states/cosmetic: responsive layouts, loading states, empty states
2. Run automated test suite:
   - **Default to impact-scoped tests.** Use `git diff --name-only <pr-base>..HEAD` to identify changed files, map them to test files via project conventions or heuristics, and run only the tests that cover them. For Python use `pytest path/to/test.py`; for JS/TS use `vitest run path/to/test.ts` or `jest path/to/test.ts`.
   - **Full-suite fallback.** Run the complete test suite only when the diff touches any of the following. Otherwise, the impact-scoped test run is sufficient.
     - test harness
     - config
     - shared fixtures
     - dependency lockfiles
     - files imported by many tests
   - Unit tests
   - Integration tests
   - Type checking
   - Linting
3. **Coverage check:**
   - Run the test suite with coverage reporting (use the project's existing coverage tool)
   - Identify all source files that are new or modified in the current diff
   - When a diff introduces new source files, verify each has coverage > 0% — the completeness property for the test coverage domain
   - Any new file at 0% coverage is a QA failure at all tiers
   - Any modified file where all changed lines are uncovered is flagged for human review
4. **Call completeness check** (if diff touches API, bridge, preload, or handler files):
   - Grep renderer/client code for API call patterns using project conventions or heuristics (`*Api`, `*Bridge`, `invoke`, `fetch`, `rpc`, etc.)
   - List all unique external calls found in new or modified renderer code
   - Cross-reference each call with backend handlers, preload definitions, or API route files
   - Flag any orphaned call (no backend match) as a QA failure
5. If browser testing is available (Playwright configured):
   - Launch headless browser
   - Navigate through critical user flows
   - Fill forms, click buttons, verify state changes
   - Capture screenshots for visual regression
6. For any bug found:
   - Fix the bug in source
   - Generate a regression test that would have caught it
   - Commit the fix and test atomically
7. **Stage-failure triage:** If any validation stage fails, gather the following evidence before retrying or escalating to a human. Append the triage block to the QA report; do not write it to the repository.
   - Failing command and full output
   - Files touched by the current diff
   - Last successful stage
   - Relevant environment variables (`AET_*`)
   - Whether the failure reproduces outside the orchestrator (run the same command manually in the worktree)
8. Produce a QA report:
   - Determine the task ID from the active plan filename or branch name
   - Write the report to `/tmp/aet-reports/{task-id}/qa-report.md`
   - Include:
     - pass/fail status per tier
     - bugs found and fixed
     - regression tests added
     - screenshot diffs (if browser mode used)
     - coverage delta
     - **Coverage section:** list files checked, their coverage %, and which (if any) failed the 0% gate
     - **Triage section:** stage-failure evidence, if any stage failed
   - Do NOT write `.qa-report.md` to the repository root

**Evidence verdict (writer contract):**

Before updating the plan.md footer, write a JSON verdict record so the orchestrator can gate the stage machine-checkably. The footer remains a human breadcrumb only.

1. Build a verdict record matching the `qa` schema:

   ```json
   {
     "task_id": "{task-id}",
     "stage": "qa-complete",
     "skill": "aet-qa",
     "verdict": "pass" | "fail",
     "summary": "One-line outcome",
     "generated_at": "{ISO-8601 timestamp}",
     "test_command": "{command that was run}",
     "tests_total": 0,
     "tests_passed": 0,
     "tests_failed": 0
   }
   ```

2. Submit the verdict through the sanctioned writer — `aet gate submit` is the only writer of stage verdicts (G1). Write the payload JSON to a scratch file outside the tracked tree, then run:

   ```bash
   aet gate submit --stage qa --verdict <pass|fail> --evidence <payload-file>
   ```

   The CLI schema-validates the payload, resolves the destination (`$AET_EVIDENCE_PATH` → `$AET_EVIDENCE_PATH_QA` → `~/.aet/reports/{project-slug}/{task-id}/qa.json`), and exits non-zero with a named error on any failure. If `aet gate submit` is unavailable, fall back to writing equivalent JSON to the path from `resolve_verdict_path(task_id, "qa")` in `aet-work/lib/evidence.py`.

3. Only update the plan.md footer to `*Stage: qa-complete*` after `aet gate submit` exits 0.

**Browser tooling preference:**

- Prefer a compiled CLI browser tool (e.g., Playwright CLI) over MCP-based browser automation
- MCP browsers are often slower (2–3 seconds per action) and cause context bloat
- A compiled binary keeps browser automation fast, reliable, and out of the agent's context window

**Coverage tooling:**

- Use the coverage tool already configured for the project; do not hardcode a specific tool
- Language-appropriate defaults: `php artisan test --coverage` for Laravel, `vitest --coverage` or `jest --coverage` for JS/TS, `pytest --cov` for Python, `go test -cover` for Go
- If the project has no coverage tool configured, flag this as a setup gap rather than silently skipping the check

## Completion Protocol

After `qa` completes and all tiers pass:

1. Update the plan.md footer to:

   ```
   *Stage: qa-complete*
   *Next step: run `aet-review`*
   ```

2. Print: `"✓ Stage: qa-complete → Next step: run \`aet-review\`"`

## Key Principles

- **Automate QA to unlock parallelism** — manual QA is the bottleneck once planning + coding are handled
- **Every bug gets a regression test** — the system gets more robust over time
- **Tiered approach** — Quick for hotfixes, Standard for normal features, Exhaustive for major releases
- **Fail fast** — run unit tests first, integration second, browser last
