---
name: aet-pipeline-plan
description: End-to-end planning pipeline. Takes a raw idea and runs it through aet-discover → aet-plan → aet-validate-scope in sequence. Stops at human gates. Produces a scope-validated PRD and plan files ready for implementation. Triggers on requests like "pipeline plan this," "run the full planning flow," "plan from scratch," or "I have an idea, do the full planning."
---

# aet-pipeline-plan

Planning pipeline for agentic engineering. One entry point — from raw idea to scope-validated, implementation-ready plan. Chains `aet-discover`, `aet-plan`, and `aet-validate-scope` in order, with hard human gates between them.

## When to Use

- You have a raw idea and want to run the full planning sequence without manually invoking each skill
- You want to ensure no planning step is skipped
- When you want to go from idea → validated PRD → approved plans in a single session

## Before You Start

Before executing, collect the following context:

- `BRANCH` — current git branch
- `REPO_STATE` — clean / dirty / merge-conflict
- `AGENTS_MD` — presence and last-modified date of AGENTS.md
- `LEARNINGS` — top-3 relevant entries from `.agents/learnings.jsonl` (if exists)
- `EXISTING_BRIEFS` — any `docs/product-briefs/*.md` (list titles + dates)
- `EXISTING_PRDS` — any `docs/prds/*.md` (list titles + dates)
- `ACTIVE_PRD_STAGE` — current `*Stage:` value from the most-recently-modified `docs/prds/*.md` footer (if exists)
- `ACTIVE_PLAN_STAGE` — current `*Stage:` value from the most-recently-modified `docs/plans/*.md` footer (if exists)

Use this context to ground all recommendations. Do not ask the user to provide it manually.

If a stage is found, print at the start of execution: `"📍 Current stage: {stage} — resuming pipeline from the appropriate step."`

## Resuming from a Stage

If `ACTIVE_PRD_STAGE` or `ACTIVE_PLAN_STAGE` is found, skip already-completed steps:

| Stage found                          | Resume from                                                        |
| ------------------------------------ | ------------------------------------------------------------------ |
| `brief-validated`                    | Step 2 (aet-plan)                                                  |
| `prd-approved` or `prd-draft`        | Step 3 (aet-validate-scope)                                        |
| `scope-validated` or `plan-approved` | Pipeline complete → suggest `aet-pipeline-implement` or `aet-work` |

## Commands

### `plan`

Run the full planning sequence from raw idea to scope-validated plan.

**Sequence:**

```
Step 1: aet-discover
    ↓ [HARD GATE: verdict must be BUILD]
Step 2: aet-plan
    ↓ [HARD GATE: user approves PRD]
Step 3: aet-validate-scope
    ↓ [OUTPUT: scope-validated PRD + plan-approved plans]
```

**Procedure:**

**Step 1 — aet-discover:**

1. Follow the full `aet-discover` → `discover` command procedure
2. Save the product brief to `docs/product-briefs/{name}-brief.md`
3. Render verdict: **BUILD / NARROW / PIVOT / KILL**
4. **HARD GATE:**

   - If BUILD → continue to Step 2
   - If NARROW / PIVOT / KILL → stop the pipeline. Print:

     ```
     ⛔ Pipeline stopped at aet-discover.
     Verdict: {NARROW/PIVOT/KILL}
     Reason: {brief explanation}
     Next: {assignment from aet-discover verdict definitions}
     Run `aet-pipeline-plan` again once the concept is sharpened.
     ```

**Step 2 — aet-plan:**

1. Follow the `aet-plan` → `clarify-goal` + `create-prd` + `create-stories` + `plan` procedures
2. Produce: `docs/prds/{feature}-prd.md`, `docs/plans/*.md` files, `.agents/work-queue.json`
3. **HARD GATE:** Present PRD to user for review. Ask:

   ```
   "The PRD is ready. Please review docs/prds/{feature}-prd.md.
   Approve to continue to scope validation, or request changes."
   ```

   Do NOT proceed to Step 3 until user explicitly approves.

**Step 3 — aet-validate-scope:**

1. Follow the `aet-validate-scope` → `validate` command procedure
2. Surface conflicts, fuzzy language, code contradictions
3. Update CONTEXT.md and propose ADRs as needed
4. Update plan footers to `scope-validated` / `plan-approved`

**Output:**

- `docs/product-briefs/{name}-brief.md` — stage: `brief-validated`
- `docs/prds/{feature}-prd.md` — stage: `scope-validated`
- `docs/plans/*.md` — stage: `plan-approved`
- `.agents/work-queue.json` — ready for `aet-work`

## Completion Protocol

After the pipeline completes all three steps:

1. Print:

   ```
   ✓ Planning pipeline complete.

   Artifacts:
   - Brief: docs/product-briefs/{name}-brief.md (brief-validated)
   - PRD:   docs/prds/{feature}-prd.md (scope-validated)
   - Plans: docs/plans/*.md (plan-approved)
   - Queue: .agents/work-queue.json

   Next step:
   - Single task: run `aet-pipeline-implement docs/plans/{ticket}-plan.md`
   - All tasks (AFK): run `aet-work run`
   ```

## Key Principles

- **Hard gates are non-negotiable** — the pipeline stops at NARROW/PIVOT/KILL and at PRD review; never auto-advance
- **Resumable** — if a stage is found in the footer, skip completed steps
- **Same quality as individual skills** — the pipeline chains skills, it does not shortcut them
- **AFK-safe** — the only human touchpoints are the two defined gates; everything else runs unattended
