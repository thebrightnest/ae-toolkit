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
- `ACTIVE_PRD_STAGE` — current `*Stage:` value from the most-recently-modified `docs/prds/*.md` footer (if exists)
- `ACTIVE_PLAN_STAGE` — current `*Stage:` value from the most-recently-modified `docs/plans/*.md` footer (if exists)

Use this context to ground all recommendations. Do not ask the user to provide it manually.

If a stage is found, print at the start of execution: `"📍 Current stage: {stage}."`

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
>
> Note: entering a worktree does **not** clear the context window. If context is stale, start a new session first, then set up the worktree.

**Worktree mode** (use with `--worktree` flag, "in a worktree", or when invoked by aet-work):

Worktree mode puts each implementation on its own branch using standard git commands — no agent-specific tooling required.

1. Extract the ticket ID from the plan filename:
   - `docs/plans/FEAT-001-plan.md` → `feat-001`
   - Fall back to a lowercase-slugified version of the plan title
2. Ensure `.worktrees/` is in `.gitignore`; add the line if missing.
3. Note the absolute repo root path (you'll need it to return):

   ```bash
   REPO_ROOT=$(git rev-parse --show-toplevel)
   ```

4. Create and enter the worktree:

   ```bash
   git worktree add .worktrees/<ticket-id> -b <ticket-id>
   cd .worktrees/<ticket-id>
   ```

5. Execute the normal implement steps (above) from inside the worktree directory,
   **skipping step 2** (branch already created by the worktree setup).
6. Commit the work.
7. Return to the repo root:

   ```bash
   cd $REPO_ROOT
   ```

   The worktree and its branch persist automatically — no special teardown needed.

8. Report: worktree path (`.worktrees/<ticket-id>`), branch name, commit SHA. Suggest: `git worktree list` to see all active worktrees.

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

## Completion Protocol

After `implement` completes and all validation passes:

1. Update the plan.md footer to:

   ```
   *Stage: implemented*
   *Next step: run `aet-qa`*
   ```

2. Print: `"✓ Stage: implemented → Next step: run \`aet-qa\`"`

## Key Principles

- **Plan.md is the sole input** — no additional context should be needed
- **Self-validate continuously** — don't write hundreds of lines before checking anything
- **TDD preferred** — write failing tests first, then make them pass, then refactor. Use `/tdd` for dedicated TDD guidance.
- **Agent handles admin** — branching, committing, PR creation
- **Human handles review** — code review and manual testing are not optional
