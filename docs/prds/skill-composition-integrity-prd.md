# PRD: Skill Composition Integrity and Build System

## Overview

The skills contradict each other. `aet-pipeline-implement` institutionalizes the exact horizontal-slicing anti-pattern `aet-tdd` forbids in bold. README says Implement → Review → QA; the pipeline runs QA → Review. `aet-plan` and `aet-pipeline-plan` share identical triggers, causing ambiguous routing. And the Shared Preamble is copy-pasted into ~15 skills and already drifted.

This PRD makes composition **mechanically checkable**: a canonical stage state machine in one doc, a build system that assembles skills from shared partials, and a validator that catches contradictions before they reach users.

## Goals

1. **Canonical pipeline definition** — write the stage state machine in `docs/PIPELINE.md`. This is the single source of truth for order, triggers, and completion protocols.
2. **Build skills from shared source** — shared partials (preamble, guardrail blocks, stage table) assembled into self-contained `SKILL.md` files at build time via `make package`.
3. **Extend `validate-skills.sh`** — verify: completion-protocol "next step" pointers form a consistent graph with `docs/PIPELINE.md`; no two skills share a trigger phrase; preamble blocks match the canonical template.
4. **Fix composition contradictions** — align `aet-pipeline-implement` with `aet-tdd`'s anti-pattern rule; align README order with pipeline order; disambiguate `aet-plan` vs `aet-pipeline-plan` triggers.

## Non-Goals

- Rewriting all 21 skills by hand. The build system does the assembly; one edit propagates.
- Changing the `.skill` packaging format. It stays a zip archive; only the assembly process changes.
- Adding a custom templating language. Plain text partials with simple substitution are sufficient.

## User Stories

- As a toolkit maintainer, I want to update the Shared Preamble in one place, not 15, and have `make package` propagate it.
- As a contributor, I want CI (or local validation) to catch when my new skill uses a trigger phrase already claimed by another skill.
- As a user, I want `aet-tdd` and `aet-pipeline-implement` to agree on whether I should write all tests first or use vertical slices.

## Acceptance Criteria

- [ ] `docs/PIPELINE.md` exists with canonical stage state machine, trigger definitions, and completion protocol graph.
- [ ] `scripts/` contains shared partials: `preamble.md`, `guardrails.md`, `stage-table.md`.
- [ ] `make package` assembles partials into `*/SKILL.md` before zipping into `.skill` files.
- [ ] `scripts/validate-skills.sh` extended to check: next-step graph consistency, trigger uniqueness, preamble template match.
- [ ] `aet-pipeline-implement/SKILL.md` aligned with `aet-tdd/SKILL.md` on test-writing order.
- [ ] README canonical order aligned with actual pipeline execution order.
- [ ] `aet-plan` and `aet-pipeline-plan` triggers disambiguated (e.g., `aet-plan` = "design this feature", `aet-pipeline-plan` = "plan and validate this feature").

## Open Questions

1. Should the build system use Python (standard library) for assembly, or stay in Make/sed?
2. Should partials be markdown files in `scripts/partials/` or embedded in the build script?
3. How do we handle skills that legitimately need a custom preamble variant — exception process or template parameter?

---

*Stage: scope-validated*
*Validated: 2026-06-10*
*Notes: No direct conflicts, but this is the highest-risk change — touches all 21 skills via build system. Recommend implementing after PRD 1 (routing) and before PRD 3/4 (skill content updates) so updates are assembled from partials.*
