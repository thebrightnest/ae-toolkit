# PRD: aet-upgrade Skill

## Overview

Two of the worst June incidents were Laravel 11 breaking changes (the `hashed` cast double-hashing; the `storage/app/private` path move) that no skill could own. Upgrades are not a feature — no PRD makes sense. They are not a bug — nothing was "broken" yet. They silently fall through the toolkit's routing.

This PRD creates **`aet-upgrade`**, a skill that treats dependency and framework upgrades as a first-class work type with their own proportionate pipeline.

## Goals

1. **Create `aet-upgrade` skill** — YAML frontmatter, markdown instructions, examples, references. Under 400 lines.
2. **Framework-agnostic breaking-change analysis** — fetch the upgrade guide/changelog for the bumped dependency, enumerate breaking changes, grep the codebase for each affected pattern.
3. **Risk-mapped plan** — classify each breaking change as high/medium/low risk based on whether the pattern appears in the codebase.
4. **Smoke before/after** — run foundation smoke checks before starting the upgrade and after completing it.
5. **Integration with work-class routing** — `aet-upgrade` is a critical-class work type, routed from the triage front door.

## Non-Goals

- Automated dependency bumping (e.g., `composer update`, `npm update`). The skill plans and validates; the actual bump is still human- or agent-executed.
- CVE scanning or security auditing. That remains `aet-cso`'s domain.
- Handling every package manager. The skill is agnostic; examples cover common cases (npm, composer, pip) but the procedure is generic.

## User Stories

- As a developer upgrading Laravel, I want the toolkit to tell me exactly which breaking changes affect my codebase before I start.
- As a team lead, I want upgrade work to follow the same governance as critical features — PRD, smoke checks, evidence — rather than bypassing the system.
- As an agent, I want a clear procedure for upgrade work so I don't accidentally treat it as a bug or feature.

## Acceptance Criteria

- [ ] `aet-upgrade/SKILL.md` exists with valid YAML frontmatter (`name: aet-upgrade`, `description` explicitly stating when to trigger).
- [ ] `aet-upgrade/examples/` and `aet-upgrade/references/` exist.
- [ ] Skill instructions include: fetching changelog, enumerating breaking changes, grepping codebase, risk mapping, smoke before/after.
- [ ] Skill is under 400 lines; deep detail lives in `references/`.
- [ ] `aet-upgrade` is added to the work-class routing table as critical-class.
- [ ] `make package` produces `aet-upgrade.skill`.
- [ ] `make validate` passes for the new skill.

## Open Questions

1. Should the breaking-change checklist be generated as a plan file, or live inline in the skill instructions?
2. Should `aet-upgrade` integrate with `aet-verify` (run smoke after) or call it independently?
3. How do we handle upgrades with no published changelog (e.g., internal packages)?

---

*Stage: scope-validated*
*Validated: 2026-06-10*
*Notes: No conflicts. Self-contained new skill. Work-class routing (PRD 1) must classify it as critical before this skill is used in production.*
