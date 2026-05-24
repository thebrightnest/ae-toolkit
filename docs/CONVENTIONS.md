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

## Task Size Guardrails

All planning output must be implementable in a single agent coding session. Use the dual-limit model to enforce this.

### Dual-Limit Model

| Layer                   | Human-Time Limit | AI-Complexity Limit            |
| ----------------------- | ---------------- | ------------------------------ |
| Story (PRD → ticket)    | ≤ 2 days         | ≤ 10 files OR ≤ 500 diff lines |
| Task (ticket → plan.md) | ≤ 4 agent-hours  | ≤ 8 files OR ≤ 300 diff lines  |

A task **fails** if **either** limit is exceeded. AI-complexity is the operative limit.

### Size Labels

Every task must carry an S/M/L label:

| Label | Human Time                          | Files | Diff Lines |
| ----- | ----------------------------------- | ----- | ---------- |
| S     | ≤ 2 hr                              | ≤ 3   | ≤ 100      |
| M     | ≤ 1 day                             | ≤ 5   | ≤ 200      |
| L     | > 1 day OR > 5 files OR > 200 lines | —     | —          |

**L is a mandatory split trigger.** No L task may enter the work queue without being broken down.

### Auto-Split Rule

When a task exceeds limits:

1. Split along vertical-slice boundaries (behavior, entity, or layer).
2. Re-evaluate each child. Repeat recursively.
3. **Max split depth = 3.** If a child still fails, mark it `⚠️ ATOMIC OVERSIZED` and surface for explicit user approval.
4. Document splits with `Split from: {parent-id}` and suffix IDs (`01a`, `01b`).

## Execution Mode

Skills with interactive approval gates must respect the execution-mode contract so they work correctly in both interactive sessions and unattended orchestration.

### Contract

```
Environment variable: AET_EXECUTION_MODE
  - unset or "interactive"  → Default. Hard gates enforced.
  - "unattended"            → Orchestrator/background mode. Gates bypassed with logging.
```

### Gate Bypass Protocol (Unattended Mode)

When `AET_EXECUTION_MODE=unattended` is detected at an approval checkpoint:

1. **List scope.** Still enumerate intended files and magnitude (audit trail).
2. **Log bypass.** Print exactly: `🤖 Unattended mode (AET_EXECUTION_MODE=unattended) — skipping interactive approval. Proceeding with: ~N files, ~M lines changed.`
3. **Continue.** Proceed to the next step; do not ask the user.

### Gates That Must Still Stop in Unattended Mode

Not all gates are bypassed. The following categories **must** halt execution even in unattended mode:

- **ATOMIC OVERSIZED tasks** — No human available to approve scope override. Hard stop with non-zero exit code.
- **Critical security findings** (`aet-cso` Critical/High) — Unattended mode must not auto-approve security risks.
- **Merge verification failures** (`aet-ship`, `post-ship-verify`) — Mechanical check; failure is a hard stop.

### Author Checklist

When adding a new approval gate to a skill:

- [ ] Gate checks `AET_EXECUTION_MODE` before prompting
- [ ] Unattended path logs the bypass with the exact emoji + wording above
- [ ] Gate is categorized as "bypassable" or "hard stop even in unattended mode"

## Versioning

Skills are versioned implicitly by git commit. The `.skill` package is a snapshot. No separate version field in frontmatter.
