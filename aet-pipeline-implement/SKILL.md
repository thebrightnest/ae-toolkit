---
name: aet-pipeline-implement
description: End-to-end implementation pipeline. Takes an approved plan.md and runs it through aet-tdd → aet-implement → aet-qa → aet-review → aet-cso (conditional) → aet-sync-docs (conditional). Resumable from any stage. Triggers on requests like "pipeline implement," "run the full implementation flow," "implement and test and review," or "full pipeline on this plan."
---

# aet-pipeline-implement

Implementation pipeline for agentic engineering. One entry point — from approved plan to reviewed, secure, synced branch ready for `aet-ship`. Chains all implementation-phase skills in the correct TDD order, with hard gates for human-judgment decisions.

## When to Use

- A `docs/plans/{ticket}-plan.md` exists with stage `plan-approved` or `scope-validated`
- You want to run the full implementation sequence without manually invoking each skill
- When resuming a partially-complete pipeline (reads current stage, skips completed steps)
- Called internally by `aet-work` for each task in the queue

## Before You Start

Before executing, collect the following context:

- `BRANCH` — current git branch
- `REPO_STATE` — clean / dirty / merge-conflict
- `AGENTS_MD` — presence and last-modified date of AGENTS.md
- `LEARNINGS` — top-3 relevant entries from `.agents/learnings.jsonl` (if exists)
- `ACTIVE_PLAN` — the plan.md file (path from user input or current branch name)
- `ACTIVE_PLAN_STAGE` — current `*Stage:` value from the plan.md footer
- `ACTIVE_PRD_STAGE` — current `*Stage:` value from the most-recently-modified `docs/prds/*.md` footer (if exists)

Use this context to ground all recommendations. Do not ask the user to provide it manually.

Print at the start of execution: `"📍 Current stage: {stage} — starting pipeline from {first-step}."`

## Resuming from a Stage

The pipeline reads the plan's current stage and skips completed steps:

| Stage found                          | Start from                                                |
| ------------------------------------ | --------------------------------------------------------- |
| `plan-approved` or `scope-validated` | Step 1 (aet-tdd)                                          |
| `tdd-complete`                       | Step 2 (aet-implement)                                    |
| `implemented`                        | Step 3 (aet-qa)                                           |
| `qa-complete`                        | Step 4 (aet-review)                                       |
| `reviewed`                           | Step 5 (aet-cso, if applicable) or Step 6 (aet-sync-docs) |
| `secure`                             | Step 6 (aet-sync-docs)                                    |
| `synced`                             | Pipeline complete → `aet-ship` then `post-ship-verify`    |
| `merged`                             | Pipeline complete → branch verified on `origin/main`      |

## Commands

### `implement`

Run the full implementation sequence for a single plan.md.

**Input:** Path to `docs/plans/{ticket}-plan.md`

**Sequence:**

```
Step 1: aet-tdd         (RED: write failing tests — the behavior contract)
    ↓ [GATE: tests exist and fail for the right reasons]
Step 2: aet-implement   (GREEN + refactor: write code to satisfy the tests)
    ↓ [GATE: all tests pass, lint and type-check pass]
Step 3: aet-qa          (tiered validation: unit → integration → browser)
    ↓ [GATE: coverage maintained, no new bugs]
Step 4: aet-review      (staff-level diff review)
    ↓ [GATE: no critical architecture issues; auto-fixes applied]
Step 5: aet-cso         (security audit — only if auth/data/API/deps changed)
    ↓ [GATE: no Critical or High findings]
Step 6: aet-sync-docs   (sync PRD + plan to reality — only if divergences found)
    ↓
Branch ready for aet-ship
```

**Procedure:**

**Step 0 — Approval checkpoint:**

Before starting the pipeline, confirm the implementation scope:

1. List every file you intend to modify or create
2. State the approximate magnitude: "~N files, ~M lines changed"
3. Check for unattended execution (environment variable `AET_EXECUTION_MODE`):
   - If `AET_EXECUTION_MODE=unattended`: print `🤖 Unattended mode (AET_EXECUTION_MODE=unattended) — skipping interactive approval. Proceeding with: ~N files, ~M lines changed.` and continue directly to Step 1
   - Otherwise: ask _"This will modify the files listed above. Approve to proceed?"_ and **hard gate** — do not begin the pipeline until the user explicitly confirms

**Step 1 — aet-tdd:**

1. Follow the `aet-tdd` → `plan-tests`, `tracer`, `cycle`, `refactor` command procedures
2. Write failing tests that define the behavior contract for this plan
3. **GATE:** Confirm tests exist and fail (RED confirmed). If tests cannot be written (no testable interface), note the reason and continue.
4. Stage advances to `tdd-complete`

**Step 2 — aet-implement:**

1. Follow the `aet-implement` → `implement` command procedure
2. Write code to satisfy the tests from Step 1
3. Run validation: lint, type-check, all tests must pass
4. **GATE:** All tests pass. If validation fails, auto-retry up to 3×, then stop for human review.
5. Stage advances to `implemented`

**Step 3 — aet-qa:**

1. Follow the `aet-qa` → `qa` command procedure (tier: Standard by default)
2. Run full test suite + integration tests + browser tests (if Playwright configured)
3. For each bug found: fix + add regression test + commit atomically
4. **GATE:** All tiers pass, coverage maintained. If unresolvable bug found, stop for human review.
5. Stage advances to `qa-complete`

**Step 4 — aet-review:**

1. Follow the `aet-review` → `review` command procedure
2. Multi-lens review: architecture, SQL safety, error handling, completeness, tests
3. Auto-fix obvious issues (style, imports, typos)
4. **HARD GATE:** If architecture or scope issues found → stop pipeline. Print:

   ```
   ⛔ Pipeline paused at aet-review.
   Issues require human judgment: {summary of flags}
   Resolve these before re-running aet-pipeline-implement (will resume from aet-review stage).
   ```

5. Stage advances to `reviewed`

**Step 5 — aet-cso (conditional):**

1. Check if diff touches auth, data models, API endpoints, or dependencies
2. If yes: follow the `aet-cso` → `cso` command procedure
3. **HARD GATE:** Any Critical or High finding → stop pipeline. Print:

   ```
   ⛔ Pipeline paused at aet-cso.
   Security finding: {severity} — {description}
   Fix before re-running aet-pipeline-implement (will resume from aet-cso stage).
   ```

4. If no security-sensitive files changed: skip this step, advance directly to Step 6
5. Stage advances to `secure`

**Step 6 — aet-sync-docs (conditional):**

1. Check if aet-review or aet-cso noted divergences from the plan
2. If yes: follow the `aet-sync-docs` → `sync` command procedure
3. If no meaningful divergences: update stage only, skip docs commit
4. Stage advances to `synced`

### `post-ship-verify`

Verify the branch has been merged to `origin/main` and advance the plan to `merged`.

**When to Use**

- After `aet-ship` confirms the PR is merged
- When resuming at stage `synced` and the PR has already merged

**Procedure:**

1. Run `git fetch origin`
2. Verify: `git merge-base --is-ancestor HEAD origin/main`
3. If the check fails:

   - **STOP** and print:

     ```
     ⚠️  POST-SHIP VERIFICATION FAILED
         This branch's commits are NOT ancestors of origin/main.
         The PR may not have merged yet, or it targeted a different base branch.
         Re-run this step after the PR is confirmed merged.
     ```

   - Do not advance the stage

4. If the check passes:

   - Print: `✓ Post-ship verification passed. Branch is on origin/main.`
   - Update the plan.md footer to:

     ```
     *Stage: merged*
     *Next step: none — pipeline complete*
     ```

   - If `.agents/work-queue.json` exists, find the task matching the current branch and set `merge_verified: true`, `merged_at` to current ISO-8601 timestamp, and `completed_at` to current ISO-8601 timestamp if not already set
   - Print:

     ```
     ✓ Implementation pipeline complete.

     Branch: {branch}
     Stage: merged
     Work queue: merge_verified
     ```

## Auto-retry Rules

- Steps 1–3 (tdd, implement, qa): auto-retry up to 3× on validation/test failure, then stop for human review
- Steps 4–6 (review, cso, sync-docs): no auto-retry; hard stop on failure, preserve branch for inspection

## Completion Protocol

After all steps complete:

1. Update the plan.md footer to:

   ```
   *Stage: synced*
   *Next step: run `aet-ship`, then `post-ship-verify` to reach `merged`*
   ```

2. Print:

   ```
   ✓ Implementation pipeline complete.

   Branch: {branch}
   Reports committed:
   - .review-report.md
   - .security-audit.md  (if aet-cso ran)
   - .qa-report.md

   Next step: run `aet-ship` to open a PR, then `post-ship-verify` to reach `merged`.
   ```

## Key Principles

- **TDD order is enforced** — tests define the contract before code is written; this is not optional
- **Resumable** — the pipeline reads plan stage and skips completed steps; safe to re-run after failure
- **Hard gates on judgment calls** — auto-retry mechanical failures; stop for human judgment on architecture and security
- **Each step is independently callable** — the pipeline chains skills; each skill can still be run in isolation
- **aet-work uses this** — when `aet-work` runs the queue, it calls this pipeline per task, giving every queued task full quality coverage
