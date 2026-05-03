# PRD — AET Phase-Based Skill Suite

## Executive Summary

Expand the Agentic Engineering Toolkit (AET) from a single project-setup skill (`aet-setup`) into a cohesive, phase-based skill suite that encodes proven agentic engineering workflow patterns from top practitioners (YC, GStack/Gary Tan, Matt Pocock, AI Transformation Workshop). The suite covers the full development lifecycle: planning → execution → quality → shipping → orchestration. Each skill is agent-agnostic, independently installable, and follows the "One Skill = One Job" principle.

## Mission

Make agentic engineering workflows reproducible, teachable, and composable by encoding the best patterns from the field into a modular skill ecosystem that works with any AI coding agent.

## Target Users

- **Solo developers and small teams** who want to adopt agentic workflows without building them from scratch
- **Engineering leads** who want consistent planning, review, and shipping standards across their team
- **AI-native startups** who treat the AI layer (rules, commands, skills) as first-class infrastructure

## Scope

### In Scope

- **11 skills total:** `aet-setup`, `aet-discover`, `aet-plan`, `aet-evolve`, `aet-prime`, `aet-implement`, `aet-review`, `aet-cso`, `aet-qa`, `aet-ship`, `aet-work`
- Update `aet-setup` to scaffold agentic workflow infrastructure (`.agents/`, templates, `docs/prds/`, `docs/plans/`)
- Agent-agnostic design using open standards (`AGENTS.md`, `.agents/`, `docs/`)
- Modular rules architecture (tiny global rules + task-specific refs loaded on demand)
- Context budget documentation and sub-agent delegation patterns
- Persistent learning system (`.agents/learnings.jsonl`)
- Shared preamble concept for consistent skill invocation
- Work queue system with DAG (`.agents/work-queue.json`) for AFK task orchestration
- Context isolation between tasks in AFK loops
- All skills packaged as `.skill` files for the open skills ecosystem

### Out of Scope (Explicitly)

- GUI/harness (like GStack's Conductor) — skills are CLI/text-based only
- Real-time collaboration features
- Cloud-hosted infrastructure or CI services
- Browser automation binary (recommend Playwright CLI but don't ship one)
- Model-specific optimizations beyond optional tips in `references/`
- Parallel worktrees v2 (sequential loops are v1; parallel is future work)

## User Stories

### Story 1: Developer Plans a New Feature
**As a** developer
**I want** to go from a rough idea to a reviewed implementation plan
**So that** the AI agent builds exactly what I imagined, not what it assumed

**Acceptance Criteria:**
- [ ] `/clarify-goal` interviews me until shared understanding exists
- [ ] `/create-prd` produces a structured PRD saved to `docs/prds/`
- [ ] `/create-stories` breaks the PRD into vertically-sliced tickets with a DAG queue
- [ ] `/plan` produces a self-contained `plan.md` for implementation handoff
- [ ] Each artifact is human-reviewed before the next phase begins

### Story 2: Developer Implements from Plan (Single Task PIV Loop)
**As a** developer
**I want** the agent to execute a reviewed plan in a fresh session
**So that** planning bias doesn't corrupt implementation

**Acceptance Criteria:**
- [ ] `/prime` loads minimal, relevant context at session start
- [ ] `/implement` reads `plan.md` as the sole input
- [ ] Agent self-validates (lint, type-check, tests) before declaring done
- [ ] Implementation is compared against the plan; deviations are flagged

### Story 3: Team Runs an Epic AFK (Multi-Task Loop)
**As a** developer
**I want** the agent to work through multiple tasks sequentially while I focus on other things
**So that** I get the "night shift" productivity boost without micromanaging each task

**Acceptance Criteria:**
- [ ] `create-stories` generates `.agents/work-queue.json` with blocking relationships
- [ ] `aet-work run` picks the next unblocked task automatically
- [ ] Context is cleared between tasks to prevent degradation
- [ ] The loop stops on failure for human review
- [ ] Completed tasks unlock their dependents in the DAG

### Story 4: Team Improves AI Layer Over Time
**As a** team lead
**I want** every bug to improve our rules/commands, not just fix the code
**So that** our agents get more reliable with every sprint

**Acceptance Criteria:**
- [ ] `/retro` analyzes what went wrong and identifies the systemic layer
- [ ] `/system-evolve` updates the specific rule/command/template that allowed the bug
- [ ] Learnings persist in `.agents/learnings.jsonl` across sessions
- [ ] AI layer changes are committed to source control and reviewed in PRs

### Story 5: Developer Ships with Confidence
**As a** developer
**I want** automated pre-merge validation that catches issues before human review
**So that** PRs are clean and review time is spent on judgment, not bugs

**Acceptance Criteria:**
- [ ] `/ship` runs tests, coverage audit, code review, and security audit automatically
- [ ] Bisectable commits are enforced (one logical change per commit)
- [ ] CHANGELOG and VERSION are auto-generated
- [ ] Gate stops only for conflicts, test failures, coverage drops, or version decisions

## Technical Notes

### Architecture Decisions

- **Agent-agnostic over agent-optimized:** The toolkit works with Claude Code, Codex CLI, Cursor, Copilot, Kimi, etc. No `.claude/` hardcoded paths. `AGENTS.md` is the cross-tool standard; `.agents/` is the agent-neutral home.
- **One Skill = One Job:** Rejected monolithic `aet-workflow` skill. Each skill has a single, clear purpose. Skills compose; they don't aggregate.
- **Markdown workflows over slash commands:** Commands live as `.md` files in `.agents/commands/`. Any LLM can read and follow them. No dependency on a specific agent's command system.
- **MCP as optional fallback:** External integrations (Jira, GitHub, Linear) use MCP if available, otherwise produce artifacts for manual copy-paste.
- **Template-driven skill structure:** Every skill follows `SKILL.md` (tiny, 50–150 lines) + `references/` (detailed docs) + `examples/`. Keeps context window usage minimal.
- **Context isolation in loops:** The AFK loop (`aet-work run`) explicitly clears context and re-primes between tasks. Without this, the loop degrades silently after 3–4 tasks.

### Skill Suite

| Skill | Phase | Commands | Key Patterns |
|-------|-------|----------|--------------|
| `aet-setup` | Foundation | `/aet-setup` | Stack detection, quality scaffolding, `.agents/` infrastructure |
| `aet-discover` | Discovery | `discover` | YC-style diagnostic, demand validation, product brief |
| `aet-plan` | Planning | `clarify-goal`, `create-prd`, `create-stories`, `publish-issues`, `plan` | Shared design concept, vertical slices, work-queue generation |
| `aet-evolve` | Evolution | `retro`, `system-evolve` | Outer loop, learning persistence, rule updates |
| `aet-prime` | Execution | `prime` | Git-as-memory, context discipline, on-demand refs |
| `aet-implement` | Execution | `implement` | Single-task, plan.md as sole input, self-validation |
| `aet-review` | Quality | `review`, `codex-review` | Multi-lens review, adversarial challenge |
| `aet-cso` | Quality | `cso` | Diff-focused security audit, pass/fail gate |
| `aet-qa` | Quality | `qa` | Tiered validation, regression test generation |
| `aet-ship` | Shipping | `ship` | Pre-merge gate, bisectable commits, auto-artifacts |
| `aet-work` | Orchestration | `init-queue`, `next`, `run`, `status` | DAG queue, AFK loop, context isolation |

### Components Involved

- **Skill definitions:** 11 `SKILL.md` files across `aet-*` directories
- **Reference docs:** Deep-dive markdown files per skill (context budgets, sub-agent patterns, security checklists, context isolation, etc.)
- **Templates:** PRD, plan, retro templates in `aet-setup/examples/`
- **Work queue:** `.agents/work-queue.json` with DAG structure for task orchestration
- **Packaging:** `Makefile` produces `.skill` zip archives for distribution
- **Distribution:** `npx skills add getatelier/ae-toolkit.git@<skill-name>`

### Artifact Locations

| Artifact | Location |
|----------|----------|
| Skills source | `aet-*/SKILL.md` |
| Skill reference docs | `aet-*/references/*.md` |
| Product briefs | `docs/product-briefs/*.md` |
| Project PRDs | `docs/prds/*.md` |
| Project plans | `docs/plans/*.md` |
| Work queue (DAG) | `.agents/work-queue.json` |
| Agent config | `.agents/` |
| AI context | `AGENTS.md` (project root) |
| Learning log | `.agents/learnings.jsonl` |
| Command workflows | `.agents/commands/*.md` |
| Task-specific refs | `.agents/reference/*.md` |

### Skill Structure Standard

Every AET skill follows the same structure:

```
aet-<name>/
├── SKILL.md              # Tiny: when to use, invocation, shared preamble, core flow
├── examples/
│   └── README.md
├── references/
│   ├── workflow-details.md   # Deep dive into command procedures
│   ├── context-budget.md     # Context window rules
│   └── model-tips.md         # Agent-specific tips (optional)
└── ...
```

**Shared preamble** (copied into every SKILL.md):
- `BRANCH` — current git branch
- `REPO_STATE` — clean / dirty / merge-conflict
- `AGENTS_MD` — presence and last-modified date of AGENTS.md
- `LEARNINGS` — top-3 relevant entries from `.agents/learnings.jsonl`
- `ACTIVE_PLAN` — any `docs/plans/*.md` modified in last 7 days
- `LAST_PIV` — date of last completed plan-implement-validate cycle

### Work Queue Format

`.agents/work-queue.json` enables the AFK loop by tracking task dependencies:

```json
{
  "source_prd": "docs/prds/feature-prd.md",
  "tasks": [
    {
      "id": "T1",
      "title": "User can register",
      "plan_file": "docs/plans/T1-register-plan.md",
      "status": "unblocked",
      "blocks": ["T2"],
      "blocked_by": []
    }
  ]
}
```

- Built from `docs/plans/*.md` only (PRDs are metadata)
- `status`: `unblocked` | `blocked` | `in-progress` | `done` | `failed`
- `blocks` / `blocked_by` arrays define the DAG

### Context Isolation in AFK Loops

**The problem:** Running 5–10 tasks in one session accumulates context until the agent degrades.

**The solution:** After each task:
1. Mark task done in queue
2. **CLEAR CONTEXT** (mandatory)
3. **RE-PRIME** (reload minimal context: AGENTS.md + last 5 commits + next plan.md)
4. Continue to next task

Each task starts with 5–15k tokens. The loop can run 20+ tasks without degradation.

## Use Cases

### UC1: Starting a New Project
Bootstrap → discover → PRD → stories → AFK loop → ship. Full agentic workflow from day one. Discovery is optional if the idea is already validated.

### UC2: Adopting on an Existing Project
Audit → add guardrails → run first PIV loop. Gradual adoption without rewriting the project.

### UC3: Single Task / PIV Loop
Plan → clear context → implement → review → ship. The classic one-ticket cycle.

### UC4: Big Feature / Epic (AFK Loop)
Day shift: human runs discovery (if needed), then plans the PRD and breaks it into stories. Night shift: `aet-work run` implements tasks sequentially with context isolation.

### UC5: System Evolution After a Bug
Retro → identify root cause layer → update rule/template → persist learning. The outer loop that compounds quality.

### UC6: Security-First PR
Plan → implement → `aet-cso` security audit → `aet-qa` exhaustive testing → `aet-ship`. Security is non-optional.

## References & Sources

The patterns encoded in this suite are synthesized from:

1. **AI Transformation Workshop** (Leor Weinstein) — PIV Loop, PRD-first, system evolution
2. **GStack / Gary Tan** — Hard gates, structured decisions, multi-agent orchestration, bisectable commits, template-compiled skills, shared preambles
3. **Matt Pocock** (aihero.dev) — Grill Me, ubiquitous language, TDD, deep modules, vertical slices, day shift / night shift
4. **YC Partner Diana** — AI as operating system, closed loops, software factories, token maxing

All source highlights are preserved in `content/agentic-engineering-study/` for ongoing reference.

## Open Questions

- Should we add a `aet-canary` post-deploy monitoring skill (Phase 4)?
- Should skills support cross-model review out of the box, or is that an advanced configuration?
- How do we validate that the skills work across different agents (Claude, Codex, Cursor) without manual testing on each?
- Should `aet-work` support parallel worktrees (v2) or stay sequential only?

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Skills are too verbose for small context windows | Medium | High | Keep SKILL.md under 150 lines; references loaded on demand only |
| Agent ignores fresh-session recommendation | High | Medium | Document strongly; context clearing in `aet-work run` is mandatory, not optional |
| Teams don't adopt system evolution (outer loop) | High | High | Make `retro` lightweight; tie to `learnings.jsonl`; show ROI |
| AFK loop degrades silently without context isolation | High | High | `aet-work run` mandates clearing; reference doc explains why |
| `.agents/` directory conflicts with existing conventions | Low | Medium | Semantically tied to `AGENTS.md`; follows dot-directory convention |

---

*Created: 2026-05-03*
*Status: Approved / Implemented*
*Implemented by: AET Phase-Based Skill Suite (11 skills packaged)*
