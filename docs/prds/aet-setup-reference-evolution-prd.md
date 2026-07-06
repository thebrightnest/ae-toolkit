# PRD: aet-setup Reference Evolution

## Overview

Evolve the default `aet-setup` skill scaffold so newly bootstrapped AE Toolkit projects receive a richer, research-driven set of reference documents in `docs/references/`. These defaults are distilled from the reference folders of four active AE Toolkit-consuming projects (Atelier, Shary, Personica, Blueocean) and capture the most reusable load-on-demand guardrails: testing strategy, API conventions, security guidelines, UI conventions, and worktree/ship hygiene. The skill itself will continue to auto-detect stack and adapt, but it will now ship opinionated starter templates instead of leaving every project to reinvent them.

## Goals

1. Add default reference templates to `aet-setup/examples/` for:
   - `README.md` — load-on-demand index
   - `testing-strategy.md` — pyramid, suite splitting, overtesting rules, change-type validation matrix
   - `api-conventions.md` — auth, response envelopes, URL naming, type-sync sequence
   - `security-guidelines.md` — threat model, controls, forbidden patterns
   - `ui-conventions.md` — component source priority, design-token alignment (frontend projects)
   - `worktree-ship-hygiene.md` — merge-base checks, rebase commands, PR scope red flags
2. Update `aet-setup/examples/AGENTS.md.example` to list the new reference docs in its "Reference Docs (load on demand)" section.
3. Update `aet-setup/SKILL.md` to describe the new scaffolded reference artifacts in `docs/references/` and link to them.
4. Update `aet-setup/checklist.md` to verify that reference docs are generated and load-on-demand.
5. Ensure all new content passes `make validate` (markdownlint, prettier, skill-structure validator).

## Non-Goals

- This PRD does not change `aet-setup` stack-detection logic or add new CLI flags.
- It does not retrofit these templates into existing AE Toolkit projects; it only changes what `aet-setup` scaffolds for new/upgrade runs.
- It does not modify packaged `.skill` files directly; those are regenerated via `make package` after skill changes.
- It does not replicate project-specific deep rules (e.g., Atelier's Electron preload serialization or Claude SDK `settingSources`); those remain the responsibility of per-project `aet-evolve` learnings.

## User Stories

- As an AE Toolkit user bootstrapping a new project, I want `aet-setup` to create useful `docs/references/` stubs so that my agents have load-on-demand guardrails from day one.
- As a project maintainer, I want the default testing-strategy to warn against overtesting and to map change types to validation commands so that agents don't waste time on low-value tests.
- As a reviewer, I want the default security-guidelines to use a threat-model format so that security conversations start from concrete risks, not generic platitudes.

## Acceptance Criteria

- [ ] `aet-setup/examples/` contains `reference-README.md.example`, `testing-strategy.md.example`, `api-conventions.md.example`, `security-guidelines.md.example`, `ui-conventions.md.example`, and `worktree-ship-hygiene.md.example`.
- [ ] `aet-setup/examples/AGENTS.md.example` includes a table mapping each reference doc to the task type that triggers it.
- [ ] `aet-setup/SKILL.md` describes the new `docs/references/` artifacts in the "Generated Artifacts" and "Agentic Workflow Infrastructure" sections.
- [ ] `aet-setup/checklist.md` includes verification items for reference doc scaffolding.
- [ ] `make validate` passes after all changes.
- [ ] No single `SKILL.md` exceeds 400 lines; any overflow is moved to `references/` or `examples/` as appropriate.

## Technical Notes

- Templates must remain stack-agnostic enough to be useful across languages, but may include language-specific examples (e.g., PHPUnit/Vitest/pytest) because those are the dominant stacks in the source projects.
- The `testing-strategy.md.example` should incorporate:
  - Personica's "avoid overtesting" list and validation-by-change-type matrix
  - Shary's suite-splitting pattern (`Feature-Http`, `Feature-Api`, etc.)
  - Atelier's component-testing mocking rules and stable mock references
- The `security-guidelines.md.example` should mirror Shary's format: threat model → controls → forbidden patterns.
- The `ui-conventions.md.example` should mirror Personica's component-source priority (shadcn/ui first) and design-token alignment.
- The `worktree-ship-hygiene.md.example` should capture Personica's merge-base/rebase checklist and red flags.
- All new example files are referenced by `aet-setup/SKILL.md` and `aet-setup/examples/AGENTS.md.example`, but they are copied into the target project as real `docs/references/*.md` files during setup.

## Open Questions

1. Should `css-debugging.md` be a separate template or folded into `ui-conventions.md`?
2. Should `aet-setup` conditionally skip `ui-conventions.md` and `worktree-ship-hygiene.md` when no frontend or no git workflow is detected?
3. Should the reference-doc table in `AGENTS.md.example` be auto-customized during setup based on detected stack?

---

_Intake triage: This is a feature/enhancement, not a reproducible defect._

_Stage: scope-validated_
_Next step: run `aet-work` (single-plan or multi-task queue)_
