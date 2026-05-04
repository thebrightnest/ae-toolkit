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

Use this context to ground all recommendations. Do not ask the user to provide it manually.

## Commands

### `cso`

Scan the current branch diff for security issues.

**Procedure:**

1. Read the git diff for the current branch
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
8. Produce a markdown security report with:
   - Severity classification: Critical / High / Medium / Low / Info
   - Description of each finding
   - Recommended fix
   - Pass/fail gate recommendation

**Pass/fail gate:**

- **Pass** — no Critical or High findings; Medium findings have documented mitigations
- **Fail** — any Critical or High finding must be fixed before merge

## Key Principles

- **Diff-focused** — only review what changed, not the entire codebase
- **Severity-based** — not all findings are blockers; classify honestly
- **False positive handling** — document suppressions with justification (e.g., `# nosec`)
- **Composable** — `aet-ship` invokes `cso` automatically when relevant files change
- **No external infrastructure** — works with static analysis of the diff only
