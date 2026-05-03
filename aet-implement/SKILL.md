---
name: aet-implement
description: Fresh-session implementation from plan.md with self-validation. Use after a plan.md has been reviewed and approved. The agent writes code, runs validation, and compares against the plan. Triggers on requests like "implement this plan," "execute the plan," or "build this feature."
---

# aet-implement

Implementation execution for agentic engineering. Read the plan, write the code, validate the work.

## When to Use

- A `docs/plans/{ticket}-plan.md` exists and has been reviewed
- You are in a fresh session (context cleared from planning)
- The plan.md is the only context needed to execute

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

### `implement`

Execute a plan.md from start to finish with self-validation.

**Procedure:**
1. Read the plan.md file specified by the user
2. Create a feature branch if not already on one
3. Execute tasks in the order specified in the plan
4. After each task, run the relevant validation from the plan's self-validation strategy
5. Compare implementation against the plan — flag any deviation
6. Commit with a message that references the ticket/plan
7. Summarize what was built, what validation passed, and any deviations

**Fresh session reminder:**
If this session still contains planning context, strongly recommend clearing it first:
> "⚠️ This appears to be the same session where planning occurred. For best results, open a fresh session and run `/implement docs/plans/{file}.md` with only the plan as context."

**Validation strategy (from plan.md):**
- Linting must pass
- Type checking must pass
- Unit tests must pass
- Integration tests must pass (if applicable)
- Manual verification steps must be checked

**Deviation handling:**
- If implementation diverges from the plan, stop and explain why
- Do not silently change the plan — either follow it or flag the need to replan
- Minor deviations (naming, organization) are OK if they improve consistency with existing code

## Key Principles

- **Plan.md is the sole input** — no additional context should be needed
- **Self-validate continuously** — don't write hundreds of lines before checking anything
- **TDD preferred** — write failing tests first, then make them pass, then refactor
- **Agent handles admin** — branching, committing, PR creation
- **Human handles review** — code review and manual testing are not optional
