---
name: aet-prime
description: Session context loading and intake triage. Use at the start of every new coding session to classify incoming work, load project context, and route to the correct skill and pipeline. Triggers on requests like "prime the session," "load context," "what should we build next?", or any new task.
---

# aet-prime

Triage front door for agentic engineering. Every session starts with classification — then context loading — then routing to the right pipeline.

## When to Use

- Starting a new coding session
- Switching from planning to a new implementation session
- Returning to a project after time away
- Picking up a new ticket from the backlog
- Any time a new request arrives that needs routing

## Context

Run `aet context` and parse its JSON for session context (branch, repo
state, AGENTS.md, learnings, active plan/PRD stage); print the stage
banner it emits. Do not ask the user for this context manually.

## Commands

### `prime`

Load project context and classify the incoming request before any coding.

**Procedure:**

#### Step 0 — Load context

1. Read `AGENTS.md` at project root (always — this is the foundation)
2. If a ticket ID or plan.md is provided, read that specific `docs/plans/{ticket}-plan.md`
3. If no specific ticket, read the most recently modified PRD from `docs/prds/`
4. Read recent git commits (last 5–10) to understand current patterns and conventions
5. Check the current branch name for context
6. If working on a specific area, load the relevant `.agents/reference/` doc on demand

#### Step 1 — Intake classification

Ask the user (or infer from the request):

1. **"Does this touch auth, sessions, permissions, passwords, data models, migrations, infrastructure, or bump a dependency by major/minor version?"**
   - If **yes** → class = **critical**
2. **"Is this a reproducible misbehavior of existing code (bug, crash, error, unexpected behavior)?"**
   - If **yes** → route to `aet-bug-report`, not a planning pipeline
3. **"How many files and lines do you estimate this will touch?"**
   - ≤ 1 file / ≤ 5 lines → class = **trivial**
   - Everything else → class = **normal**

#### Step 2 — Route by work class

| Class        | Pipeline                                                                                     | Plans?           | QA Gate           |
| ------------ | -------------------------------------------------------------------------------------------- | ---------------- | ----------------- |
| **Trivial**  | Direct edit → `make validate` → `aet-ship`                                                   | No               | Diff review only  |
| **Normal**   | Quick plan (≤ 4 tasks) → `aet-implement` → auto checks → `aet-ship`                          | Yes, lightweight | Automated tests   |
| **Critical** | Full PRD → `aet-tdd` → `aet-implement` → `aet-qa` → `aet-review` → `aet-verify` → `aet-ship` | Yes, full        | Observed evidence |

**Routing rules:**

- **Trivial:** "fix typo", "change button color", "update copy" — skip `aet-plan`, `aet-tdd`, `aet-qa`, `aet-review`. Edit, validate, ship.
- **Normal:** "add email field", "new list endpoint", "simple modal" — use lightweight plan (≤ 4 tasks, no full PRD). Skip `aet-verify`.
- **Critical:** "add OAuth", "migrate database", "upgrade framework" — full ceremony. No shortcuts.
- **Bug:** Any reproducible defect → `aet-bug-report`. `aet-plan` and `aet-pipeline-plan` must reject bug reports.

#### Step 3 — Summarize and confirm

1. Summarize the loaded context in 5–10 bullets
2. State the assigned work class and pipeline
3. Ask: "Based on the PRD/plan, what should we build next?" or route to the appropriate skill

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

- **Classify first** — every request gets a work class before any skill runs
- **Context window is precious** — load only what's needed for the immediate task
- **Git is long-term memory** — recent commits guide what comes next better than any static doc
- **On-demand reference loading** — `.agents/reference/` docs are task-specific; don't preload them all
- **Prime before every session** — even a 30-second prime prevents hours of misalignment
- **Proportionality** — trivial work gets trivial ceremony; critical work gets full ceremony
