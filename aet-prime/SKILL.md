---
name: aet-prime
description: Session context loading with git-as-memory and context discipline. Use at the start of every new coding session to ground the agent in the project's current state, goals, and conventions. Triggers on requests like "prime the session," "load context," or "what should we build next?"
---

# aet-prime

Context loading for agentic engineering. Every session starts with a clear picture of where we are and what comes next.

## When to Use

- Starting a new coding session
- Switching from planning to a new implementation session
- Returning to a project after time away
- Picking up a new ticket from the backlog

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

## Commands

### `prime`

Load project context before any coding. Keep it lean — protect the context window.

**Procedure:**

1. Read `AGENTS.md` at project root (always — this is the foundation)
2. If a ticket ID or plan.md is provided, read that specific `docs/plans/{ticket}-plan.md`
3. If no specific ticket, read the most recently modified PRD from `docs/prds/`
4. Read recent git commits (last 5–10) to understand current patterns and conventions
5. Check the current branch name for context
6. If working on a specific area, load the relevant `.agents/reference/` doc on demand
7. Summarize the loaded context in 5–10 bullets
8. Ask: "Based on the PRD/plan, what should we build next?"

**What NOT to load:**

- The full codebase (too much context)
- All reference docs at once (load on demand only)
- Old plans/PRDs unrelated to current work
- Test output or build artifacts

**Git-as-memory pattern:**

- Recent commits reveal: coding style, file organization patterns, testing conventions, commit message style
- Look for recurring patterns in commit messages (e.g., "feat:", "fix:", conventional commits)
- If a commit touched a file you're about to modify, read that commit's diff for guidance

## Key Principles

- **Context window is precious** — load only what's needed for the immediate task
- **Git is long-term memory** — recent commits guide what comes next better than any static doc
- **On-demand reference loading** — `.agents/reference/` docs are task-specific; don't preload them all
- **Prime before every session** — even a 30-second prime prevents hours of misalignment
