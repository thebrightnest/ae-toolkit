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

Skills are installed together from this repository via `npx skills add ... --all`. The pipeline only works when the whole system is present.

## Package-Deliverable Rules

AE Toolkit is installed together, not à la carte. Skills may reference shared conventions, cross-skill rules, and toolkit-level docs because the whole system is present at runtime.

Rules:

- Put rules that are specific to one skill inside that skill's files (`SKILL.md`, `references/`, `examples/`, or scripts in `<skill>/bin/`).
- Put cross-cutting rules in toolkit-level docs (`.agents/reference/`, `AGENTS.md`, `docs/CONVENTIONS.md`).
- It is fine for a skill to reference another skill or a shared convention by name (e.g., "run `aet-validate-scope` next"). Do not rely on hardcoded paths that assume a specific install location.
- If a rule must be visible to an agent that reads only the skill file (e.g., when a skill is pasted into chat), include the essential version of that rule directly in `SKILL.md` or link to a skill-level reference doc.

## Skill Binaries

Skills may include executable helpers in `<skill>/bin/`. These are installed into the agent's skills directory when the toolkit is installed with `npx skills ... --all`, but they are **not** automatically added to `PATH`.

Rules:

- Skill instructions must invoke helper binaries by command name (e.g. `aet-state record-merge`), not by hardcoded agent-specific paths.
- Skills that depend on binaries must include a **Prerequisites** section telling the user how to install them onto `PATH`.
- The canonical installer is owned by `aet-setup`: run the `install-aet-binaries` helper from the installed `aet-setup` skill (`~/.agents/skills/aet-setup/bin/install-aet-binaries`). It symlinks binaries from all installed skill directories into `~/.local/bin` (or `AET_BIN_DIR`).
- `make install-skills` in this repo runs the installer automatically for the local development workflow.

## Planning Artifact Directories

The `docs/` directory has strict boundaries for planning documents. Only atomic, implementable task plans may live in `docs/plans/`; all other planning artifacts belong in their designated directories.

| Directory        | Purpose                                                                        | Queue Ingestion                                            |
| ---------------- | ------------------------------------------------------------------------------ | ---------------------------------------------------------- |
| `docs/plans/`    | Atomic, implementable task plans (single session, ≤ 8 files, ≤ 300 diff lines) | Yes — `aet-work init-queue` and `sync` scan this directory |
| `docs/prds/`     | Product Requirements Documents                                                 | No                                                         |
| `docs/roadmaps/` | Multi-phase roadmaps, completion trackers, meta-plans                          | No                                                         |
| `docs/audits/`   | Testing audits, strategy reviews, gap analyses                                 | No                                                         |

Rules:

- A document in `docs/plans/` that references other plan files or contains multiple "Phase" sections is non-atomic and must be moved to `docs/roadmaps/` or `docs/audits/`.
- The dual-limit model (Task Size Guardrails) is the operative filter: if a plan exceeds AI-complexity limits, it does not belong in `docs/plans/`.
- Directory creation is the user's responsibility; skills document the convention but do not auto-create directories.

## Plan Frontmatter Contract

Every atomic plan file in `docs/plans/` must begin with YAML frontmatter:

```yaml
---
id: { ticket-id }
size: S/M/L
blocked_by:
  - { blocker-id }
---
```

- `id` must match the plan filename stem and be unique within the PRD family.
- `blocked_by` is the authoritative dependency list; prose dependency sections are ignored by `aet-work sync`.
- `size` is the S/M/L complexity label from the dual-limit model.
- `stage` lives only in the task record, never in plan frontmatter.

`aet-work sync` validates the contract and fails closed on missing or duplicate IDs, unknown blockers, mismatched filenames, or invalid size values.

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

### Batching Rule

The opposite mistake is also possible: splitting a coherent feature into plans that are each too small to justify their own branch, worktree, and PR overhead. Before creating a new plan, ask:

- Is this change part of a set of near-identical additions (e.g., multiple example templates, multiple convention docs)?
- Will each resulting diff be ≤ 3 files and ≤ 50 lines?
- Do the changes share the same validation steps and rollout risk?

If the answer is **yes** to any of these, batch the related work into a single plan/branch/PR and list every deliverable in the task list. Do not create one plan per file just because the PRD enumerated files separately.

## Recorded-Forward Work Queue State

Workflow state is recorded at transition time and trusted on read.

- `aet-state transition` is the only writer of `tasks[].state`.
- `aet-work status`, `aet-work next`, and the orchestrator read stored `state` directly and make zero git calls on the read path.
- `aet-state audit` reconciles stored state against git ground truth on demand; it never runs during normal operation.

### Legal Transitions

```text
sync:        ∅ → planned
sync:        planned → blocked            (pending_blockers > 0)
sync:        planned → ready              (pending_blockers == 0)
transition:  blocked → ready              (last blocker reached terminal)
transition:  ready → in_progress          (branch + worktree recorded)
transition:  in_progress.stage advances   (tdd → implement → qa → review → cso → sync-docs)
transition:  in_progress → awaiting_merge (pipeline exited 0; NOT terminal)
transition:  awaiting_merge → merged      (TERMINAL; merge_commit verified once)
transition:  any → abandoned (reason)     (TERMINAL)
transition:  in_progress → failed         (needs inspection; may re-enter)
```

Terminal states are `merged` and `abandoned`. Only terminal states satisfy blockers; `awaiting_merge` does not.

### Live / Settled Partition

`.agents/work-queue.json` holds only non-terminal tasks. When a task reaches a terminal state, the writer appends its final record and history to `.agents/work-history.jsonl` and removes it from the live file atomically. Settled history is retained for auditability but is never loaded for scheduling.

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

## Branch Lifecycle

### Feature Branches

- Branch naming: `<task-id>` or `<type>/<task-id>-<slug>` (e.g., `waf-03-aet-ship-branch-lifecycle`).
- The actual branch name is stored in the work queue `branch` field.
- Feature branches are deleted locally **and remotely** after successful merge verification.
- Do **not** append post-merge commits (plan stage updates, review reports, release bumps) to a branch that has already been merged.

### Release Commits

- `chore(release)` commits and `VERSION` file bumps are **only allowed on `main`**.
- The pre-commit hook rejects release commits on non-main branches.
- `aet-ship` does not bump versions; release versioning is a future skill responsibility.

## Repository Hooks

Hooks live in `scripts/hooks/` and must be symlinked from `.git/hooks/`:

```bash
ln -s $(pwd)/scripts/hooks/pre-push .git/hooks/pre-push
ln -s $(pwd)/scripts/hooks/pre-commit .git/hooks/pre-commit
```

### pre-push

Runs `make validate` before any push. Short-circuits (exits 0 immediately) when **all** pushed refs are branch deletions, so `git push origin --delete` is not blocked by a slow coverage gate.

### pre-commit

Runs the AE Toolkit quality checks:

- **markdownlint** (`make lint`)
- **format-check** (`make format-check`)
- **secrets scan** (via `pre-commit run`, which includes `detect-private-key`)

If the `pre-commit` framework is not installed, the hook falls back to `make lint` and `make format-check`.

## Cross-Project Feedback Channel

Projects that use the AE Toolkit may produce retros with findings relevant to the toolkit itself. These are surfaced through a defined `reports/` convention.

### Reports Directory

Each project maintains a `docs/retros/` directory (or equivalent) for retrospectives. Toolkit-relevant retros are marked and mined periodically.

### Toolkit-Relevant Marker

A retro is toolkit-relevant when its frontmatter includes:

```yaml
---
toolkit-relevant: true
---
```

### Required Sections

Every toolkit-relevant retro must contain:

- **Problem** — What went wrong, with concrete example
- **Root cause** — Why it happened (systemic layer, not individual mistake)
- **Fix** — What was changed in the project
- **Prevents** — What rule, check, or gate would have prevented it

### Mining Procedure

Run `aet-evolve --toolkit` periodically (monthly, or after every 5 retros) to scan `reports/*.md` files with `toolkit-relevant: true` and propose toolkit-level changes. See `aet-evolve/SKILL.md` for the full procedure.

The orchestrator writes execution telemetry directly to `~/.aet/telemetry/{project-slug}/{date}/{run-id}/`. Run `aet-evolve/bin/mine-learnings` periodically to scan the archive for recurring patterns (dependency issues, repeated loops, stage failures, review noise) and propose toolkit-level skill edits.

## Versioning

Skills are versioned implicitly by git commit. No separate version field in frontmatter.
