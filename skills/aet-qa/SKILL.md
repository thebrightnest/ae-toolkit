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

## Context

Run `aet context` and parse its JSON for session context (branch, repo
state, AGENTS.md, learnings, active plan/PRD stage); print the stage
banner it emits. Do not ask the user for this context manually.

## Commands

### `qa`

Run tiered automated validation.

**Procedure:**

1. **Consume the run handoff note.** If the orchestrator injected a handoff
   block into the stage prompt, treat its decisions and pre-existing failures
   as settled inputs — do not re-derive setup context or re-investigate them.
2. Determine tier (default: Standard if not specified):
   - **Quick** — critical paths only: core user flows, auth, payment (if applicable)
   - **Standard** — + medium priority flows: error handling, edge cases, data validation
   - **Exhaustive** — + all states/cosmetic: responsive layouts, loading states, empty states
3. Run automated test suite:
   - **Run the full test suite unconditionally.** `aet-qa` owns the complete validation surface; do not scope tests by impact, do not skip previously-passing tests, and do not reuse a cached result from `aet-implement`.
   - Unit tests
   - Integration tests
   - Type checking
   - Linting
4. **Coverage check:**
   - Run the test suite with coverage reporting (use the project's existing coverage tool)
   - Identify all source files that are new or modified in the current diff
   - When a diff introduces new source files, verify each has coverage > 0% — the completeness property for the test coverage domain
   - Any new file at 0% coverage is a QA failure at all tiers
   - Any modified file where all changed lines are uncovered is flagged for human review
5. **Call completeness check** (if diff touches API, bridge, preload, or handler files):
   - Grep renderer/client code for API call patterns using project conventions or heuristics (`*Api`, `*Bridge`, `invoke`, `fetch`, `rpc`, etc.)
   - List all unique external calls found in new or modified renderer code
   - Cross-reference each call with backend handlers, preload definitions, or API route files
   - Flag any orphaned call (no backend match) as a QA failure
6. If browser testing is available (Playwright configured):
   - Launch headless browser
   - Navigate through critical user flows
   - Fill forms, click buttons, verify state changes
   - Capture screenshots for visual regression
7. For any bug found:
   - Fix the bug in source
   - Generate a regression test that would have caught it
   - Commit the fix and test atomically
8. **Gap analysis.** If a test fails, compare the failing test path against the targeted tests recorded in the run handoff note (look for `[stage: implemented]` → `validation commands`). If the failing test was not run during `aet-implement`, record:
   - the missed test path
   - why it was outside the path-based floor (e.g., different directory, no matching name, shared fixture)
   Include this in the QA report and, if you append a handoff entry, in `--decision`.
9. **Stage-failure triage:** If any validation stage fails, gather the following evidence before retrying or escalating to a human. Append the triage block to the QA report; do not write it to the repository.
   - Failing command and full output
   - Files touched by the current diff
   - Last successful stage
   - Relevant environment variables (`AET_*`)
   - Whether the failure reproduces outside the orchestrator (run the same command manually in the worktree)
10. Produce a QA report:

    - Determine the task ID from the active plan filename or branch name
    - Write the report to `/tmp/aet-reports/{task-id}/qa-report.md`
    - Include:

      - pass/fail status per tier
      - bugs found and fixed
      - regression tests added
      - screenshot diffs (if browser mode used)
      - coverage delta
      - **Gap-analysis section:** targeted tests run by `aet-implement`, failing tests that were missed, and why the floor did not catch them
      - **Coverage section:** list files checked, their coverage %, and which (if any) failed the 0% gate
      - **Triage section:** stage-failure evidence, if any stage failed

    - Do NOT write `.qa-report.md` to the repository root

11. **Submit the stage verdict** per the writer contract below. It comes last
    because it reports the test counts from step 3 — there is nothing to submit
    before the suite has run. The stage is not complete until it is written.

**Evidence verdict (writer contract):**

Submit the stage verdict through the sanctioned writer — `aet gate submit` is the only writer of stage verdicts (G1). Do not hand-edit plan footers or queue state. A commit or a footer update is not a verdict; the orchestrator gate is fail-closed on the verdict file.

Use builder mode, which constructs the payload in code:

```bash
aet gate submit --stage qa --verdict <pass|fail> \
  --summary "<one line>" --from-pytest <report.json>
```

`--from-pytest` accepts a `pytest-json-report` file, or a scratch JSON object you write yourself with four keys — `test_command`, `tests_total`, `tests_passed`, `tests_failed`. Builder mode stamps every other schema field itself, so nothing here has to track the `qa` schema. It needs `AET_TASK_ID`, which orchestrated sessions already have.

Hand-authoring the full payload and passing `--evidence <payload-file>` still works, but you would be reproducing schema fields you cannot see — the cause of past rejected verdicts. Prefer builder mode; `docs/CLI.md` carries the generated option reference.

After submitting the verdict, if `AET_RUN_ID` is set, append the QA handoff
entry so later stages inherit the verdict and evidence path:

```bash
aet handoff append \
  --stage qa-complete \
  --decision "<QA decisions taken>" \
  --pre-existing-failure "<pre-existing failures observed>" \
  --validation-command "<commands run>" \
  --evidence-path "<path to the QA evidence payload>"
```

Do not hand-edit `.agents/runs/<run-id>/handoff.json`; use `aet handoff append`.

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

1. The plan.md footer will read:

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
