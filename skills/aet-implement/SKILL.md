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

0. **Pre-flight size check:** Before the approval checkpoint, read the target `plan.md` and scan its task list. If any task contains `⚠️ ATOMIC OVERSIZED`:

   - **Refuse to start.** Print the oversized task(s).
   - If `AET_EXECUTION_MODE=unattended` (check via `env` or equivalent): **hard stop.** Print `⛔ Unattended mode cannot override ATOMIC OVERSIZED. Replan with smaller tasks.` and exit with a non-zero status so the orchestrator marks this task as failed.
   - Otherwise (interactive session): ask for explicit user confirmation (`--force` or interactive approval) to proceed despite the warning.
   - If confirmed, log the override with `aet learnings append --problem <...> --layer <...> --fix <...> --prevents <...>` and continue.
   - If not confirmed, stop and instruct the user to replan with smaller tasks.

1. **Approval checkpoint:** Before writing any code, confirm the implementation scope:

   - List every file you intend to modify or create
   - State the approximate magnitude: "~N files, ~M lines changed"

   If `AET_EXECUTION_MODE=unattended` (check via `env` or equivalent):

   - Print: `🤖 Unattended mode (AET_EXECUTION_MODE=unattended) — skipping interactive approval. Proceeding with: ~N files, ~M lines changed.`
   - Continue directly to step 2

   Otherwise (interactive session):

   - Ask: _"This will modify the files listed above. Approve to proceed?"_
   - **Hard gate:** Do not begin editing until the user explicitly confirms

2. **Pre-branch git hygiene check:**

   Before creating a feature branch, verify `main` is in a safe state:

   1. `git fetch origin`
   2. Check working tree: `git -C $(git rev-parse --show-toplevel) status --short`
      - If dirty: print warning with stash/commit options; **hard stop** unless user confirms
   3. Check unpushed commits: `git rev-list --count origin/main..main`
      - If > 0: print `"Local main is ahead of origin/main. Push first: git push origin main, or branch from origin/main: git checkout -b <branch> origin/main"`; **hard stop** unless user confirms
   4. Check unpulled commits: `git rev-list --count main..origin/main`
      - If > 0: print `"Local main is behind origin/main. Pull first: git pull origin main"`; **hard stop** unless user confirms

3. Read the plan.md file specified by the user
4. **Reconciliation checkpoint:** Before writing code, compare constraints and requirements stated in the plan's prose against the code blocks and file edits. If they disagree:
   - Stop and print the discrepancy
   - Do not silently follow the code block over the prose
   - Flag for human judgment or replanning
5. Create a feature branch if not already on one
6. Execute tasks in the order specified in the plan
7. After each task, run the relevant validation from the plan's self-validation strategy. **If validation fails, stop immediately, report the failing task and the failure, and do not start the next task until it passes.**
8. Compare implementation against the plan — flag any deviation
9. Commit with a message that references the ticket/plan
10. Summarize what was built, what validation passed, and any deviations

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
   **skipping step 5** (branch already created by the worktree setup).
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
- **Focused test runs while iterating:** when the project has a large test suite, run only the tests that cover files you are touching (`pytest path/to/test.py`, `vitest run path/to/test.ts`, etc.). Use the diff or the plan's task list to pick the relevant subset.
- **Full suite before final commit:** run the complete test suite at least once before committing, unless the plan explicitly says otherwise.
- Manual verification steps must be checked
- **Visual / CSS verification** — if the plan includes renderer/UI work, verify that all custom `className` values have corresponding CSS definitions before declaring implementation complete

**Deviation handling:**

- If implementation diverges from the plan, stop and explain why
- Do not silently change the plan — either follow it or flag the need to replan
- Minor deviations (naming, organization) are OK if they improve consistency with existing code

## Completion Protocol

After `implement` completes and all validation passes:

1. The plan.md footer will read:

   ```
   *Stage: implemented*
   *Next step: run `aet-qa`*
   ```

2. Print: `"✓ Stage: implemented → Next step: run \`aet-qa\`"`

## Key Principles

- **Plan.md is the sole input** — no additional context should be needed
- **Self-validate continuously** — don't write hundreds of lines before checking anything
- **TDD preferred** — write one failing test, make it pass, refactor. Repeat per behavior (vertical slices). Use `/tdd` for dedicated TDD guidance.
- **Agent handles admin** — branching, committing, PR creation
- **Human handles review** — code review and manual testing are not optional
