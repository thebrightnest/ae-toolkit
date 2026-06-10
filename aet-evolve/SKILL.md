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
- `LEARNINGS` — top-3 relevant entries from `.agents/learnings.jsonl` (if exists)
- `ACTIVE_PLAN` — any `docs/plans/*.md` modified in last 7 days
- `LAST_PIV` — date of last completed plan-implement-validate cycle (from git log if available)
- `ACTIVE_PRD_STAGE` — current `*Stage:` value from the most-recently-modified `docs/prds/*.md` footer (if exists)
- `ACTIVE_PLAN_STAGE` — current `*Stage:` value from the most-recently-modified `docs/plans/*.md` footer (if exists)

Use this context to ground all recommendations. Do not ask the user to provide it manually.

## Commands

### `retro`

Analyze what went wrong in the last loop and identify the systemic root cause.

**Procedure:**

1. Read the completed `docs/plans/{ticket}-plan.md` and the actual implementation (git diff).
2. Identify deviations: what did the agent do differently from the plan? What did you have to correct?
3. Ask: which layer allowed this? Options:
   - **Global rules** (`AGENTS.md`) — coding style, testing strategy, logging
   - **Commands** (`.agents/commands/*.md`) — prompts/procedures that were unclear or incomplete
   - **Reference docs** (`.agents/reference/*.md`) — missing or incorrect task-specific guidance
   - **Templates** (`.agents/templates/*.md`) — gaps in PRD/plan/retro structure
   - **On-demand context** (`docs/CONVENTIONS.md`, architecture notes) — outdated or AI-unreadable docs
4. Use `.agents/templates/retro-template.md` to produce a retro document.
5. Create `docs/retros/` if it doesn't exist. Save to `docs/retros/{date}-retro.md` or append to `.agents/learnings.jsonl`.

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
   - Date
   - Problem summary
   - Root cause layer
   - Fix applied
   - Expected prevention

**Learning persistence format (`.agents/learnings.jsonl`):**

```json
{
  "date": "2026-05-03",
  "problem": "Agent forgot to run tests before committing",
  "layer": "commands/implement.md",
  "fix": "Added explicit 'run tests' step to validation strategy in plan template",
  "prevents": "Untested code being committed"
}
```

## Key Principles

- **Outer loop vs inner loop** — inner loop: chug through tickets. Outer loop: pause and improve the AI layer.
- **Treat the AI layer like code** — check changes into source control, review in PRs.
- **One fix, one layer** — don't rewrite everything. The smallest rule change that prevents recurrence.
- **Compounding quality** — `.agents/learnings.jsonl` makes the system smarter across sessions, not just within them.
- **High leverage** — improving one command can save dozens of engineer-hours going forward.
