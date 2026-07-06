# Skill Writing Guide

Reference material for authoring AE Toolkit skills. Load this file only when creating or editing skills.

## Pre-Plan Checklist

Run this before designing any solution that touches a `SKILL.md`:

- [ ] **Agent-agnostic** — does the proposed approach use any Claude Code-specific
      tooling (`EnterWorktree`, `ExitWorktree`, `Agent` tool, `/clear`, MCP tools)?
      If yes, replace with git/shell equivalents before proceeding.
- [ ] **AGENTS.md guardrails read** — open AGENTS.md and read the "AI Assistant
      Guardrails" section. Not just presence-checked — actually read.
- [ ] **`skill-writing-guide.md` loaded** — you are reading this file (check).
- [ ] **No new patterns** — if introducing a new convention, check
      `docs/CONVENTIONS.md` first and update it after.
- [ ] **New-file location verified** — if creating NEW skill directories, run
      `ls -la <skills-parent-dir>` BEFORE `mkdir`. Check whether existing skills are
      real directories or symlinks. If symlinks, create the new skill in the symlink
      target (the real repo), then add a symlink from the skills directory.
      Never `mkdir` a new skill directly into `~/.agents/skills/` — it will be outside
      the git repo and silently untracked.
- [ ] **Package-deliverable rules** — every rule, guardrail, or convention this skill
      enforces must live inside the skill's packaged files (`SKILL.md`, `references/`,
      `examples/`). Do not rely on `.agents/reference/`, `AGENTS.md`, or other
      toolkit-internal documents for runtime skill behavior, because those files are
      not packaged with the skill when it is installed in another project.

## Frontmatter Schema

```yaml
---
name: skill-name # Required. Must match directory name.
description: > # Required. Trigger description.
  Use when the user wants to X, Y, or Z.
  Trigger on phrases like "do X", "help me Y".
---
```

## Instruction Structure

Use numbered steps for procedural skills:

```markdown
## Execution Steps

### Step 1: Discovery

...

### Step 2: Research

...

### Step 3: Audit

...
```

Use bullet lists for rules and constraints.

## Execution Mode in Skills

If your skill contains an interactive approval gate ("Approve to proceed?", "Hard gate", or similar), you must handle both interactive and unattended execution contexts.

### Contract

```
AET_EXECUTION_MODE
  - unset or "interactive"  → Default. Hard gates enforced.
  - "unattended"            → Orchestrator/background mode. Gates bypassed with logging.
```

### Implementation Pattern

At every approval checkpoint:

1. Check the environment variable.
2. If `unattended`: list the scope, print the bypass log, and continue.
3. If interactive (or unset): present the gate as normal.

**Exact bypass log wording:**

```
🤖 Unattended mode (AET_EXECUTION_MODE=unattended) — skipping interactive approval. Proceeding with: ~N files, ~M lines changed.
```

**Gates that must still stop in unattended mode:**

- ATOMIC OVERSIZED scope override
- Critical/High security findings
- Merge verification failures

### Interactive-Only Exemption

Skills that are **never invoked in unattended mode** (e.g., `aet-bug-report`, which
is always run interactively) may omit `AET_EXECUTION_MODE` handling.

To avoid the validator flagging these skills, use `"Hard gate"` or `"Approval gate"`
phrasing instead of the literal string `"Approve to proceed?"`. The validator
only checks for the exact phrase.

If adding an interactive-only gate to an existing skill, update this guide and
ADR 005 to document the exemption.

## Quality Checklist Before Publishing

- [ ] `description` explicitly states trigger conditions
- [ ] `name` matches directory name
- [ ] `SKILL.md` is under 400 lines
- [ ] `examples/` and `references/` directories exist
- [ ] Examples are realistic, not toy cases
- [ ] No agent-specific syntax unless unavoidable
- [ ] All external links are valid
- [ ] If the skill has approval gates, `AET_EXECUTION_MODE` is handled (unless the skill is documented as interactive-only)
- [ ] All rules the skill enforces are package-deliverable (inside `SKILL.md`, `references/`, or `examples/`), with no dependency on `.agents/reference/` or other toolkit-internal docs
