---
name: aet-verify
description: Conditional live verification with three modes — foundation smoke checks, feature evidence capture, and bug reproduction. Use when the work class is critical, when shipping auth/data/API changes, or when a bug report needs a verified reproduction. Triggers on requests like "verify this," "run smoke tests," "capture evidence," "reproduce this bug," or before merging critical work.
---

# aet-verify

Live verification that captures observed evidence of behavior in the running system. Complements automated tests — exercises real code paths instead of mocked boundaries.

## When to Use

- **Foundation mode** — at the start of a session, before critical work, or when the substrate feels unstable
- **Feature mode** — after implementing a critical task, before review; exercise the changed flow and capture proof it works
- **Reproduction mode** — when investigating a bug report; reproduce the issue and capture steps + evidence
- Skip entirely for trivial and normal work-class tasks

## Shared Preamble

Before executing any command in this skill, collect the following context:

- `BRANCH` — current git branch
- `REPO_STATE` — clean / dirty / merge-conflict
- `AGENTS_MD` — presence and last-modified date of AGENTS.md
- `LEARNINGS` — top-3 relevant entries from `.agents/learnings.jsonl` (if exists)
- `ACTIVE_PLAN` — any `docs/plans/*.md` modified in last 7 days
- `WORK_CLASS` — from the plan footer (`*Work class:`) or infer from task scope (trivial / normal / critical)
- `SMOKE_CMD` — the project's smoke command (`make smoke`, `npm run smoke`, etc.) or check `.agents/smoke/`
- `QA_REPORT_PATH` — `/tmp/aet-reports/{task-id}/qa-report.md` (standard aet-qa output location)
- `ACTIVE_PRD_STAGE` — current `*Stage:` value from the most-recently-modified `docs/prds/*.md` footer (if exists)
- `ACTIVE_PLAN_STAGE` — current `*Stage:` value from the most-recently-modified `docs/plans/*.md` footer (if exists)

Use this context to ground all recommendations. Do not ask the user to provide it manually.

If a work class is found, print at the start of execution: `"📍 Work class: {class} — running verification accordingly."`

## Commands

### `foundation`

Run substrate smoke checks to verify the system boots and core paths are healthy.

**When to run:**

- Once per coding session for any developer
- Before and after critical work
- When `make test` passes but the app "feels wrong"

**Procedure:**

1. Locate the smoke command:

   - Preferred: `make smoke` (project-level Makefile)
   - Fallback: `.agents/smoke/*.sh` scripts (run all executable files in this directory)
   - Fallback: `npm run smoke`, `pnpm smoke`, `yarn smoke`
   - If none exist, flag a setup gap and stop

2. Run the smoke command and capture **all** output (stdout + stderr)

3. Verify the following categories are covered (flag gaps):

   - **Boot** — the application starts without crash
   - **Auth** — login / session creation succeeds
   - **Primary CRUD** — at least one create, read, update, delete operation on a core entity
   - **Dev services** — database, cache, or message queue responds

4. Produce a smoke report:

   - Determine the task ID from the active plan filename or branch name
   - Write to `/tmp/aet-reports/{task-id}/smoke-report.md`
   - Include: pass/fail per category, raw output (or last 100 lines if verbose), gaps flagged
   - Do NOT commit the report to the repository

5. If any check fails:
   - Print the failing category and last error
   - Stop the pipeline — do not proceed with critical work on a broken substrate

### `feature`

Exercise the changed flow in the running system and capture observed evidence.

**When to run:**

- After implementing a critical work-class task
- Before `aet-review` or `aet-ship`
- Only for critical work; normal and trivial tasks skip this step

**Procedure:**

1. Identify the changed flow:

   - Read `ACTIVE_PLAN` tasks to understand what was built
   - Read the git diff to find modified source files
   - Determine the user-facing entry point (API endpoint, page route, CLI command, etc.)

2. Choose the verification tool based on project type and availability:

   - **API / backend change** — `curl` or HTTP client; capture response body and status code
   - **Web UI change** — headless browser (Playwright preferred) or manual screenshot
   - **CLI change** — run the command and capture stdout/stderr
   - **Library / module change** — write a small integration script that imports the module and exercises the public API; capture output

3. Exercise the flow at least once end-to-end. Do not mock first-party modules.

4. Capture evidence:

   - Save response bodies, screenshots, or terminal output to `/tmp/aet-reports/{task-id}/evidence/`
   - Use descriptive filenames: `{mode}-{timestamp}-{slug}.{ext}` (e.g. `feature-20260115-143022-login-200.json`)
   - Include a metadata header in text artifacts:

     ```
     ---
     mode: feature
     task: {task-id}
     tool: curl|playwright|cli
     timestamp: {ISO-8601}
     ---
     ```

5. Append to the QA report:

   - If `QA_REPORT_PATH` exists, append an Evidence section
   - If not, create the QA report at `/tmp/aet-reports/{task-id}/qa-report.md` with the evidence section
   - Include: what was exercised, what tool was used, pass/fail, path to saved artifact

6. If evidence capture fails (flow does not work, crashes, or returns unexpected result):
   - Treat as a bug — fix in source, add regression test, re-capture evidence
   - Do not proceed to review until evidence is clean

### `reproduction`

Reproduce a reported bug and capture the exact steps and observed behavior.

**When to run:**

- When a bug report lacks a verified reproduction
- Before writing a fix — confirm the bug exists and understand its surface area

**Procedure:**

1. Read the bug report and extract:

   - Expected behavior
   - Actual behavior
   - Steps to reproduce (if provided)
   - Environment details (version, OS, browser, etc.)

2. Follow the reported steps exactly. Do not skip "obvious" setup.

3. Capture evidence at each step:

   - Terminal output after each command
   - Screenshots after each UI interaction
   - HTTP request/response for API-related bugs

4. Produce a reproduction report:

   - Write to `/tmp/aet-reports/{task-id}/reproduction-{slug}.md`
   - Include: environment, exact steps, expected vs actual, evidence file references
   - If the bug **cannot** be reproduced, document what was tried and close the report with "Could not reproduce"

5. If reproduced successfully:
   - Hand off to `aet-bug-report` for root-cause analysis and fix
   - Include the reproduction report path in the bug report

## Evidence Capture Formats

| Work type    | Preferred tool          | Artifact format   | Metadata required             |
| ------------ | ----------------------- | ----------------- | ----------------------------- |
| API endpoint | `curl`                  | `.json` or `.txt` | status, headers, body snippet |
| Web page     | Playwright / screenshot | `.png`            | viewport, URL                 |
| CLI command  | Direct execution        | `.txt`            | command, exit code            |
| Integration  | Custom script           | `.txt` or `.json` | imports exercised, output     |

## Key Principles

- **Observed > Mocked** — capture the real system's behavior, not a test double's
- **Critical only** — normal and trivial tasks skip live verification to preserve velocity
- **Evidence is append-only** — never overwrite an evidence file; use timestamps
- **Tool-agnostic** — curl, CLI output, and screenshots are all valid; Playwright is optional
- **Fail the substrate, fail the pipeline** — a broken foundation blocks all downstream work

## Rules

- Never mock first-party modules during evidence capture
- Never commit `/tmp/aet-reports/` files to the repository
- Never skip foundation smoke before critical work
- Always include metadata headers in text evidence artifacts
- Always append feature-mode evidence to the QA report when one exists
