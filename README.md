# AI Skills

A collection of agent skills for the open skills ecosystem. Each skill is a self-contained package that extends AI assistant capabilities with specialized knowledge, workflows, and tools.

## Skills

| Skill | Description | Install |
|-------|-------------|---------|
| [project-quality](./project-quality) | Bootstrap or upgrade any software project with best-practice documentation, code quality enforcement, local automation, and AI guardrails. | `npx skills add pedrorocha-net/aiskills@project-quality` |

## Install a Skill

```bash
npx skills add pedrorocha-net/aiskills@<skill-name>
```

Or browse for skills:
```bash
npx skills find <query>
```

## Development Workflow

This repo is the source of truth. All skills are symlinked from here to `~/.claude/skills/` for active development.

```bash
# Install all skills from this repo into ~/.claude/skills/
make install-skills

# Package all skills into .skill files
make package

# Scaffold a new skill
make add-skill NAME=my-new-skill
```

## Adding a New Skill

```bash
make add-skill NAME=my-skill
```

This creates:
```
my-skill/
├── SKILL.md
├── examples/
│   └── README.md
└── references/
    └── README.md
```

Edit `SKILL.md` following the [skill creator guide](https://docs.kimi.ai/skills). Key rules:
- YAML frontmatter with `name` and `description` (description is the trigger — be explicit about when to use it)
- Concise is key — only add context the AI doesn't already have
- Use references/ for detailed docs, keep SKILL.md for procedural instructions

## Packaging

Skills are distributed as `.skill` files (zip archives):

```bash
make package
```

This produces `project-quality.skill` (and any other skill `.skill` files) in the repo root.

## License

MIT
