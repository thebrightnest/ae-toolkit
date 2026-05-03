---
name: aet-plan
description: PRD creation, "grill me" mode, story breakdown, and plan.md generation. Use when starting a new feature, sprint, or project. Prevents misalignment by building shared understanding before any code is written. Triggers on requests like "plan this feature," "create a PRD," "break this into tickets," or "help me design."
---

# aet-plan

Planning and alignment for agentic engineering. The #1 failure mode is starting implementation before shared understanding exists. This skill prevents that.

## When to Use

- Starting a new feature, sprint, or project
- You have an idea but no structured plan yet
- The agent built something different from what you imagined (go back to grill-me)
- Breaking a PRD into implementable tickets

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

### `grill-me`

The agent interviews the human relentlessly until a shared design concept exists. This is the single highest-leverage step in the entire workflow.

**Procedure:**
1. Ask the user to describe what they want to build (brain dump — no structure required)
2. Ask clarifying questions one at a time. Be relentless — walk down each branch of the design tree.
3. Use multiple-choice options when possible to speed up answers.
4. Continue until the agent is satisfied that a shared understanding exists (typically 20–100 questions).
5. Summarize the shared design concept for confirmation.

**Rules:**
- This is NOT plan mode. Do not produce artifacts yet. Build shared context first.
- Anti-sycophancy: never say "that's an interesting approach." Always take a position.
- The conversation history becomes a valuable asset — save it for reference.

### `create-prd`

Transform the grilled conversation into a structured Product Requirements Document.

**Procedure:**
1. Read the grill-me conversation history as input.
2. Use `.agents/templates/prd-template.md` as the structure guide.
3. Produce a PRD saved to `docs/prds/{feature-name}-prd.md`.
4. Include: executive summary, mission, target users, scope (in/out), user stories with acceptance criteria, technical notes, architecture decisions, open questions, risks.
5. **Explicitly list out-of-scope items** — crucial for defining "done."
6. Ask the user to review before proceeding. Do not auto-generate stories from an unreviewed PRD.

### `create-stories`

Break the PRD into vertically-sliced, independently implementable tickets.

**Procedure:**
1. Read the approved PRD from `docs/prds/`.
2. Create tickets as markdown files in `docs/plans/` or push via MCP if configured.
3. **Force vertical slices**: each ticket must cross all layers (schema + API + minimal UI), not horizontal layers (all DB → all API → all UI).
4. Define blocking relationships between tickets (directed acyclic graph).
5. Each ticket gets: title, user story, acceptance criteria, technical notes, estimated effort.
6. **Generate `.agents/work-queue.json`** from the tickets. This is the machine-readable queue that enables AFK loops.

**Vertical slice rule:**
- Bad (horizontal): "Create user table" → "Add user API" → "Build user profile page"
- Good (vertical): "User can register" (schema + endpoint + form) → "User can view profile" (query + page)

**Work queue generation:**
- The queue is built from `docs/plans/*.md` only (PRDs are metadata, not queue entries)
- Each task gets: `id`, `title`, `plan_file`, `status` (unblocked/blocked/done/failed), `blocks` (array of IDs), `blocked_by` (array of IDs)
- Tasks with no `blocked_by` entries start as `unblocked`
- Tasks with `blocked_by` entries start as `blocked`
- Save to `.agents/work-queue.json`
- The queue enables `aet-work` to pick the next task automatically

### `plan`

From a ticket/story, produce a structured `plan.md` for implementation.

**Procedure:**
1. Read the ticket and relevant PRD section.
2. Use `.agents/templates/plan-template.md` as the structure guide.
3. Produce `docs/plans/{ticket-id}-plan.md` containing:
   - Summary and user story
   - Locked-in architecture decisions (cannot change without re-planning)
   - Files to create and modify
   - Ordered, granular task list
   - Self-validation strategy (lint, type-check, unit tests, e2e)
4. Ask the user to review and iterate. This is the last chance to steer before implementation.

**Context discipline:**
- During exploration (before plan is locked), sub-agents may research the codebase or web.
- Sub-agents consume 100k+ tokens but return only concise summaries.
- Once plan.md is produced, the planning conversation context should be cleared.

## Key Principles

- **Shared design concept first** — never skip grill-me. Misalignment is the #1 cause of wasted work.
- **PRD is the north star** — every session starts by checking "what does the PRD say?"
- **Vertical slices** — AI naturally codes horizontal layers; force vertical slices for immediate feedback.
- **Human reviews every artifact** — PRD, stories, plan. Never chain automatically.
- **Separate planning from implementation** — plan.md must be comprehensive enough to require zero additional context at execution time.
