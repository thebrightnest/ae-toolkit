# PRD: AET Config File Overhaul — Team vs Shadow Config, Discoverable Epic Mode

## Overview

The epic-based integration model shipped in v1.5.0 (ADR-044/045) works, but
opting into it requires hand-editing a JSON file whose location, name, and
precedence nobody can discover from the CLI or the skills. A real consumer
(aet 1.5.0 installed on a client project, 2026-07-24) had to read the
toolkit's source to configure `single-pr` mode and still emitted two broken
commands (`aet run --base`, which the dispatcher does not forward; `aet ship
close --target`, wrong flag name). Additionally, the two adoption modes —
whole-team (committed config) and solo/"shadow" (nothing committed) — are
both possible today but undocumented, and both break silently when `aet` is
invoked from a linked worktree or a subdirectory, because in-tree config is
resolved relative to cwd and the external config slug is labelled per-worktree.

This PRD overhauls the config surface: one canonical in-tree file
(`.agents/aet-config.json`, committed = team mode), one external file
(`~/.aet/{slug}/config.json`, the shadow/personal layer), repo-root-anchored
resolution, a worktree-independent config slug, a CLI writer (`aet configure`),
a working per-run branch override (`--base` forwarded), and the docs/skills
that teach both adoption modes.

## Goals

- A new user can enable epic mode (`integration_mode: single-pr`) with one
  CLI command, without hand-editing JSON.
- Solo adoption on a shared repo ("shadow mode") requires zero committed
  files and works from any checkout or worktree of the project.
- Team adoption is exactly one committed file, `.agents/aet-config.json`;
  personal overrides layer on top via the external file.
- Resolved config (mode, branches, provenance) is inspectable before a run.
- Every command a consumer is told to run in docs actually exists.

## Non-Goals

- No change to the integration engine itself (rebase → re-validate →
  squash-merge → push under the lock); ADR-045 mechanics are untouched.
- No change to the telemetry/reports slug scheme (`~/.aet/telemetry/{slug}`,
  `~/.aet/reports/{slug}` keep the worktree label). The known evidence-path
  split that the label causes for verdict writers (learnings 2026-07-14) is a
  separate follow-up, not this PRD.
- No multi-developer coordination on a shared epic branch (already an
  ADR-045 non-goal; the integration lock stays local and advisory).
- No auto-creation of the epic PR; it stays a manual operator step.
- No migration of plans/PRDs out of `docs/` (owner decision 2026-07-12,
  ewl-07: only config leaves version control).

## Requirements

- **R-1**: The canonical in-tree config file is `.agents/aet-config.json`.
  `.agents/aet-work.json` is renamed away with no silent fallback read. If the
  old file exists and the new one does not, config resolution fails closed
  with an error naming the exact fix, consistent with the
  `IntegrationModeError` fail-closed philosophy — never a silent revert to
  trunk-based defaults. The named fix is a command, not manual surgery:
  `aet configure --migrate` performs the rename (content-preserving, including
  the git-tracked case via `git mv`) and confirms the result.
- **R-2**: In-tree config is resolved against the repository root
  (`git rev-parse --show-toplevel`), not the process cwd, so `aet` works
  identically from any subdirectory of the repo.
- **R-3**: The project slug used for *config* resolution is the main-worktree
  identity (`<main-dir-name>/main` semantics, label dropped), so
  `~/.aet/{slug}/config.json` resolves from every linked worktree of the same
  repo. Telemetry/reports slug derivation is unchanged (see Non-Goals).
- **R-4**: Resolution precedence is preserved and documented:
  `AET_WORK_CONFIG` env → external `~/.aet/{slug}/config.json` → in-tree
  `.agents/aet-config.json` → built-in defaults. External stays first so a
  solo dev can override a committed team config locally (ewl-07 lineage).
- **R-5**: A CLI writer sets every config key without hand-editing JSON:
  `task_backend`, `trunk_branch`, `integration_mode`, `integration_branch`,
  with a scope choice (`project` = in-tree file, `user` = external file).
  Invalid values (e.g. a `integration_mode` outside the legal set) are
  rejected at write time.
- **R-6**: `aet run` and `aet run-one` accept and forward `--base <branch>`
  to the orchestrator, making the documented per-run integration-branch
  override reachable from the installed CLI.
- **R-7**: Resolved configuration is inspectable before a run: `aet setup
  verify` (or equivalent surface) prints resolved `integration_mode`,
  `integration_branch`, and `trunk_branch` with provenance (config /
  detected / fallback), extending epi-11's trunk display.
- **R-8**: "Shadow mode" is documented as a first-class setup: external
  config only, nothing committed, no repo-level hooks; and team mode as one
  committed file. Includes a clear, complete upgrade guide in
  `docs/upgrades/` covering the `aet-work.json` → `aet-config.json` rename
  and the new setup commands, indexed from the README upgrades table and
  pointed to from the CHANGELOG entry for the releasing version.
- **R-11**: First-time setup is code-guided, not doc-guided: the setup
  surface (`aet setup` flow and/or the aet-setup skill) offers to create the
  config — asking the two questions that matter (scope: team/shadow; mode:
  pr-per-task/single-pr) and writing the file in the right place with valid
  values. A fresh install reaches a working config without reading
  CONVENTIONS.md first.
- **R-9**: The skill surface teaches the branch model: `aet-work` and
  `aet-ship` (SKILL.md + references/examples) describe both integration
  modes, how to configure them, and stop hardcoding `origin/main` as the
  merge/verification target; the stale `task_backend: github` claim in
  `aet-work/SKILL.md` is removed.
- **R-10**: Every command referenced by user-facing docs exists and is
  spelled correctly: the `--base-branch` typo in CONVENTIONS.md is fixed,
  `aet ship close --target-branch` is documented with its real name, and
  docs stop describing the epic model as a worktree model (it is a branch/
  integration model).

## User Stories

- As a solo dev on a shared client repo, I want to run one setup command and
  have AET fully configured outside the repo, so that my team sees zero AET
  footprint and I cannot forget an env var (satisfies: R-3, R-4, R-5, R-8).
- As a tech lead adopting AET for my whole team, I want to commit one config
  file so every checkout and worktree resolves the same backend and
  integration mode (satisfies: R-1, R-2, R-4, R-5).
- As a user starting an epic, I want `aet run --base feat/x` to work as
  documented, so that each run targets the right integration branch without
  editing config between epics (satisfies: R-6, R-10).
- As a user about to launch a run, I want to see the resolved mode and
  branches with provenance, so that I never discover a trunk-based fallback
  via a wrong PR (satisfies: R-7).
- As an agent operating on a consumer project, I want skills that describe
  both modes accurately, so that I emit commands that exist (satisfies: R-9,
  R-10).
- As an existing aet user upgrading past the rename, I want a loud, exact
  migration instruction instead of silently running trunk-based, so that my
  epic setup cannot silently degrade (satisfies: R-1, R-8).
- As an existing aet user, I want `aet configure --migrate` to do the rename
  for me, so that upgrading is one command (satisfies: R-1).
- As a brand-new aet user, I want the setup flow to ask me scope and mode and
  write a valid config, so that my first `aet run` works without studying
  the config resolution chain (satisfies: R-11, R-5).

## Acceptance Criteria

- [ ] Fresh repo, `aet configure --integration-mode single-pr --scope user`,
  then `aet run` from a **linked worktree**: mode resolves to `single-pr`
  (satisfies: R-3, R-4, R-5).
- [ ] Same setup, run any `aet` command from a repo subdirectory: config
  still resolves (satisfies: R-2).
- [ ] Committed `.agents/aet-config.json` in a team repo: a fresh clone with
  no external config resolves the committed values (satisfies: R-1, R-4).
- [ ] Committed team config + external user config with a different
  `integration_mode`: external wins, and `aet setup verify` shows which
  source won (satisfies: R-4, R-7).
- [ ] Repo containing only the legacy `.agents/aet-work.json`: any
  config-reading command fails closed naming `aet configure --migrate`;
  running it renames the file (preserving contents and git tracking) and
  subsequent commands resolve the migrated values (satisfies: R-1).
- [ ] Fresh project, run the guided setup, choose shadow + single-pr: the
  external config file exists with valid values, the repo tree has no AET
  config, and `aet setup verify` shows the resolved mode (satisfies: R-11,
  R-3, R-7).
- [ ] The upgrade guide for this release exists in `docs/upgrades/`, is
  linked from the README upgrades table and the CHANGELOG, and a consumer
  following only it completes the migration (satisfies: R-8).
- [ ] `aet run --base feat/x` and `aet run-one --base feat/x` are accepted by
  the dispatcher and reach the orchestrator as the integration branch
  (satisfies: R-6).
- [ ] `aet configure --integration-mode bogus` is rejected at write time
  naming the legal values (satisfies: R-5).
- [ ] A consumer following only SKILL.md + CONVENTIONS.md + the upgrade
  guide can set up shadow mode and team mode without reading toolkit source;
  every command in those docs parses (satisfies: R-8, R-9, R-10).

## Technical Notes

- Config resolution lives in `src/aet/backends/factory.py`
  (`DEFAULT_CONFIG_PATH`, `resolve_config`, `resolve_integration_mode`);
  branch resolution in `src/aet/branch_ref.py`; slug derivation in
  `src/aet/project_id.py` (`derive_project_slug` — the worktree label is
  added at lines 64-66; R-3 needs a config-specific identity that skips the
  label, not a change to the shared function's telemetry consumers).
- The `--base` Typer option exists only on the orchestrator's internal CLI
  (`src/aet/cli/orchestrator.py:3090-3094`); the dispatcher
  (`src/aet/cli/main.py:280-334`) must accept and forward it.
- `aet configure-backend` (`src/aet/cli/configure_backend.py`) already writes
  `task_backend` to in-tree or external (`--external-config`). R-5 extends
  this surface; whether it stays `configure-backend` or becomes
  `aet configure` is an open question below, not a new resolver.
- Consistency with prior decisions (validate-scope checklist):
  - ewl-07 / ADR-022: external-first precedence is *preserved* (R-4); the
    committed team file is optional, never required — the "nothing required
    in the client repo" bar (R-9/R-10 of the P3 PRD) still holds via the
    external path.
  - ADR-044: `integration_branch` remains per-run input; the committed file
    carries team-wide keys (`task_backend`, `trunk_branch`,
    `integration_mode`), not the per-epic branch.
  - ADR-045: engine mechanics untouched.
  - ADR-039 (CLI taxonomy): any command rename follows the atomic alias-free
    rule.
- Structural change to the toolkit → requires an ADR in `docs/adr/`
  (AGENTS.md mandate) covering the rename, the two-layer model, and the
  resolution anchoring.
- Existing test anchors: `tests/backends/test_integration_mode_config.py`
  (resolver chain), `tests/orchestrator/test_pr_per_task_unchanged.py`
  (default-mode regression), `tests/ship/test_epic_merge_verification.py`.

## Open Questions

- **Command naming for R-5:** extend `aet configure-backend` with the new
  keys and a `--scope project|user` flag (minimal surface, slightly stale
  name), or atomic-rename to `aet configure` per ADR-039? Recommendation:
  rename to `aet configure` — the command stops being backend-only the
  moment it writes `integration_mode`.
- **Old-file detection scope (R-1):** fail closed on *any* config-reading
  command when only the legacy file exists, or only warn? Recommendation:
  fail closed — a warning scrolls past in agent-driven runs and the failure
  mode (silent trunk-based) is exactly what this PRD exists to kill.

## Risks

- **Rename breakage for existing installs.** Any consumer with
  `.agents/aet-work.json` breaks loudly on upgrade. Mitigation: R-1's error
  names the one-line fix; R-8's upgrade guide covers it; the blast radius is
  small (feature is weeks old, config file is rare in the wild).
- **Slug change confusion (R-3).** A config-specific identity that differs
  from the telemetry slug could confuse future readers. Mitigation: keep the
  shared `derive_project_slug` untouched; add a clearly-named
  config-resolution identity beside it, with a comment naming the telemetry
  split as deliberate.
- **Docs/skills drift again.** R-9/R-10 fix today's docs but nothing
  prevents recurrence. Mitigation: acceptance criterion that every documented
  command parses; the docs lint surface (`aet docs lint`) gains rules only if
  the plans find a cheap mechanical check — otherwise left as process.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible
  defect. (Verified consumer pain is a discoverability/design gap in shipped
  behavior, not a crash or incorrect computation in existing code paths.)

## Divergence Summary

*Recorded: 2026-07-24 — Branch: cfg-01-config-resolution-overhaul*

The implementation branch delivered the config-resolution mechanics (R-1 through R-4 and the `--migrate` remedy) but deferred the broader CLI, docs, and skill surface work to a follow-up cycle.

### Changed from plan

- None — the plan.md scope was implemented as written.

### Added (unplanned)

- None.

### Deferred

- **R-5 (CLI writer for all config keys):** `aet configure` currently only writes `task_backend`; `--integration-mode`, `--trunk-branch`, `--integration-branch`, and `--scope project|user` remain to be added.
- **R-6 (`--base` forwarding):** `aet run` / `aet run-one` do not yet accept or forward `--base` to the orchestrator.
- **R-7 (resolved config inspection):** `aet setup verify` was updated to the new filename only; it does not yet print resolved mode/branches with provenance.
- **R-8 (shadow mode docs + upgrade guide):** No `docs/upgrades/` guide or README/CHANGELOG links were added.
- **R-9 (skill surface updates):** `aet-work` and `aet-ship` SKILL.md files were not updated to describe both integration modes or remove stale `task_backend: github` claims.
- **R-10 (doc command accuracy):** CONVENTIONS.md typo fix and `aet ship close --target-branch` documentation were not addressed.
- **R-11 (guided first-time setup):** The setup flow does not yet ask scope/mode questions and write a valid config.

---

*Stage: synced*
*Next step: run `aet-ship`*
