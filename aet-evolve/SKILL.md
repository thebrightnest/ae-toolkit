---
name: aet-evolve
description: System evolution through retrospectives and rule/command/template updates. Use after a bug, misalignment, or completed development cycle. The highest-leverage long-term skill — one improved command saves hours across dozens of future sessions. Triggers on requests like "retro this," "the agent made this mistake again," "update our rules," or "system evolve."
---

# aet-evolve

System evolution for agentic engineering. When the agent makes a mistake, don't just fix the bug — fix the system that allowed it.

## When to Use

- After a bug or misalignment in a completed PIV loop
- The agent repeated a mistake it made before
- You had to manually correct the same pattern multiple times
- You want to improve the AI layer (rules, commands, templates)
- End of sprint / weekly retrospective

## Shared Preamble

Before executing any command in this skill, collect the following context:

- `BRANCH` — current git branch
- `REPO_STATE` — clean / dirty / merge-conflict
- `AGENTS_MD` — presence and last-modified date of AGENTS.md
- `LEARNINGS` — entries from `.agents/learnings.jsonl` whose `trigger` field matches the current context (task type, files touched, or error class). If no trigger match, fall back to the most recent 3 entries.
- `ACTIVE_PLAN` — any `docs/plans/*.md` modified in last 7 days
- `LAST_PIV` — date of last completed plan-implement-validate cycle (from git log if available)
- `ACTIVE_PRD_STAGE` — current `*Stage:` value from the most-recently-modified `docs/prds/*.md` footer (if exists)
- `ACTIVE_PLAN_STAGE` — current `*Stage:` value from the most-recently-modified `docs/plans/*.md` footer (if exists)

Use this context to ground all recommendations. Do not ask the user to provide it manually.

## Prerequisites

`ingest-telemetry` and `mine-learnings` must be on `PATH`. Run `/aet-setup install-binaries` (or `~/.agents/skills/aet-setup/bin/install-aet-binaries`) once after installing skills. If you are developing in this repo, `make install-skills` runs it automatically.

## Commands

### `retro`

Analyze what went wrong in the last loop and identify the systemic root cause.

**Procedure:**

1. **Retro debt check** — review action items from the most recent `docs/retros/*.md`.
   - Verified done → mark complete.
   - Not done → convert to a queue task in `.agents/work-queue.json` or explicitly drop with reason.
   - Record the outcome in the current retro context.
2. Read the completed `docs/plans/{ticket}-plan.md` and the actual implementation (git diff).
3. Identify deviations: what did the agent do differently from the plan? What did you have to correct?
4. Ask: which layer allowed this? Options:
   - **Global rules** (`AGENTS.md`) — coding style, testing strategy, logging
   - **Commands** (`.agents/commands/*.md`) — prompts/procedures that were unclear or incomplete
   - **Reference docs** (`.agents/reference/*.md`) — missing or incorrect task-specific guidance
   - **Templates** (`.agents/templates/*.md`) — gaps in PRD/plan/retro structure
   - **On-demand context** (`docs/CONVENTIONS.md`, architecture notes) — outdated or AI-unreadable docs
5. Use `.agents/templates/retro-template.md` to produce a retro document.
6. Create `docs/retros/` if it doesn't exist. Save to `docs/retros/{date}-retro.md` or append to `.agents/learnings.jsonl`.

### `system-evolve`

Update the layer that allowed the issue so it doesn't happen again.

**Procedure:**

1. Review the retro output to identify the target layer.
2. Propose a specific, minimal change to that layer:
   - If `AGENTS.md` — add/modify one rule or guardrail
   - If command — update the markdown workflow in `.agents/commands/`
   - If reference doc — add/clarify guidance in `.agents/reference/`
   - If template — add a missing section or example
3. Show the exact diff before applying.
4. Apply the change and commit it to source control.
5. Document the learning in `.agents/learnings.jsonl` with:
   - `date`
   - `trigger` — string or list of keywords that describe when this learning applies (e.g., `["test factories", "catch blocks"]`)
   - `problem`
   - `layer`
   - `fix`
   - `prevents`
   - Optional: `recurrence` — count of how many times this issue has recurred (used for escalation; see `references/escalation-ladder.md`)

**Learning persistence format (`.agents/learnings.jsonl`):**

```json
{
  "date": "2026-05-03",
  "trigger": ["test factories", "catch blocks"],
  "problem": "Agent forgot to run tests before committing",
  "layer": "commands/implement.md",
  "fix": "Added explicit 'run tests' step to validation strategy in plan template",
  "prevents": "Untested code being committed"
}
```

Entries without a `trigger` field remain valid; matching falls back to recency.

### `ingest-telemetry`

Archive raw telemetry from a project run so it can be mined for systemic improvements.

See `../docs/telemetry-guide.md` for how to enable telemetry in a project, configure dependency warmup, and manage retention.

**Procedure:**

1. From a project repository, run `ingest-telemetry`.
2. The script copies `.agents/execution.log.jsonl`, `.agents/work-history.jsonl`, and `/tmp/aet-reports/{task-id}/*.md` into `~/.aet/telemetry/{project-slug}/{date}-{run_id}/`.
3. Absolute repository and home paths are sanitized to `{REPO_ROOT}` and `{HOME}` placeholders.
4. Markdown reports receive a YAML frontmatter header with `project_id` and `repo_slug`; a `manifest.json` records all archived files.

### `mine-learnings`

Scan the telemetry archive for recurring patterns and output a ranked report.

See `../docs/telemetry-guide.md` for how to archive telemetry from projects first.

**Procedure:**

1. Run `mine-learnings`.
2. The script scans both structured JSONL records and narrative markdown reports (QA, review, CSO, verification reports) for: dependency issues, repeated loops, full-suite runs, stage failures, and review noise.
3. It prints a markdown report ranked by frequency with example snippets.
4. With `--archive-dir PATH`, point to a custom telemetry root (defaults to `~/.aet/telemetry/`).
5. With `--propose`, it prints suggested skill edits (for example, tighten `aet-setup` dependency checks or `aet-implement` validation guardrails). It **never** writes edits directly.

## Key Principles

- **Outer loop vs inner loop** — inner loop: chug through tickets. Outer loop: pause and improve the AI layer.
- **Treat the AI layer like code** — check changes into source control, review in PRs.
- **One fix, one layer** — don't rewrite everything. The smallest rule change that prevents recurrence.
- **Compounding quality** — `.agents/learnings.jsonl` makes the system smarter across sessions, not just within them.
- **High leverage** — improving one command can save dozens of engineer-hours going forward.
- **Escalation ladder** — when a learning recurs, escalate enforcement strength. See `references/escalation-ladder.md`.
