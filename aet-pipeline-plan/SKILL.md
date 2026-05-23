---
name: aet-pipeline-plan
description: End-to-end planning pipeline. Takes a validated idea and runs it through aet-plan → aet-validate-scope in sequence, with an optional aet-validate-ui step. Stops at human gates. Produces a scope-validated PRD and plan files ready for implementation. Triggers on requests like "pipeline plan this," "run the full planning flow," "plan this feature," or "help me design." UI validation runs when explicitly requested (e.g., "with UI," "validating UI") or when the user opts in at the PRD gate.
---

# aet-pipeline-plan

Planning pipeline for agentic engineering. One entry point — from validated idea to scope-validated, implementation-ready plan. Chains `aet-plan` and `aet-validate-scope` in order, with an optional `aet-validate-ui` step, and hard human gates between them.

## When to Use

- You have a validated idea and want to run the full planning sequence without manually invoking each skill
- You want to ensure no planning step is skipped
- When you want to go from concept → validated PRD → approved plans in a single session

## What This Skill Does NOT Do

This skill produces **plans and PRDs only**. It never writes, modifies, or deletes application source code.

- Do not create, edit, or delete application source files
- Do not run application tests, linting, or type-checking
- Do not create branches or commits for implementation work
- Do not generate "quick proofs of concept" or spike code

If the user describes a change imperatively ("remove X", "adapt Y", "change Z to W"), treat it as a **planning target**, not a command to execute immediately.

## Before You Start

Before executing, collect the following context:

- `BRANCH` — current git branch
- `REPO_STATE` — clean / dirty / merge-conflict
- `AGENTS_MD` — presence and last-modified date of AGENTS.md
- `LEARNINGS` — top-3 relevant entries from `.agents/learnings.jsonl` (if exists)
- `EXISTING_BRIEFS` — any `docs/product-briefs/*.md` (list titles + dates) — context only; discover is not run
- `EXISTING_PRDS` — any `docs/prds/*.md` (list titles + dates)
- `ACTIVE_PRD_STAGE` — current `*Stage:` value from the most-recently-modified `docs/prds/*.md` footer (if exists)
- `ACTIVE_PLAN_STAGE` — current `*Stage:` value from the most-recently-modified `docs/plans/*.md` footer (if exists)

Use this context to ground all recommendations. Do not ask the user to provide it manually.

If a stage is found, print at the start of execution: `"📍 Current stage: {stage} — resuming pipeline from the appropriate step."`

## Resuming from a Stage

If `ACTIVE_PRD_STAGE` or `ACTIVE_PLAN_STAGE` is found, skip already-completed steps:

| Stage found                          | Resume from                                                        |
| ------------------------------------ | ------------------------------------------------------------------ |
| `prd-approved` or `prd-draft`        | Prompt for UI validation or skip to Step 3 (aet-validate-scope)    |
| `ui-validated`                       | Step 3 (aet-validate-scope)                                        |
| `scope-validated` or `plan-approved` | Pipeline complete → suggest `aet-pipeline-implement` or `aet-work` |

## Commands

### `plan`

Run the full planning sequence from validated idea to scope-validated plan.

**Sequence:**

```
Step 1: aet-plan
    ↓ [HARD GATE: user approves PRD]
Step 2: aet-validate-ui (optional)
    ↓ [HARD GATE: if run, blocking gaps addressed or accepted]
Step 3: aet-validate-scope
    ↓ [OUTPUT: scope-validated PRD + plan-approved plans]
```

**Procedure:**

**Step 0 — Planning Lockout:**

Print the planning lockout banner:

```
🔒 PLANNING MODE ACTIVE
This session produces PRDs and plans only. No code changes.
```

If the user's request contains implementation directives (e.g., "make", "change", "adapt", "remove", "refactor", "fix", "update", "implement", "build"), explicitly restate the goal in planning terms before proceeding.

**Step 1 — aet-plan:**

1. Follow the `aet-plan` → `clarify-goal` + `create-prd` + `create-stories` + `plan` procedures
2. Produce: `docs/prds/{feature}-prd.md`, `docs/plans/*.md` files, `.agents/work-queue.json`
3. **Queue preservation guardrail:** When `aet-plan` produces `.agents/work-queue.json`, it must merge new tickets into the existing queue rather than replacing it. Existing tasks must survive the planning session unchanged.
4. **HARD GATE:** Present PRD to user for review. Ask:

   ```
   "The PRD is ready. Please review docs/prds/{feature}-prd.md.
   Approve to continue. Do you want to run UI validation before scope validation?
   Reply with one of:
   - 'yes' or 'with UI' to run UI validation
   - 'no' or 'skip UI' to go straight to scope validation
   - 'changes' to request PRD edits"
   ```

   Do NOT proceed until the user explicitly responds.

   - If the user approves with UI → proceed to Step 2
   - If the user approves without UI / skips → skip Step 2, proceed to Step 3
   - If the user requests changes → stop and return to Step 1

**Step 2 — aet-validate-ui (conditional):**

Run this step only if the user's original request contained an explicit UI validation trigger (e.g., "with UI", "validating UI", "run UI validation") OR if the user opted in at the Step 1 hard gate.

1. Check the PRD for a "no UI" marker (API-only, CLI-only, pure backend). If found:
   - Print: `"⏭️ UI validation skipped — PRD marked as no UI."`
   - Continue directly to Step 3
2. Follow the `aet-validate-ui` → `validate-ui` command procedure against `docs/prds/{feature}-prd.md`
3. Produce a gap report and append its path to the PRD footer
4. **HARD GATE:**

   - If any `blocking` findings → stop the pipeline. Print:

     ```
     ⛔ Pipeline stopped at aet-validate-ui.
     Blocking findings: {count}
     Report: {path to gap report}
     Address the blocking gaps or explicitly accept them to continue.
     ```

   - If only warnings / all PASS → continue to Step 3

If this step was skipped, proceed directly to Step 3.

**Step 3 — aet-validate-scope:**

1. Follow the `aet-validate-scope` → `validate` command procedure
2. Surface conflicts, fuzzy language, code contradictions
3. Update CONTEXT.md and propose ADRs as needed
4. Update plan footers to `scope-validated` / `plan-approved`

**Step 4 — aet-work sync:**

1. Run `aet-work sync` to incrementally add the newly created `docs/plans/*.md` files to `.agents/work-queue.json`
2. Preserve all existing queue entries and their statuses
3. If drift or orphaned entries are surfaced, resolve them before declaring the pipeline complete

**Output:**

- `docs/prds/{feature}-prd.md` — stage: `scope-validated`
- `docs/ui-reports/{feature}-ui-report.md` — gap report (if UI validation ran)
- `docs/plans/*.md` — stage: `plan-approved`
- `.agents/work-queue.json` — synced via `aet-work sync`, ready for `aet-work`

## Completion Protocol

After the pipeline completes all steps:

1. Print:

   ```
   ✓ Planning pipeline complete.

   Artifacts:
   - PRD:       docs/prds/{feature}-prd.md (scope-validated)
   - UI Report: docs/ui-reports/{feature}-ui-report.md (if UI validation ran)
   - Plans:     docs/plans/*.md (plan-approved)
   - Queue:     .agents/work-queue.json

   Next step:
   - Single task: run `aet-pipeline-implement docs/plans/{ticket}-plan.md`
   - All tasks (AFK): run `aet-work run`
   ```

## Key Principles

- **Hard gates are non-negotiable** — the pipeline stops at PRD review and scope validation; never auto-advance
- **Resumable** — if a stage is found in the footer, skip completed steps
- **Same quality as individual skills** — the pipeline chains skills, it does not shortcut them
- **AFK-safe** — the only human touchpoints are the defined gates; everything else runs unattended
- **Implementation lockout** — Never edit application source files during planning. If a step would require code changes, stop and redirect to `aet-pipeline-implement`
- **UI validation is optional** — Run UI validation only when the user explicitly requests it or opts in at the PRD gate. The "no UI" marker still auto-skips.
- **Imperative requests are planning targets** — "Do X" means "Plan how to do X"
