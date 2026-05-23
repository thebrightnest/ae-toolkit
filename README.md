# Agentic Engineering Toolkit (AE Toolkit)

**AE Toolkit is a process, not a collection of prompts.**

Most AI coding sessions start strong and end in drift. The agent builds what it _assumed_, not what you _meant_. Context degrades after a few tasks. The same bug shows up next week because the system never learned. There is no workflow — just vibes and hope.

AE Toolkit fixes this by encoding the best agentic engineering patterns from YC, Garry Tan (GStack), Matt Pocock, and the AI Transformation Workshop into a modular skill suite that runs in order:

**Discover → Plan → Design → Validate → Prime → Implement → Review → QA → Ship → Evolve**

Each skill feeds into the next. `/aet-discover` validates demand before any planning begins. `/aet-plan` writes a PRD. `/aet-design-system-creation` produces DESIGN.md — your design source of truth. `/aet-validate-scope` checks the plan and design against your existing domain model and documented decisions before a single line of code is written. `/aet-implement` reads the plan — with `/aet-tdd` optionally guiding test-first development. `/aet-review` catches what `/aet-implement` missed. `/aet-qa` verifies the fix. `/aet-ship` gates the merge. `/aet-evolve` updates the rules so the bug never repeats. Nothing falls through the cracks because every step knows what came before it.

## What you get

- **Validate before you plan** — `aet-discover` stress-tests ideas with YC-style forcing questions so you don't build something no one needs
- **Shared understanding before code** — `clarify-goal` builds shared understanding through targeted questions until the agent actually gets it
- **Validate against reality before you build** — `aet-validate-scope` catches terminology conflicts, code contradictions, and architectural misalignment while they're still cheap to fix
- **Test-first development** — `aet-tdd` guides red-green-refactor with vertical tracer bullets and integration-style tests that survive refactors
- **Fresh-session implementation** — plans and code never share a context window; bias can't leak
- **Night-shift productivity** — `aet-work run` grinds through your task queue while you sleep, clearing context between each ticket so quality doesn't degrade
- **One-command full flows** — `aet-pipeline-plan` runs the entire planning sequence; `aet-pipeline-implement` runs the full implementation sequence without manual skill switching
- **Compounding quality** — every bug updates a rule, template, or guardrail in `.agents/`. The system gets smarter across sessions, not just within them.
- **Agent-agnostic** — works with Claude Code, Kimi, Cursor, Codex, Copilot, or paste-into-chat. Your workflow is portable.

### Who it's for

- **Solo developers** who want agentic workflows without building them from scratch
- **Engineering leads** who want consistent planning, review, and shipping standards across a team
- **AI-native startups** who treat the AI layer (rules, commands, skills) as first-class infrastructure

---

## Quick Start

### Option 1: Install with `npx skills` (recommended)

The open agent skills installer auto-detects your AI coding tool and works with 35+ agents:

```bash
# Install one (any) skill
npx skills add getatelier/ae-toolkit.git@<skill-name>

# Target a specific agent explicitly
npx skills add getatelier/ae-toolkit.git@<skill-name> -a claude-code
npx skills add getatelier/ae-toolkit.git@<skill-name> -a vscode

# Install all AE Toolkit skills at once
npx skills add getatelier/ae-toolkit.git --all
```

Don't have `npx skills`? Install it once: `npm install -g skills` or use `npx skills` directly.

### Option 2: Manual install

Copy skill directories to your agent's skills folder, or paste the skill content directly into chat:

```bash
# Kimi Code CLI
cp -r aet-setup ~/.kimi/skills/

# Claude Code
cp -r aet-setup ~/.claude/skills/

# Or simply open any SKILL.md and paste it into your chat
```

### Run it

| Tool                          | How to invoke             | Example                               |
| ----------------------------- | ------------------------- | ------------------------------------- |
| **Claude Code**               | Slash command             | `/aet-setup`                          |
| **Kimi Code CLI**             | Natural language          | "Run aet-setup on this project"       |
| **Cursor**                    | Natural language or rules | "Set up this project with aet-setup"  |
| **Codex / Copilot / Generic** | Paste into prompt         | Copy `SKILL.md` content into the chat |

Pipelines work the same way — just invoke `aet-pipeline-plan` or `aet-pipeline-implement` instead of an individual skill.

All skills follow the same markdown-based format. The agent reads the YAML frontmatter (`name`, `description`) to decide when to trigger, then loads the full instructions on demand.

---

## Skills

Install any skill with:

```bash
npx skills add getatelier/ae-toolkit.git@<skill-name>
```

| Skill                                                      | Description                                                                                                                                                                               |
| ---------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [aet-setup](./aet-setup)                                   | Bootstrap or upgrade any software project with best-practice documentation, code quality enforcement, local automation, and AI guardrails. Scaffolds the agentic workflow infrastructure. |
| [aet-extract-stack](./aet-extract-stack)                   | Extract proven infrastructure, DevOps, and automation setup from an existing project into a reusable, sanitized scaffold. Inverse of aet-setup.                                           |
| [aet-discover](./aet-discover)                             | Product-definition diagnostic with YC-style forcing questions. Validates demand, narrows the wedge, and produces a product brief — not a PRD. Hard gate: no code.                         |
| [aet-plan](./aet-plan)                                     | PRD creation, goal clarification, story breakdown, plan.md generation, and optional issue tracker publishing. Prevents misalignment before any code is written.                           |
| [aet-design-system-creation](./aet-design-system-creation) | Complete design system creation: aesthetic direction, typography, color, layout, motion. Produces DESIGN.md as the project's design source of truth. Opinionated and research-driven.     |
| [aet-validate-scope](./aet-validate-scope)                 | Validate a plan against the existing domain model, terminology, and documented decisions. Post-PRD alignment gate before implementation.                                                  |
| [aet-validate-ui](./aet-validate-ui)                       | Validate PRDs and plans for UI/UX coverage gaps. Surfaces accessibility, responsive design, motion, and navigation risks before implementation.                                           |
| [aet-evolve](./aet-evolve)                                 | System evolution through retrospectives and rule/command/template updates. The highest-leverage long-term skill.                                                                          |
| [aet-prime](./aet-prime)                                   | Session context loading with git-as-memory and context discipline.                                                                                                                        |
| [aet-tdd](./aet-tdd)                                       | Test-driven development with red-green-refactor loop and vertical tracer bullets. Integration-style tests through public interfaces.                                                      |
| [aet-implement](./aet-implement)                           | Fresh-session implementation from plan.md with self-validation.                                                                                                                           |
| [aet-review](./aet-review)                                 | Staff-level code review with multi-lens checks and cross-model adversarial challenge.                                                                                                     |
| [aet-cso](./aet-cso)                                       | Diff-focused security audit: secrets, injection risks, auth bypass, CVEs, LLM trust boundaries.                                                                                           |
| [aet-qa](./aet-qa)                                         | Automated QA with tiered validation (Quick/Standard/Exhaustive) and regression test generation.                                                                                           |
| [aet-bug-report](./aet-bug-report)                         | Structured bug investigation and fixing. Reproduce, diagnose, fix, and validate without the overhead of full PRD planning.                                                                |
| [aet-ship](./aet-ship)                                     | Pre-merge validation gate with bisectable commits, changelog generation, and PR creation.                                                                                                 |
| [aet-sync-docs](./aet-sync-docs)                           | Sync PRD and plan.md to reflect what was actually built. Appends a divergence summary when implementation drifts from the plan.                                                           |
| [aet-work](./aet-work)                                     | Work queue management and AFK task orchestration. Enables sequential "night shift" loops across multiple plan.md files.                                                                   |

### Pipelines

These skills chain multiple individual skills into complete end-to-end flows:

| Skill                                              | Description                                                                                                         |
| -------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| [aet-pipeline-plan](./aet-pipeline-plan)           | End-to-end planning pipeline. Runs discover → plan → validate-ui → validate-scope with hard human gates.            |
| [aet-pipeline-implement](./aet-pipeline-implement) | End-to-end implementation pipeline. Runs tdd → implement → qa → review → cso → sync-docs, resumable from any stage. |

---

## Use Cases

Eight real-world scenarios show how the skills compose into complete workflows:

- [Starting a new project](./docs/use-cases.md#scenario-1-starting-a-new-project)
- [Adopting on an existing project](./docs/use-cases.md#scenario-2-adopting-on-an-existing-project)
- [Single task / PIV loop](./docs/use-cases.md#scenario-3-single-task--piv-loop)
- [Big feature / Epic with multiple tasks (AFK loop)](./docs/use-cases.md#scenario-4-big-feature--epic-with-multiple-tasks-afk-loop)
- [System evolution after a bug](./docs/use-cases.md#scenario-5-system-evolution-after-a-bug)
- [Security-first PR](./docs/use-cases.md#scenario-6-security-first-pr)
- [Refactoring with TDD safety rails](./docs/use-cases.md#scenario-7-refactoring-with-tdd-safety-rails)
- [Validating a plan against existing architecture](./docs/use-cases.md#scenario-8-validating-a-plan-against-existing-architecture)

Read the full walkthroughs in [docs/use-cases.md](./docs/use-cases.md).

---

## Development Workflow

This repo is the source of truth. All skills are symlinked from here to your agent's skills directory for active development.

```bash
# Install all skills from this repo into ~/.claude/skills/
make install-skills

# Install into a different agent's skills directory
SKILLS_DIR=~/.kimi/skills make install-skills
SKILLS_DIR=~/.cursor/skills make install-skills

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

This produces `aet-setup.skill` (and any other skill `.skill` files) in the repo root.

## License

MIT
