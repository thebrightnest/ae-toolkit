# AE Toolkit Conventions

This document defines the patterns and standards for authoring, editing, and maintaining skills in this repository.

---

## Project Structure

Each skill lives in its own directory at the repository root:

```
<skill-name>/
├── SKILL.md              # Required. Skill instructions (YAML frontmatter + markdown body)
├── examples/             # Required. Usage examples and sample outputs
│   └── README.md
└── references/           # Required. Detailed reference material, edge cases, deep dives
    └── README.md
```

Skill directories are packaged into `.skill` files (zip archives) via `make package`.

## SKILL.md Format

### YAML Frontmatter

Every `SKILL.md` must begin with YAML frontmatter:

```yaml
---
name: skill-name
description: Explicit trigger description. When to use this skill. What user requests should activate it.
---
```

Rules:

- `name` must match the directory name.
- `description` is the trigger. Be explicit about invocation conditions (e.g., "Use when the user asks to create a skill, update a skill, or write skill instructions").
- No other frontmatter keys unless justified.

### Body Structure

1. **H1 Title** matching the skill name.
2. **When to Use** — bullet list of explicit trigger situations.
3. **Instructions** — procedural steps the agent must follow. Use imperative voice.
4. **Examples** (optional) — if present, keep brief and link to `examples/README.md` for full samples.
5. **Rules** (optional) — hard constraints ("Never...", "Always...").

Length: Keep `SKILL.md` under 400 lines. Move deep detail to `references/`.

## Writing Style

- **Imperative voice:** "Scan the project", "Research best practices", "Run the test suite".
- **Explicit triggers:** The `description` and "When to Use" section should make invocation unambiguous.
- **No agent assumptions:** Skills must work with Claude, Kimi, Cursor, Codex, or paste-into-chat. Do not reference tool-specific syntax unless unavoidable.
- **Concise over verbose:** Agents have context windows. Every sentence should carry instructions, not fluff.

## Naming Conventions

- Skill directories: kebab-case (`aet-setup`, `aet-validate-scope`).
- Files inside skills: `SKILL.md`, `README.md` (examples/references).
- ADR files: `NNN-title-in-kebab-case.md`.

## Error Handling

- If a skill cannot complete its task, it must explain why and what the user should do next.
- Never silently skip a step because a file is missing; document the skip in output.

## Versioning

Skills are versioned implicitly by git commit. The `.skill` package is a snapshot. No separate version field in frontmatter.
