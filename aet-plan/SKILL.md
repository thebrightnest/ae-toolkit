---
name: aet-plan
description: PRD creation, goal clarification, story breakdown, plan.md generation, and optional issue tracker publishing. Use when starting a new feature, sprint, or project. Prevents misalignment by building shared understanding before any code is written. Triggers on requests like "design this feature," "create a PRD," "break this into tickets," or "publish these to GitHub issues."
---

# aet-plan

Planning and alignment for agentic engineering. The #1 failure mode is starting implementation before shared understanding exists. This skill prevents that.

## When to Use

- Starting a new feature, sprint, or project
- You have an idea but no structured plan yet
- The agent built something different from what you imagined (go back to clarify-goal)
- Breaking a PRD into implementable tickets

## Before You Start

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

## Intake Triage

Before planning, confirm this is a **feature or enhancement**, not a **reproducible defect** in existing code.

**Question:** Can you demonstrate unexpected behavior in existing code?

- **Yes** → This is a bug. Stop and redirect to `aet-bug-report`:
  _"This appears to be a reproducible defect in existing code. Use `aet-bug-report` for structured investigation and targeted fixes."_
- **No** → Continue with planning

## Planning Lockout

This skill is **planning-only**. No application source code is written, modified, or deleted.

- `clarify-goal`: Research and codebase exploration are allowed; file edits are forbidden
- `create-prd`: Produce documents only; do not generate source code, migrations, or config
- `create-stories`: Do not implement "quick spikes" or proofs of concept
- `plan`: Architecture notes and pseudocode are allowed; production code is forbidden

If the user states a goal imperatively ("I want X removed"), treat it as a planning target.

## Task Size Guardrails

Every task produced by this skill must fit within a single agent coding session. Oversized tasks cause context bloat, quality degradation, and abandoned sessions. Enforce the dual-limit model at both the story and task level.

### Dual-Limit Model

| Layer                   | Human-Time Limit | AI-Complexity Limit            |
| ----------------------- | ---------------- | ------------------------------ |
| Story (PRD → ticket)    | ≤ 2 days         | ≤ 10 files OR ≤ 500 diff lines |
| Task (ticket → plan.md) | ≤ 4 agent-hours  | ≤ 8 files OR ≤ 300 diff lines  |

A task **fails** if **either** limit is exceeded. AI-complexity is the operative limit; human-time is a sanity check against human-scale estimates (weeks, sprints) leaking into agent plans.

### Auto-Split Procedure

When a task exceeds either limit:

1. Identify natural vertical-slice boundaries:
   - By user-visible behavior (e.g., "user can register" vs "user can reset password")
   - By data entity (e.g., "user schema" vs "order schema")
   - By layer dependency (e.g., "backend API" before "frontend form")
2. Split the task into independently implementable children.
3. Re-evaluate each child against both limits. Repeat recursively.
4. **Max split depth = 3.** If a child still fails after 3 splits, mark it `⚠️ ATOMIC OVERSIZED` and surface it for explicit user approval.
5. Document parent/child relationships with `Split from: {parent-id}` and suffix IDs (`01a`, `01b`).

### Size Labels

Use S/M/L labels on every task. L is a mandatory split trigger.

| Label | Human Time                          | Files | Diff Lines |
| ----- | ----------------------------------- | ----- | ---------- |
| S     | ≤ 2 hr                              | ≤ 3   | ≤ 100      |
| M     | ≤ 1 day                             | ≤ 5   | ≤ 200      |
| L     | > 1 day OR > 5 files OR > 200 lines | —     | —          |

## Commands

### `clarify-goal`

The agent interviews the human until a shared design concept exists. This is the single highest-leverage step in the entire workflow.

**Procedure:**

1. Ask the user to describe what they want to build (brain dump — no structure required)
2. Ask clarifying questions one at a time. Walk down each branch of the design tree.
3. Use multiple-choice options when possible to speed up answers.
4. Continue until the agent is satisfied that a shared understanding exists. Focus on what matters — stop when the core concept is clear, not after an arbitrary number of questions.
5. Summarize the shared design concept for confirmation.

**Rules:**

- This is NOT plan mode. Do not produce artifacts yet. Build shared context first.
- **No implementation** — Never edit source files during clarification. Research only.
- Anti-sycophancy: never say "that's an interesting approach." Always take a position.
- Be efficient — ask about gaps and ambiguities, not every possible detail.
- The conversation history becomes a valuable asset — save it for reference.

### `create-prd`

Transform the grilled conversation into a structured Product Requirements Document.

**Procedure:**

1. Read the clarify-goal conversation history as input.
2. Use `.agents/templates/prd-template.md` as the structure guide.
3. Create `docs/prds/` if it doesn't exist. Produce a PRD saved to `docs/prds/{feature-name}-prd.md`.
4. Include: executive summary, mission, target users, scope (in/out), a numbered **Requirements** section (R-1…, each independently testable — carried from the brief when one exists, minted here otherwise), user stories with acceptance criteria (each citing the R-ids it satisfies), technical notes, architecture decisions, open questions, risks.
5. **Explicitly list out-of-scope items** — crucial for defining "done."
6. Ask the user to review before proceeding. Do not auto-generate stories from an unreviewed PRD.

### `create-stories`

Break the PRD into vertically-sliced, independently implementable tickets.

**Procedure:**

1. Read the approved PRD from `docs/prds/`.
2. Create `docs/plans/` if it doesn't exist. Create tickets as markdown files in `docs/plans/` or push via MCP if configured. Atomic task plans MUST be saved to `docs/plans/{ticket-id}-plan.md`. Roadmaps, audits, and meta-plans MUST be saved to `docs/roadmaps/` or `docs/audits/` and will NOT be added to the work queue.
3. **Force vertical slices**: each ticket must cross all layers (schema + API + minimal UI), not horizontal layers (all DB → all API → all UI).
4. **Apply task size guardrails**. Evaluate each story against the dual-limit model (≤ 2 days human time; ≤ 10 files / 500 diff lines AI-complexity). Auto-split oversized stories recursively (max depth 3). Mark `⚠️ ATOMIC OVERSIZED` if unsplittable.
5. Define blocking relationships between tickets (directed acyclic graph).
6. Each ticket gets: title, user story, acceptance criteria, technical notes, estimated effort, size label (S/M/L), and the R-id(s) it satisfies (cited on each user story and acceptance criterion so coverage is visible at review time).
7. **Plan file frontmatter contract.** Every `docs/plans/{ticket-id}-plan.md` must begin with YAML frontmatter:

   ```yaml
   ---
   id: { ticket-id }
   size: S/M/L
   blocked_by:
     - { blocker-id }
   pipeline: standard
   security_review: required
   security_review_reason: { one line }
   docs_sync: required
   docs_sync_reason: { one line }
   ---
   ```

   - `id` must match the plan filename stem and must be unique within the PRD.
   - `blocked_by` is a list of blocking task IDs; an empty list means no blockers.
   - `size` is the S/M/L complexity label. `stage` lives only in the task record, never in frontmatter.
   - `pipeline` is optional and controls orchestrator isolation: `minimal` (all stages in one session), `standard` (default stage grouping), or `full` (one session per stage).

8. **Set gate routing keys deliberately.** `security_review` and `docs_sync` route the aet-cso and aet-sync-docs stages at plan time, so the engine never judges at run time. Default both to `required`. Set `skipped` only when the gate is genuinely unnecessary for the plan, and always pair a skip with a one-line `security_review_reason` / `docs_sync_reason` recording why — intake rejects a `skipped` key without its reason, and a missing key is treated as `required` (fail-safe: the stage runs).

9. **Queue handoff.** After all plan files are written, do not add them to the sprint automatically. Plans are the durable source of truth; `.agents/work-queue.json` is an ephemeral, gitignored sprint board. Instruct the user to add plans explicitly with `aet-work add`. Do not write `.agents/work-queue.json` directly from this skill.

**Vertical slice rule:**

- Bad (horizontal): "Create user table" → "Add user API" → "Build user profile page"
- Good (vertical): "User can register" (schema + endpoint + form) → "User can view profile" (query + page)

**Work queue handoff:**

- `aet-plan` produces `docs/plans/*.md` only
- Queue management is owned by `aet-work`. After plan files are created, the user curates the sprint with `aet-work add <plan-file>`
- This keeps queue format, merge logic, and state management in a single skill
- See [references/work-queue-format.md](references/work-queue-format.md) for the task record schema

### `publish-issues`

Push locally-created stories to an external issue tracker (GitHub, GitLab, etc.). This is optional — local plan files remain the source of truth for intent and closure.

**Procedure:**

1. Read `docs/plans/*.md` and the approved PRD from `docs/prds/`.
2. Determine the target tracker from user input, environment config, or AGENTS.md.
3. For each story, create an issue with:
   - **Title**: short descriptive name
   - **Type**: HITL (requires human interaction) or AFK (can be implemented without human input)
   - **Blocked by**: references to blocking issues (publish blockers first so real IDs exist)
   - **Parent**: reference to the parent issue/PRD if applicable
   - **What to build**: concise description of the vertical slice
   - **Acceptance criteria**: checklist of verifiable behaviors
4. Apply a triage label (e.g., `needs-triage`) so each issue enters the normal triage flow.
5. Do NOT close or modify any parent issue.
6. Update the local plan files with tracker issue IDs for reference.

**Issue template:**

```markdown
## Parent

Reference to the parent issue or PRD (omit if none).

## What to build

A concise description of this vertical slice. Describe the end-to-end behavior, not layer-by-layer implementation.

## Acceptance criteria

- [ ] Criterion 1
- [ ] Criterion 2
- [ ] Criterion 3

## Blocked by

- Reference to the blocking ticket (if any)

Or "None — can start immediately" if no blockers.
```

**Rules:**

- Publish in dependency order (blockers first) so real issue IDs can be referenced
- External issues are a mirror; the local work queue remains the source of truth for `aet-work`
- If the tracker is not configured, skip this step and document the gap in AGENTS.md

### `plan`

From a ticket/story, produce a structured `plan.md` for implementation.

**Procedure:**

1. Read the ticket and relevant PRD section.
2. Use `.agents/templates/plan-template.md` as the structure guide.
3. Create `docs/plans/` if it doesn't exist. Produce `docs/plans/{ticket-id}-plan.md` containing: (atomic task plans only; save roadmaps, audits, and meta-plans to `docs/roadmaps/` or `docs/audits/`)
   - Summary and user story
   - Locked-in architecture decisions (cannot change without re-planning)
   - Files to create and modify
   - Ordered, granular task list with size labels (S/M/L)
   - Self-validation strategy (lint, type-check, unit tests, e2e)
   - **Never create `docs/plans/plans/` or any nested duplicate directory.** Always write directly to `docs/plans/{filename}`.
4. **Validation strategy gate.** The self-validation strategy must list, for each new source file or module introduced by the plan, at least one specifically named test that will cover it. A strategy that only says "add tests" or "write tests for new behavior" without naming what is tested is flagged as incomplete and must be revised before the plan is saved as `plan-draft`.
   - Distinguish test types: **unit tests** (single layer), **integration tests** (cross-layer within backend or frontend), and **API boundary tests** (frontend ↔ backend contract for vertical slices that introduce both sides).
   - _Cross-Cutting Completeness framing:_ When a plan introduces new source files, verify each has a named test in the validation strategy.
5. **Apply task size guardrails** to the task list. Evaluate each task against the dual-limit model (≤ 4 agent-hours; ≤ 8 files / 300 diff lines). Auto-split oversized tasks into subtasks with explicit dependencies. Mark `⚠️ ATOMIC OVERSIZED` if unsplittable.
6. **Self-consistency lint.** Before saving the plan, run these checks on the produced plan.md. Print the result for each check as `PASS`, `WARN`, or `FAIL`.

   - **Check 1 — Prose constraints in code blocks:** Scan the plan for constraints, requirements, or business rules stated in prose (outside code blocks). Verify each one is represented inside a code block, task list item, or explicit file edit. If a prose constraint has no corresponding code artifact, flag it.
   - **Check 2 — Files assigned to tasks:** Extract every file path from the "Files to create and modify" section. Verify each path appears in at least one task. Unassigned files are a `FAIL`.
   - **Check 3 — Observable acceptance criteria:** For each acceptance criterion, verify it describes an observable user behavior (e.g., "user sees an error message") rather than restating a task (e.g., "add error handling"). Criteria that merely restate tasks are `WARN`; criteria that are unverifiable are `FAIL`.
   - **Check 4 — R-trace coverage:** Collect the R-ids declared in scope (from the PRD/brief Requirements section) and the `(traces: R-n)` citations on the task list. An in-scope R-id with no covering task (and not explicitly deferred with a reason) is a `FAIL`; a task that cites an R-id not present in scope is a `FAIL`.

   **Gate:** Any `FAIL` → stop and print the inconsistency. Do not advance to `plan-draft` until resolved. Any `WARN` → print the warning and continue.

7. Ask the user to review and iterate. This is the last chance to steer before implementation.

**Context discipline:**

- During exploration (before plan is locked), sub-agents may research the codebase or web.
- Sub-agents consume 100k+ tokens but return only concise summaries.
- Once plan.md is produced, the planning conversation context should be cleared.

## Completion Protocol

After the `plan` command completes and the plan.md is ready for review:

1. Ensure the PRD file footer reads:

   ```
   *Stage: prd-approved*
   *Next step: run `aet-validate-scope`*
   ```

2. Ensure the plan.md footer reads:

   ```
   *Stage: plan-draft*
   *Next step: run `aet-validate-scope`*
   ```

3. Confirm the intake triage guard was applied (bug vs. feature) and document the classification in the PRD or plan notes.
4. Confirm the new plan files were explicitly added to `.agents/work-queue.json` with `aet-work add`; run `aet-work sync` only to reconcile existing entries and report drift.
5. Print: `"✓ Stage: prd-approved / plan-draft → Next step: run \`aet-validate-scope\`, then \`aet-work\`"`

## Key Principles

- **Shared design concept first** — never skip clarify-goal. Misalignment is the #1 cause of wasted work.
- **PRD is the north star** — every session starts by checking "what does the PRD say?"
- **Vertical slices** — AI naturally codes horizontal layers; force vertical slices for immediate feedback.
- **Human reviews every artifact** — PRD, stories, plan. Never chain automatically.
- **Separate planning from implementation** — plan.md must be comprehensive enough to require zero additional context at execution time.
- **Planning lockout** — Never edit application source files during planning. Research and exploration are allowed; code changes are not.
- **Imperative input = planning target** — When the user says "do X," interpret it as "help me plan X."
- **Session-sized tasks only** — No task larger than a single agent session. Split early, split often.
- **No nested plan directories** — Never write to `docs/plans/plans/`. The correct path is always `docs/plans/{ticket-id}-plan.md`.
