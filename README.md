# Agentic Engineering Toolkit (AE Toolkit)

A collection of agent skills for the open skills ecosystem. Each skill is a self-contained package that extends AI assistant capabilities with specialized knowledge, workflows, and tools. This is the AE Toolkit — skills for agentic engineering.

**Design principles:** Agent-agnostic, one-skill-one-job, context-window discipline, and system evolution as a first-class concern.

## Skills

| Skill | Description | Install |
|-------|-------------|---------|
| [aet-setup](./aet-setup) | Bootstrap or upgrade any software project with best-practice documentation, code quality enforcement, local automation, and AI guardrails. Scaffolds the agentic workflow infrastructure. | `npx skills add getatelier/ae-toolkit.git@aet-setup` |
| [aet-plan](./aet-plan) | PRD creation, "grill me" mode, story breakdown, and plan.md generation. Prevents misalignment before any code is written. | `npx skills add getatelier/ae-toolkit.git@aet-plan` |
| [aet-evolve](./aet-evolve) | System evolution through retrospectives and rule/command/template updates. The highest-leverage long-term skill. | `npx skills add getatelier/ae-toolkit.git@aet-evolve` |
| [aet-prime](./aet-prime) | Session context loading with git-as-memory and context discipline. | `npx skills add getatelier/ae-toolkit.git@aet-prime` |
| [aet-implement](./aet-implement) | Fresh-session implementation from plan.md with self-validation. | `npx skills add getatelier/ae-toolkit.git@aet-implement` |
| [aet-review](./aet-review) | Staff-level code review with multi-lens checks and cross-model adversarial challenge. | `npx skills add getatelier/ae-toolkit.git@aet-review` |
| [aet-cso](./aet-cso) | Diff-focused security audit: secrets, injection risks, auth bypass, CVEs, LLM trust boundaries. | `npx skills add getatelier/ae-toolkit.git@aet-cso` |
| [aet-qa](./aet-qa) | Automated QA with tiered validation (Quick/Standard/Exhaustive) and regression test generation. | `npx skills add getatelier/ae-toolkit.git@aet-qa` |
| [aet-ship](./aet-ship) | Pre-merge validation gate with bisectable commits, changelog generation, and PR creation. | `npx skills add getatelier/ae-toolkit.git@aet-ship` |
| [aet-work](./aet-work) | Work queue management and AFK task orchestration. Enables sequential "night shift" loops across multiple plan.md files. | `npx skills add getatelier/ae-toolkit.git@aet-work` |

---

## Use Cases

### Scenario 1: Starting a New Project

You have an idea. You want solid foundations from day one.

```
/aet-setup
  → Scaffolds .agents/, docs/prds/, docs/plans/, AGENTS.md,
    linting, testing, git hooks, and agentic workflow infrastructure

/aet-plan grill-me
  → "I want to build a task management app with team collaboration"
  → Agent interviews you with 40–100 questions until shared understanding

/aet-plan create-prd
  → Produces docs/prds/task-app-prd.md
  → You review and approve

/aet-plan create-stories
  → Breaks PRD into vertical-slice tickets in docs/plans/
  → Generates .agents/work-queue.json with DAG structure

/aet-work run --dry-run
  → Previews what the AFK loop would pick first

/aet-work run
  → Picks first unblocked task, implements, validates, commits
  → Clears context between tasks
  → Repeats until all tasks done

/aet-ship
  → Pre-merge gate: tests, coverage, review, security audit
  → Bisectable commits, CHANGELOG, VERSION bump, PR opened
```

**Skills used:** `aet-setup`, `aet-plan`, `aet-work`, `aet-ship`

---

### Scenario 2: Adopting on an Existing Project

You inherited a codebase with no standards. You want to add guardrails and start using agentic workflows.

```
/aet-setup
  → Detects existing stack
  → Audits against master checklist
  → Adds missing: linting, testing, pre-commit hooks, AGENTS.md
  → Creates .agents/ with templates and reference docs
  → Documents deviations from best practice in AGENTS.md

/aet-plan plan
  → Pick your first feature ticket
  → Produces docs/plans/{ticket}-plan.md

/aet-prime
  → Loads AGENTS.md, plan.md, recent commits
  → "Based on the PRD, what should we build next?"

/aet-implement docs/plans/{ticket}-plan.md
  → Fresh session, reads plan as sole input
  → Writes code, runs validation, commits

/aet-review
  → Multi-lens diff review before merging
```

**Skills used:** `aet-setup`, `aet-plan`, `aet-prime`, `aet-implement`, `aet-review`

---

### Scenario 3: Single Task / PIV Loop

You have one well-defined ticket. You want to run the full Plan → Implement → Validate cycle.

```
# Planning (human-in-the-loop)
/aet-plan grill-me
  → Quick alignment on what the ticket should do

/aet-plan plan
  → Produces docs/plans/TICKET-123-plan.md
  → Locked decisions, file list, ordered tasks, validation strategy
  → You review and approve

# Clear context. Start fresh session.

# Execution
/aet-prime
  → Load context: AGENTS.md, plan.md, recent commits

/aet-implement docs/plans/TICKET-123-plan.md
  → Read plan → branch → code → validate → commit

# Validation
/aet-review
  → Staff-level code review

/aet-cso
  → Security audit (if auth/data touched)

/aet-qa
  → Automated QA with tiered validation

/aet-ship
  → Pre-merge gate → PR
```

**Skills used:** `aet-plan`, `aet-prime`, `aet-implement`, `aet-review`, `aet-cso`, `aet-qa`, `aet-ship`

---

### Scenario 4: Big Feature / Epic with Multiple Tasks (AFK Loop)

You have a multi-week epic. You want to plan it once, then let the agent work through tasks sequentially while you focus on other things.

```
# Day shift: Human plans
/aet-plan grill-me
  → Deep alignment session on the full epic

/aet-plan create-prd
  → docs/prds/epic-prd.md approved

/aet-plan create-stories
  → 8 vertical-slice tickets in docs/plans/
  → .agents/work-queue.json with DAG created

# Night shift: Agent implements (AFK)
/aet-work run
  → Task 1: unblocked → implement → validate → done
  → CLEAR CONTEXT
  → Task 2: now unblocked → implement → validate → done
  → CLEAR CONTEXT
  → Task 3: implement → FAIL (test broken)
  → LOOP STOPS for human review

# Morning: Human reviews
# Fix the issue, update .agents/learnings.jsonl

# Resume night shift
/aet-work run
  → Picks up where it left off
  → Task 3: retry → done
  → Tasks 4–8: continue sequentially

# When all tasks done
/aet-ship
  → Merges the epic branch
```

**Skills used:** `aet-plan`, `aet-work`, `aet-ship`

**Key feature:** Context is explicitly cleared between tasks. The loop can run 20+ tasks without degradation because each task starts with a clean 5–15k token context window.

---

### Scenario 5: System Evolution After a Bug

The agent made the same mistake twice. You want to fix the system, not just the code.

```
# Bug occurs during aet-implement
# Agent forgot to handle the error case again

/aet-evolve retro
  → Analyzes what went wrong
  → Root cause: plan.md template lacks an "error handling" section
  → Layer identified: .agents/templates/plan-template.md

/aet-evolve system-evolve
  → Updates plan-template.md with explicit error handling checklist
  → Documents the learning in .agents/learnings.jsonl
  → Commits the change to source control

# Next ticket uses the updated template
# The bug category never happens again
```

**Skills used:** `aet-evolve`

**Why this matters:** One improved template saves dozens of engineer-hours across future sessions. The system gets smarter over time.

---

### Scenario 6: Security-First PR

You're adding OAuth and payment processing. Security is non-negotiable.

```
/aet-plan plan
  → docs/plans/auth-payment-plan.md

/aet-implement docs/plans/auth-payment-plan.md
  → Implements OAuth + payment flow

/aet-cso
  → Scans diff for: secrets, SQL injection, auth bypass,
    LLM trust boundaries, dependency CVEs
  → Produces security report with severity
  → FAIL: found hardcoded API key in config

# Fix the issue, remove the key

/aet-cso
  → Re-scan
  → PASS

/aet-review
  → Architecture review of auth flow

/aet-qa --tier=exhaustive
  → All states tested: login, logout, expired token,
    payment success, payment failure, refund

/aet-ship
  → Pre-merge gate with security audit included
```

**Skills used:** `aet-plan`, `aet-implement`, `aet-cso`, `aet-review`, `aet-qa`, `aet-ship`

---

## Install a Skill

```bash
npx skills add getatelier/ae-toolkit.git@<skill-name>
```

Or browse for skills:
```bash
npx skills find <query>
```

**Install all at once:**
```bash
npx skills add getatelier/ae-toolkit.git@aet-setup
npx skills add getatelier/ae-toolkit.git@aet-plan
npx skills add getatelier/ae-toolkit.git@aet-evolve
npx skills add getatelier/ae-toolkit.git@aet-prime
npx skills add getatelier/ae-toolkit.git@aet-implement
npx skills add getatelier/ae-toolkit.git@aet-review
npx skills add getatelier/ae-toolkit.git@aet-cso
npx skills add getatelier/ae-toolkit.git@aet-qa
npx skills add getatelier/ae-toolkit.git@aet-ship
npx skills add getatelier/ae-toolkit.git@aet-work
```

---

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

This produces `aet-setup.skill` (and any other skill `.skill` files) in the repo root.

## License

MIT
