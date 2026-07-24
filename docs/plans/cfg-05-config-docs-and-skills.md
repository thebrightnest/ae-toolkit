---
id: cfg-05-config-docs-and-skills
size: M
blocked_by:
  - cfg-01-config-resolution-overhaul
  - cfg-02-configure-writer
  - cfg-03-cli-surface-fixes
  - cfg-04-guided-setup
pipeline: standard
status: queued
security_review: skipped
security_review_reason: documentation and skill content only; no code or write surface (epi-11 precedent)
docs_sync: required
docs_sync_reason: this plan IS the documentation deliverable (R-8, R-9, R-10) plus the ADR for the structural change
---

# Plan: Config Docs, Skills, Upgrade Guide, and ADR

## Context

- PRD: `docs/prds/aet-config-file-overhaul-prd.md` (R-8, R-9, R-10; ADR
  mandate from AGENTS.md for structural toolkit changes)
- Blocked on cfg-01..04: documentation describes final behavior, per the
  epi-11 lesson ("if implementation and text disagree, the text loses").
- Verified gaps this closes (2026-07-24 consumer report): skills never
  mention `single-pr`; `aet-work/references/queue-commands.md:50` hardcodes
  the gate on `main`; aet-ship examples hardcode `origin/main`;
  `aet-work/SKILL.md:95` claims `task_backend: github` is valid (rejected by
  `factory.py:59-63`); CONVENTIONS.md:118 spells `--base` as `--base-branch`;
  no upgrade guide exists for the config rename.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Locked design

- **ADR-048** records the two-layer config model (committed team file /
  external shadow file), the rename, root-anchored resolution, and the
  config-specific slug, referencing ewl-07/ADR-022/ADR-044 lineage.
- **CONVENTIONS.md** config section rewritten around the two adoption modes:
  team mode (commit the file) and shadow mode (external file, nothing
  committed, no repo hooks); resolution chain; per-epic `--base`; corrects
  the `--base-branch` typo; describes the epic model as a branch/integration
  model, never a worktree model (R-10).
- **Upgrade guide** `docs/upgrades/` for the releasing version: the
  `aet-work.json` → `aet-config.json` rename via `aet configure --migrate`,
  the new setup commands, indexed from the README upgrades table; CHANGELOG
  pointer lands via aet-release-prep at release time.
- **Skills:** `aet-work` SKILL.md + `references/queue-commands.md` and
  `aet-ship` SKILL.md + examples teach both integration modes, the resolved
  integration branch (not hardcoded `origin/main`), epic closure with
  `--target-branch`, and drop the stale `task_backend: github` claim (R-9).
- **CONTEXT.md** vocabulary gains Team Config / Shadow Mode entries, plus a
  **Config Slug** entry explicitly distinguished from the existing **Project
  Slug** (which keeps the worktree label for telemetry/reports, ADR-022) —
  the two identities must not be conflated by future readers.
- **All filename references move.** Scope-validation (2026-07-24) found
  `.agents/aet-work.json` references beyond CONVENTIONS.md:
  `docs/telemetry-guide.md` (2 sites, `symlink_dependencies`),
  `docs/use-cases.md:432`, `skills/aet-setup/SKILL.md:156`,
  `skills/aet-setup/references/README.md:60`, and `aet-work/SKILL.md:95`
  (also names the removed `configure-backend` command — renamed in cfg-02).
  Historical ADRs/briefs/audits are immutable records and stay as-is.

## Rejected Alternatives

- **A standalone "epic mode" guide doc** — rejected: epi-11 settled that the
  branch model lives in the config section it extends, not a new document;
  shadow mode joins it there.
- **Documenting before cfg-01..04 land** — rejected: epi-11's rule; text
  written against unshipped behavior drifts.

## Task List

1. Finalize ADR-048 (written at planning time; cross-check against as-built
   behavior and correct any drift) — S (traces: R-8)
2. CONVENTIONS.md config section rewrite (modes, chain, typo fix,
   branch-not-worktree language) — M (traces: R-8, R-10)
3. `docs/upgrades/` guide + README upgrades table entry — S (traces: R-8)
4. aet-work + aet-ship skill updates (both modes, no `origin/main`
   hardcoding, stale backend claim removed, `configure-backend` renamed to
   `aet configure`) — M (traces: R-9, R-10)
5. CONTEXT.md vocabulary entries (Team Config, Shadow Mode, Config Slug vs
   Project Slug) + remaining filename sweep (`docs/telemetry-guide.md`,
   `docs/use-cases.md`, aet-setup skill references) — S (traces: R-8)
6. Verify every command cited in the touched docs parses (`--help` surface) —
   S (traces: R-10)
7. Merge branch to main and verify integration — S [Deferred: ship stage]

**Size definitions:** S ≤ 2 hr / ≤ 150 lines; M ≤ 1 day / ≤ 600 lines.

### Floor Check

- [x] Stands alone: the complete documentation deliverable for the PRD;
  splitting docs from skills would ship an inconsistent story.

## Files to Modify

- `docs/adr/048-two-layer-config-model.md` (new)
- `docs/CONVENTIONS.md`
- `docs/upgrades/` (new guide) + `README.md` (upgrades table)
- `docs/telemetry-guide.md`, `docs/use-cases.md` (filename references)
- `CONTEXT.md` (repo root)
- `skills/aet-work/SKILL.md`, `skills/aet-work/references/queue-commands.md`
- `skills/aet-ship/SKILL.md`, `skills/aet-ship/examples/`, `skills/aet-ship/references/`
- `skills/aet-setup/SKILL.md`, `skills/aet-setup/references/README.md`

## Validation Steps

- [ ] `make lint` passes; `aet docs lint` passes; `skills-lint` passes
- [ ] Skill-structure validator passes (`scripts/validate-skills.sh`)
- [ ] Command-citation sweep: every `aet ...` command in touched docs/skills
  appears in the CLI help surface (manual or scripted check) (R-10)
- [ ] No remaining `origin/main` hardcoding in aet-work/aet-ship skill
  content except where trunk-based mode is explicitly the topic (R-9)
- [ ] R-trace coverage: R-8 by tasks 1, 2, 3, 5; R-9 by task 4; R-10 by tasks
  2, 4, 6; no unknown R-ids
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit; documentation returns to describing v1.5.0 behavior
(accurate again once the code plans are also reverted, if they are).

---

_Stage: plan-approved_
_Next step: run `aet-work`_
