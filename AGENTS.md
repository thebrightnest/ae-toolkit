# AE Toolkit Repository — Agent Context

## Project Overview

This is the source-of-truth repo for the **Agentic Engineering Toolkit (AE Toolkit)** — an integrated system of agentic engineering skills. Skills are directories with a `SKILL.md` file (YAML frontmatter + markdown instructions). They are designed to be installed together; the pipeline only works when the whole system is present.

## Stack

- **Content format:** Markdown with YAML frontmatter
- **Build / packaging:** GNU Make + `zip`
- **Quality:** prettier, markdownlint, custom skill-structure validator

## Directory Structure

```
├── <skill-name>/           # One directory per skill
│   ├── SKILL.md            # Skill instructions (YAML frontmatter + markdown)
│   ├── examples/           # Usage examples
│   └── references/         # Detailed reference docs
├── docs/                   # Human-readable documentation
│   ├── CONVENTIONS.md      # Skill authoring conventions
│   ├── use-cases.md        # Workflow scenarios
│   └── adr/                # Architectural Decision Records
├── .agents/                # Agent-neutral workflow infrastructure
│   ├── commands/
│   ├── reference/
│   ├── templates/
│   ├── learnings.jsonl
│   └── work-queue.json
├── scripts/                # Validation and utility scripts
├── Makefile                # Dev orchestration
└── *.skill                 # Packaged skill artifacts (generated)
```

## Tooling Reference

| Command                 | What it runs                                         |
| ----------------------- | ---------------------------------------------------- |
| `make help`             | Show all available targets                           |
| `make install-skills`   | Symlink all skills to `~/.agents/skills/`            |
| `make package`          | Build `.skill` zip artifacts for manual distribution |
| `make add-skill NAME=x` | Scaffold a new skill directory                       |
| `make lint`             | markdownlint all markdown files                      |
| `make format`           | Prettier format all markdown files                   |
| `make format-check`     | Prettier check (CI mode)                             |
| `make validate`         | Run lint + format-check + skill-structure validator  |
| `make install-hooks`    | Install pre-commit hooks                             |

## Skill Structure Validator

`scripts/validate-skills.sh` checks every skill directory for:

- `examples/` and `references/` subdirectories exist
- `SKILL.md` has valid YAML frontmatter with `name` and `description`
- `name` matches the directory name
- `SKILL.md` is under 400 lines (warns on legacy skills over limit)
- All relative internal markdown links resolve

## AI Assistant Guardrails

### Forbidden

- Never modify a `.skill` file by hand — always run `make package` after editing a skill directory
- Never delete or rename a skill directory without updating README.md skill table
- Never commit the `content/` directory (it is gitignored; used for local scratch)
- Never add a new skill without `examples/` and `references/` subdirectories
- Never write skill instructions that assume a specific AI agent (keep them agent-agnostic)
- Never introduce new skill patterns without checking `docs/CONVENTIONS.md` first

### Mandatory

- Always run `make validate` before claiming any skill edit is complete
- Always update `docs/CONVENTIONS.md` if you introduce a new skill pattern
- Always keep `SKILL.md` under 400 lines; move deep detail to `references/`
- Always use YAML frontmatter with `name` and `description` in every new SKILL.md
- Always ensure `description` explicitly states when to trigger the skill
- Always run `make package` after editing skills to regenerate `.skill` files
- Always add an ADR in `docs/adr/` for structural changes to the toolkit itself

### Agentic Workflow Guardrails

- Always produce a PRD before writing code for any feature >1 day of work
- Always review the plan.md before implementation; never skip human validation
- Always branch worktrees from `origin/main` and rebase independent branches onto `origin/main` before shipping; never let a stale or ahead local `main` leak into a PR diff
- **Design-to-implementation hard gate** — Free-form design conversations are not implementation approval. After the user approves a design proposal ("yes", "sounds good", "go ahead", or similar), STOP and confirm scope before writing files: _"This will modify [N files]: [list]. Approve to proceed?"_ Do not begin editing until the user explicitly confirms.
- **Analysis-to-action discipline** — When your own analysis identifies a violation of a documented principle (ADR, convention, guardrail), state the conclusion and propose the fix. Do not present options that preserve a pattern you have proven wrong. The user chooses between valid implementations of the correct direction, not whether to keep a known error.
- Always run self-validation (`make validate`) before declaring a task complete
- Always update `.agents/learnings.jsonl` after a bug or misalignment
- Never plan and implement in the same session; clear context between phases
- Use `docs/product-briefs/` for product briefs, `docs/plans/` for atomic plan.md files, `docs/roadmaps/` for roadmaps, `docs/audits/` for audits, and `docs/prds/` for PRDs
- Use sub-agents for research; keep main context clean
- Load `.agents/reference/` docs only when working on the relevant task type

## Context Budget

- Keep AGENTS.md under 200 lines; detailed rules live in `.agents/reference/`
- Prime command: load only core files + recent commits, not the full codebase
- Planning session: free-form conversation OK, but clear before implementing
- Sub-agents: use for any research consuming >50k tokens
- If context feels "full" (agent repeating itself, missing obvious things), clear and restart

## Decision Log

- **Markdown-only repo:** No package.json, requirements.txt, etc. Quality tools are installed via pre-commit or system package manager.
- **Zip packaging:** `.skill` files are plain zip archives of the skill directory, produced as build artifacts for manual distribution. The recommended install path is `npx skills add ... --all`.
- **No CI:** All gates local via pre-commit + Make. Keeps the repo portable and free of vendor lock-in.
- **Trimmed tooling:** Dropped cspell, lychee, and detect-secrets. A skills library's quality surface is structure and formatting, not runtime security or external link graphs.
