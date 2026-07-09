---
name: aet-review
description: Staff-level code review with multi-lens checks and cross-model adversarial challenge. Use before merging code — by author or reviewer. Catches structural issues, edge cases, and completeness gaps. Triggers on requests like "review this code," "code review," or "check my PR."
---

# aet-review

Code review for agentic engineering. Multi-lens diff review before anything lands.

## When to Use

- Before merging any PR
- After implementation but before shipping
- When you want a second opinion on a complex change
- As part of the `aet-ship` gate

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

### `review`

Staff-level diff review with multiple lenses.

**Procedure:**

1. Read the git diff for the current branch scoped to the PR base:
   - Determine the PR base: `origin/main` unless the branch was created from another branch, in which case use that parent branch.
   - Compute it with `git merge-base HEAD origin/main` or `git merge-base HEAD <parent-branch>`.
   - Review `git diff <base>..HEAD` (not `git diff` against the working tree).
   - If the user explicitly specified files, review those files instead of the diff.
2. Read the corresponding `docs/plans/{ticket}-plan.md` to compare implementation against plan
3. **Noise filtering:** ignore changes to project-level noise files — `.gitignore`, `AGENTS.md`, `docs/CONVENTIONS.md`, and similar project-level documentation — unless the task explicitly modifies them. Treat them as noise, not review signal. A noise file is considered in-scope only when the task's acceptance criteria or plan explicitly names it; otherwise skip it.
4. Run through review lenses:

   - **Project Structure** — do new files/directories follow the same pattern as existing ones? If the project uses symlinks, are new entries created in the real location (symlink target) and linked correctly? Run `ls -la` on the parent directory for any path where new files were created.
   - **Architecture** — does the change fit the existing structure? Are modules deep or shallow?
   - **SQL Safety** — are queries parameterized? Any injection risks?
   - **Conditional Side Effects** — are there hidden side effects in conditional branches?
   - **Error Handling** — are all error paths handled? Are failures observable?
   - **Completeness** — does the diff deliver the behavior described in the acceptance criteria? Ask: "If I exercised this as the user, what would I see?" This catches missing CSS, missing endpoints, and missing error states even when the plan never mentioned them.
   - **Tests** — coverage completeness check:

     1. For each new source file in the diff, verify at least one test file imports or references it. If none exists, classify as **fix-now**.
     2. If the diff introduces both a new backend route/controller and new frontend API client code, verify an API boundary test exists. If none exists, classify as **fix-now**.

     A "new source file" is any file added by the diff that is not a test file, config file, migration, seed, or type-only definition. Apply judgment — a file exporting only interfaces does not require a test; a file containing business logic, a controller, an observer, or a job does. See `references/test-coverage-check.md` for the mechanical procedure.

   - **Mock Boundaries** — does any test mock a first-party module (internal service, repository, use-case class, or utility)? System boundaries (network, external APIs, file system, timers) are acceptable to mock. First-party code is not. However, if the project already has integration-boundary tests covering the same behavior, downgrade first-party mock concerns from **fix-now** to **flag-for-human** and note the missing integration coverage. If no integration boundary test exists, classify as **fix-now** and require the test to exercise the real module or move to an integration boundary.

   - **Removal Safety** — if the diff deletes symbols from bridge, API, registry, preload, or handler files, extract the deleted names and grep the codebase for remaining references. Flag any matches.

5. For each issue found: classify as fix-now or flag-for-human
6. Auto-fix obvious issues (typos, style, missing imports)
7. Produce a review report:
   - Determine the task ID from the active plan filename or branch name
   - Write the report to `/tmp/aet-reports/{task-id}/review-report.md`
   - Include: pass/fail status, issues found, auto-fixes applied, human flags
   - Do NOT write `.review-report.md` to the repository root

**Evidence verdict (writer contract):**

Before updating the plan.md footer, write a JSON verdict record so the orchestrator can gate the stage machine-checkably. The footer remains a human breadcrumb only.

1. Build a verdict record matching the `review` schema:

   ```json
   {
     "task_id": "{task-id}",
     "stage": "reviewed",
     "skill": "aet-review",
     "verdict": "pass" | "fail",
     "summary": "One-line outcome",
     "generated_at": "{ISO-8601 timestamp}",
     "findings": []
   }
   ```

2. Determine the output path:
   - If `$AET_EVIDENCE_PATH` is set, write to that file.
   - Otherwise, write to `~/.aet/reports/{project-slug}/{task-id}/review.json`.
3. Use `aet-work/lib/evidence.py` (`write_verdict`) when available; otherwise write equivalent JSON to the resolved path.
4. Only update the plan.md footer to `*Stage: reviewed*` after the verdict file is written.

### `codex-review`

Cross-model adversarial review. If another AI model is available, run an independent review and compare findings.

**Procedure:**

1. Summarize the diff and plan in a format suitable for another model
2. Ask the other model to review with an adversarial stance: "Actively try to find bugs, security issues, and design flaws."
3. Compare findings with the primary review
4. Highlight discrepancies — areas where one model found something the other missed

**Model personality heuristic:**

- Claude-style models: great at architecture, patterns, and broad reasoning
- Codex-style models: great at precision, edge cases, and challenging assumptions
- Cross-model analysis catches failure modes that either model alone would miss

## Completion Protocol

After `review` completes with pass status:

1. Determine next step:
   - Diff touches auth, data models, API endpoints, or dependencies → `aet-cso`
   - Diff does not touch those → `aet-sync-docs`
2. Update the plan.md footer:

   ```
   *Stage: reviewed*
   *Next step: run `{determined skill from step 1}`*
   ```

3. Print: `"✓ Stage: reviewed → Next step: run \`{aet-cso or aet-sync-docs}\`"`

## Key Principles

- **Multi-lens catches more** — no single review catches everything
- **Adversarial mode** — actively try to break the code, not just validate it
- **Auto-fix the obvious** — don't waste human time on style/naming issues
- **Flag the subtle** — human review is for architecture and edge-case judgment
- **Compare to plan** — implementation must match what was agreed upon
