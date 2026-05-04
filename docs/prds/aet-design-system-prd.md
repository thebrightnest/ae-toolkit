# PRD: aet-design-system-creation Skill

## Executive Summary

Create `aet-design-system-creation`, a new AET skill that produces a complete design system (aesthetic direction, typography, color, layout, motion) as a `DESIGN.md` source-of-truth document. Ported and adapted from Garry Tan's gstack `design-consultation` skill into AET format, voice, and conventions. Removes all gstack-specific infrastructure (binaries, telemetry, brain sync, vendor routing) and integrates natively into the AET workflow between `aet-plan` (PRD) and `aet-validate-scope`.

## Mission

Close the design gap in the AET workflow. AET covers the full engineering lifecycle but has no design phase. Projects that skip design system definition before implementation produce inconsistent UI, accrue design debt, and require expensive rework. This skill makes design a first-class citizen in agentic engineering.

## Target Users

- Solo developers starting a new project's UI with no existing design system
- Teams with a PRD who need to define how the product looks and feels before building
- Projects with a stale or missing DESIGN.md that needs creation or refresh

## Scope

### In Scope
- Complete design system creation: aesthetic, typography, color, layout, spacing, motion
- Competitive landscape research via WebSearch
- `DESIGN.md` generation as project-local source of truth
- HTML preview page generation for visual validation
- Taste profile persistence (project-scoped) to track approved/rejected choices
- Soft PRD gate: recommend but don't block if PRD is missing
- Integration points with `aet-plan`, `aet-validate-scope`, and `aet-implement`
- Three commands: `design-system` (full), `design-review` (update), `design-check` (audit)

### Out of Scope
- Visual mockup generation requiring external binaries (progressive enhancement only, not critical path)
- Codex integration for "outside design voices"
- Cross-project taste profile sync (v2 consideration)
- Automatic DESIGN.md enforcement during `aet-implement` (belongs in `aet-review` or `aet-qa`)
- Design token generation for specific frameworks (too implementation-specific)
- Asset generation (logos, icons, illustrations)

## User Stories

### Story 1: Design System from Scratch
> As a developer with a PRD, I want to run `/aet-design-system-creation` so that I get a complete DESIGN.md with specific font names, hex colors, and layout principles before I write any UI code.

**Acceptance Criteria:**
- Skill checks for existing DESIGN.md and offers update/start-fresh/cancel
- Skill reads PRD from `docs/prds/*.md` for product context (soft gate)
- Skill asks one product context question + memorable-thing forcing question
- Skill optionally researches competitive landscape via WebSearch
- Skill proposes a complete coherent design system with SAFE/RISK breakdown
- Skill generates `DESIGN.md` in project root
- Skill generates `DESIGN-preview.html` in `docs/designs/`

### Story 2: Design System Refresh
> As a developer with an existing DESIGN.md, I want the skill to detect this and enter review mode, suggesting updates based on product evolution.

**Acceptance Criteria:**
- Skill reads existing DESIGN.md
- Skill detects stale elements (e.g., references to removed features)
- Skill suggests specific additions, removals, or modifications
- Skill asks before overwriting existing DESIGN.md

### Story 3: Design Compliance Check
> As a developer mid-implementation, I want the skill to audit whether my current codebase follows the DESIGN.md system.

**Acceptance Criteria:**
- Skill reads DESIGN.md and scans codebase for compliance
- Skill reports deviations with specific file/line references
- Skill suggests fixes for each deviation

### Story 4: Taste Memory
> As a returning user, I want the skill to remember that I rejected purple gradients and prefer monospace fonts so that I don't have to re-explain my taste every session.

**Acceptance Criteria:**
- Skill reads `docs/designs/taste-profile.json` at start
- Skill factors taste profile into proposal
- Skill updates taste profile with user approvals/rejections at end
- Taste profile decays confidence over time (5% per week of inactivity)

## Technical Notes

### Skill Structure
```
aet-design-system-creation/
├── SKILL.md              # Main skill instructions (~300-400 lines target)
├── examples/
│   └── README.md         # Example DESIGN.md outputs
└── references/
    ├── design-principles.md    # AET design philosophy
    └── typography-guide.md     # Reference for font pairings, scale systems
```

### AET Adaptations Required

| gstack Element | AET Replacement |
|----------------|-----------------|
| `~/.claude/skills/gstack/bin/*` | Remove entirely; use native WebSearch + agent knowledge |
| gstack telemetry | Remove |
| gstack brain sync | Remove |
| gstack learnings | Replace with `.agents/learnings.jsonl` reads |
| gstack timeline logging | Remove |
| gstack repo mode / slug | Replace with standard git commands |
| gstack config | Remove or hardcode defaults |
| gstack upgrade checks | Remove |
| gstack proactive/telemetry/routing prompts | Remove entirely |
| `CLAUDE.md` routing injection | Remove |
| `~/gstack/projects/$SLUG/` | Use `docs/designs/` |
| Codex outside voice | Omit entirely |
| AI mockup binary | Omit from critical path; keep as optional enhancement |

### DESIGN.md Output Format
```markdown
# Design System: [Project Name]

## Aesthetic Direction
## Typography
## Color System
## Layout & Spacing
## Motion & Animation
## Component Patterns
## Asset Guidelines
## Accessibility
```

### Integration Points
- **aet-plan**: Read `docs/prds/*.md` for product context; soft gate if missing
- **aet-validate-scope**: DESIGN.md is an input for alignment checking
- **aet-implement**: Implementer references DESIGN.md for visual decisions

## Workflow

The skill flows through phases. The agent progresses through them naturally based on context and user input.

### Phase 0: Pre-checks
Check for existing DESIGN.md; gather product context from README/package.json; soft gate for PRD existence.

### Phase 1: Product Context
Single question covering product, audience, space; "memorable thing" forcing question.

### Phase 2: Research (optional)
Competitive landscape analysis via WebSearch. User can decline.

### Phase 3: The Complete Proposal
Present aesthetic, decoration, layout, typography, color, motion as one coherent package with SAFE/RISK breakdown.

### Phase 4: DESIGN.md Generation
Generate the structured DESIGN.md file.

### Phase 5: Preview
Generate HTML preview page for visual validation.

### Phase 6: Taste Profile Update
Update `docs/designs/taste-profile.json` with approvals/rejections.

## Architecture Decisions

1. **Standalone skill, not sub-command** — Design is a distinct discipline from PRD writing. Keeping it separate makes the skill focused and maintainable.

2. **Project-local artifacts** — `docs/designs/` instead of `~/.gstack/`. Design artifacts are project files in AET's model. Versioned with git, discoverable by humans.

3. **No external binary dependencies** — The skill works with native agent capabilities (WebSearch, file I/O, HTML generation). No bun, no browse binary, no design binary.

4. **Opinionated by default** — Proposes specific fonts, hex colors, layout approaches. Users can push back. This produces better outcomes than option menus.

5. **Project-scoped taste profiles** — Consistent with AET's existing learning system. Cross-project sync can be a v2 enhancement.

## Open Questions (Resolved)

| # | Question | Decision |
|---|----------|----------|
| 1 | PRD requirement? | Soft gate — recommend `/aet-plan` if no PRD exists, but proceed if user says so |
| 2 | Artifact location? | `docs/designs/` — project-local, versioned with git, human-discoverable |
| 3 | Taste profile scope? | Project-scoped only (`docs/designs/taste-profile.json`) |
| 4 | Outside design voices? | Omit entirely — keep the skill lean |

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Skill becomes too large | Medium | Medium | Keep focused: design system definition only |
| gstack voice clashes with AET | Medium | Medium | Explicitly rewrite all prose to AET tone |
| User skips design entirely | High | Low | Soft gate + clear value proposition |
| DESIGN.md goes stale | High | Medium | Phase 0 pre-check detects staleness; skill can re-run full workflow for refresh |

## Completion Criteria

- [ ] `aet-design-system-creation/` directory exists with correct structure
- [ ] `SKILL.md` has YAML frontmatter, all phases, AET voice
- [ ] `make package` produces `aet-design-system-creation.skill`
- [ ] Running the skill on a test repo produces valid `DESIGN.md`
- [ ] README.md skill table includes `aet-design-system-creation`
- [ ] `docs/plans/*.md` tickets exist for all implementation work
