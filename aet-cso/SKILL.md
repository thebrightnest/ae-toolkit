---
name: aet-cso
description: Diff-focused security audit. Scans the current branch diff for secrets, injection risks, auth bypass patterns, dependency CVEs, and LLM trust boundary violations. Use before any PR that touches auth, data models, API endpoints, or dependencies. Can be invoked manually or wired into aet-ship. Triggers on requests like "security review," "audit this code," or "check for vulnerabilities."
---

# aet-cso

Security audit for agentic engineering. Lightweight, diff-focused review — not a full penetration test.

## When to Use

- Before any PR touching authentication, authorization, or session management
- Before any PR modifying data models or database access
- Before any PR adding or changing API endpoints
- Before any PR updating dependencies
- As part of the `aet-ship` gate (auto-triggered if auth/data touched)

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

### `cso`

Scan the current branch diff for security issues.

**Procedure:**

1. Read the git diff for the current branch scoped to the PR base:
   - Determine the PR base: `origin/main` unless the branch was created from another branch, in which case use that parent branch.
   - Compute it with `git merge-base HEAD origin/main` or `git merge-base HEAD <parent-branch>`.
   - Review `git diff <base>..HEAD` (not `git diff` against the working tree).
   - **Noise filtering:** ignore changes to `.gitignore` and `AGENTS.md` unless the task explicitly touches them. Treat them as project-level noise, not security signal.
2. Check for secrets/credentials:
   - API keys, tokens, passwords in code or config files
   - Hardcoded database connection strings
   - Private keys or certificates
3. Check for injection risks:
   - SQL injection (unparameterized queries, string concatenation in SQL)
   - Command injection (unsanitized input passed to exec/shell)
   - NoSQL injection (unsanitized objects passed to query builders)
4. Check for unsafe evaluation:
   - `eval()`, `exec()`, `Function()` constructor usage
   - Deserialization of untrusted data
   - Dynamic code execution from user input
5. Check for auth bypass patterns:
   - Missing authentication on new endpoints
   - Client-side authorization checks (must be server-side)
   - Insecure direct object references
   - Weak session handling
6. Check for LLM trust boundary violations:
   - Unsanitized user input reaching prompt templates
   - Missing input validation before LLM calls
   - Prompt injection vulnerabilities
7. Check dependency changes:
   - New dependencies: are they maintained? any known issues?
   - Updated dependencies: check for known CVEs in the new version
8. Produce a markdown security report:
   - Determine the task ID from the active plan filename or branch name
   - Write the report to `/tmp/aet-reports/{task-id}/security-audit.md`
   - Include: severity classification (Critical / High / Medium / Low / Info), description of each finding, recommended fix, pass/fail gate recommendation
   - Do NOT write `.security-audit.md` or `.security-*.md` to the repository root

**Evidence verdict (writer contract):**

Before updating the plan.md footer, write a JSON verdict record so the orchestrator can gate the stage machine-checkably. The footer remains a human breadcrumb only.

1. Build a verdict record matching the `cso` schema:

   ```json
   {
     "task_id": "{task-id}",
     "stage": "secure",
     "skill": "aet-cso",
     "verdict": "pass" | "fail",
     "summary": "One-line outcome",
     "generated_at": "{ISO-8601 timestamp}",
     "findings": []
   }
   ```

2. Determine the output path with this precedence:
   1. `$AET_EVIDENCE_PATH` if set (single-stage sessions).
   2. `$AET_EVIDENCE_PATH_CSO` if set (group sessions publish one per stage).
   3. Default: `~/.aet/reports/{project-slug}/{task-id}/cso.json`.
      When `aet-work/lib` is importable, call `resolve_verdict_path(task_id, "cso")` from `aet-work/lib/evidence.py` — the canonical helper implementing this precedence. Never hand-compute `{project-slug}` from the worktree CWD.
3. Use `aet-work/lib/evidence.py` (`write_verdict`) when available; otherwise write equivalent JSON to the resolved path.
4. Only update the plan.md footer to `*Stage: secure*` after the verdict file is written.

**Pass/fail gate:**

- **Pass** — no Critical or High findings; Medium findings have documented mitigations
- **Fail** — any Critical or High finding must be fixed before merge

## Completion Protocol

After `cso` completes with pass status (no Critical or High findings):

1. Update the plan.md footer to:

   ```
   *Stage: secure*
   *Next step: run `aet-sync-docs`, then `aet-ship`*
   ```

2. Print: `"✓ Stage: secure → Next step: run \`aet-sync-docs\` (if plan diverged), then \`aet-ship\`"`
3. If `cso` FAILS (Critical or High finding): do NOT update stage. Print: `"⛔ Stage unchanged — fix Critical/High findings before advancing."`

## Key Principles

- **Diff-focused** — only review what changed, not the entire codebase
- **Severity-based** — not all findings are blockers; classify honestly
- **False positive handling** — document suppressions with justification (e.g., `# nosec`)
- **Composable** — `aet-ship` invokes `cso` automatically when relevant files change
- **No external infrastructure** — works with static analysis of the diff only
