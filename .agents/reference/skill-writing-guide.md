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

## Quality Checklist Before Publishing

- [ ] `description` explicitly states trigger conditions
- [ ] `name` matches directory name
- [ ] `SKILL.md` is under 400 lines
- [ ] `examples/` and `references/` directories exist
- [ ] Examples are realistic, not toy cases
- [ ] No agent-specific syntax unless unavoidable
- [ ] All external links are valid
