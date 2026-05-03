---
name: aet-ship
description: Pre-merge validation gate with bisectable commits, changelog generation, and PR creation. Use when code is reviewed and ready to merge. Fully non-interactive except for merge conflicts, test failures, and version bump decisions. Triggers on requests like "ship this," "prepare PR," or "merge ready."
---

# aet-ship

Pre-merge validation for agentic engineering. The final gate before code lands.

## When to Use

- Code has been implemented and reviewed
- You're ready to open or update a PR
- As the final step of the PIV loop

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

### `ship`

Run the pre-merge validation gate.

**Procedure:**
1. **Sync with main** — pull latest main, attempt trivial merge conflict resolution
2. **Run test suite** — unit, integration, type-check, lint. Must all pass.
3. **Coverage audit** — check coverage didn't drop below threshold. Flag if it did.
4. **Plan completion check** — verify all tasks in `docs/plans/{ticket}-plan.md` are addressed
5. **Run `aet-review`** — staff-level code review on the diff
6. **Run `aet-cso`** — security audit if the diff touches auth, data, API, or dependencies
7. **Split commits** — ensure each commit is bisectable (one logical change). Split if needed.
8. **Generate CHANGELOG** — add entry based on commit messages and plan.md summary
9. **Bump VERSION** — auto-bump patch. Stop for human decision on MINOR/MAJOR.
10. **Push and open PR** — push branch, create PR with description linking plan.md and PRD

**Stop conditions** (requires human intervention):
- Merge conflicts that can't be auto-resolved
- Test failures
- Coverage drop below threshold
- `aet-cso` fail (Critical/High findings)
- MINOR or MAJOR version bump needed

**Output:**
- Clean branch with bisectable commits
- PR with linked plan.md and PRD
- CHANGELOG entry
- Version bump

## Key Principles

- **Non-interactive by default** — the gate runs without human input until something is wrong
- **Composable** — invokes `aet-review` and `aet-cso` rather than duplicating their logic
- **Bisectable commits** — one logical change per commit, enforced at process level
- **Auto-generated artifacts** — CHANGELOG and VERSION bump are mechanical, not human work
- **Shipping is not the end** — post-deploy monitoring (`canary`) closes the loop
