# PRD: AET Package Extraction & Repository Reorganization

## Overview

The `aet` CLI outgrew the skill directories it lives in. Today its code is
fragmented across four skills (`aet-work/bin` + `lib` + `panel`, `aet-ship/bin`,
`aet-evolve/bin`, `aet-setup/bin` + `lib`) plus root `tests/` and `scripts/`,
held together by `sys.path` hacks and an exec-based multicall dispatcher. This
PRD covers **Track A** of
[docs/roadmaps/aet-package-extraction-roadmap.md](../roadmaps/aet-package-extraction-roadmap.md):
extract the tool into a real Python package (`src/aet/`), move skills to
`skills/` as pure content, and adopt real dependencies where they replace
hand-rolled machinery — all behavior-preserving until the dependency-adoption
phase, and with no distribution changes.

**Intake triage:** feature/reorganization, not a reproducible defect. No
unexpected behavior in existing code is being fixed; structure is being
corrected.

## Goals

- **G1**: The tool is one Python package — no Python files inside any skill
  directory, no `sys.path` import hacks, tests import the installed package
  (R-2, R-3, R-4).
- **G2**: Skills are pure content under `skills/` — the validator enforces it,
  and the current `npx skills add ... --all` install path keeps working (R-5).
- **G3**: Hand-rolled formats/protocols/UI are replaced by maintained
  dependencies, each as an independently shippable, behavior-preserving change
  (R-6, R-7, R-8, R-9).
- **G4**: The decision record is honest — ADRs supersede the stale
  "markdown-only", "no runtime deps", and ADR-016 layout-caveat decisions
  before code moves (R-1).

## Non-Goals

- **No distribution work (Track B):** no CI/release pipeline, no PyPI
  publishing, no curl installer, no auto-update channel, no `aet skills`
  lifecycle commands, no deprecation of `npx skills add`. "No CI" stays in force.
- **No behavior changes to wrapped commands** in the extraction phases (A0–A3,
  A5). The dependency-adoption items (A4) are behavior-preserving refactors too.
- **No new CLI capabilities** (no new subcommands, no `--json` additions, no
  panel features).
- **No skill ID renames** and no SKILL.md content changes beyond path/link
  updates required by the `skills/` move.
- **No changes to `.agents/` workflow infrastructure** beyond what the layout
  change strictly requires.
- **No consolidation of repo-maintenance scripts into the CLI** beyond A5's
  split/archive decision.

## Requirements

- **R-1**: Three ADRs are recorded before any code moves: (a) the repo is
  content + Python package (supersedes "markdown-only repo"); (b) runtime
  dependency policy — stdlib for glue, dependencies for formats, protocols,
  and UI (supersedes "no runtime dependencies"); (c) directory layout change
  (amends ADR-016's "not changing the directory layout" caveat and explicitly
  reverses roadmap-p2's "no merging of binaries into one Python program"
  non-goal). `AGENTS.md`'s decision log is updated to match.
- **R-2**: All tool Python code lives in an installable package at `src/aet/`
  with a `pyproject.toml` (setuptools or hatchling backend). Sources:
  `aet-work/bin/*`, `aet-work/lib/*`, `aet-work/panel/*`, `aet-ship/bin/ship`,
  `aet-evolve/bin/*`, `aet-setup/bin/*`, `aet-setup/lib/harness_guard.py`.
  `pip install -e .` works; a console entry point provides `aet`.
- **R-3**: Extraction is behavior-preserving: every existing `aet <subcommand>`
  works identically from an editable install, `make validate` passes, and the
  full pytest suite passes. Zero `sys.path.insert` hacks remain in tool code.
  The multicall dispatcher may survive this phase as a thin compatibility
  layer over real package imports.
- **R-4**: The test suite imports the package (`from aet... import`) with no
  `sys.path` manipulation in `tests/conftest.py`; `tests/` is reorganized by
  domain mirroring the package layout; dev dependencies move from
  `requirements-dev.txt` into a `pyproject.toml` optional-dependencies group.
- **R-5**: All skill directories live under `skills/`; skill directories
  contain no executable code (markdown + static assets only), enforced by a
  new `validate-skills.sh` rule; `Makefile` (`install-skills`, `add-skill`),
  `skills-lint`, and test fixtures are updated; `npx skills add ... --all`
  discovery is verified working against the new layout.
- **R-6**: Hand-rolled YAML frontmatter parsing (`plan_parser.py`) is replaced
  by PyYAML with no behavior change (same accepted/rejected inputs, proven by
  the existing plus migrated parser tests).
- **R-7**: Hand-rolled file locking (queue, worktree) is replaced by the
  `filelock` package with no behavior change, including stale-lock behavior.
- **R-8**: The 19 argparse binaries are consolidated into one Typer (or Click)
  application; the multicall exec-dispatch and `SUBCOMMANDS` spec are deleted;
  `skills-lint` validates documented `aet` invocations against the real new
  parser tree (preserving ADR/roadmap-p2's reality-gap gate, G2 therein).
- **R-9**: The panel server is moved off raw `BaseHTTPRequestHandler` onto a
  small framework; the panel's routes, JSON API shape, and static page are
  unchanged (existing `.mjs` panel tests pass).
- **R-10**: `scripts/` is split by audience: repo-maintenance scripts stay;
  one-off data migrations are archived (or folded into the package as
  `aet migrate`, decided at plan time).
- **R-11**: Documentation stays truthful throughout: `README.md` skill table,
  `docs/CONVENTIONS.md` project-structure section, and `AGENTS.md` directory
  structure/tooling sections are updated in the same change that moves the
  things they describe.

## User Stories

- As a toolkit maintainer, I want all tool code in one installable package so
  that imports, tests, and refactors work like normal Python engineering
  (satisfies: R-2, R-3, R-4).
- As a toolkit maintainer, I want skills to be pure content under `skills/` so
  that the validator's model is simple and skill authoring conventions stop
  mixing prompts with runtime code (satisfies: R-5).
- As a toolkit maintainer, I want YAML parsing, locking, CLI parsing, and HTTP
  serving handled by maintained libraries so that hand-rolled machinery stops
  being a bug factory (satisfies: R-6, R-7, R-8, R-9).
- As a user of the toolkit, I want `aet <subcommand>` and `npx skills add` to
  keep working exactly as before through the reorganization so that my
  installed workflows never break (satisfies: R-3, R-5).
- As a future contributor, I want ADRs explaining why the repo stopped being
  "markdown-only" so that the decision log matches reality (satisfies: R-1).

## Acceptance Criteria

- [ ] `find skills/ -name "*.py"` (and `bin/`, `lib/`, `panel/` code dirs)
  returns nothing; `grep -rn "sys.path.insert" src/` returns nothing
  (satisfies: R-2, R-3, R-5).
- [ ] `pip install -e . && aet status` (and every other existing subcommand)
  behaves identically to the pre-extraction dispatcher (satisfies: R-3).
- [ ] `make validate` (lint-py + workflow lint + skills-lint + skill-structure
  validator + pytest) is green after each phase, including the `skills/` move
  (satisfies: R-3, R-4, R-5).
- [ ] A fresh `npx skills add <repo> --all` install against the new layout
  discovers and installs all skills (manual verification, documented in the
  A3 plan) (satisfies: R-5).
- [ ] Parser, locking, and panel behaviors are covered by tests that pass
  before and after each dependency swap (satisfies: R-6, R-7, R-9).
- [ ] `aet --help` output is generated by the new CLI framework and lists the
  same subcommands; `skills-lint` passes against the new parser tree
  (satisfies: R-8).
- [ ] Three merged ADRs exist and `AGENTS.md`'s decision log no longer claims
  "markdown-only repo" or "runtime code has no Python dependencies"
  (satisfies: R-1).

## Technical Notes

- **Layout:** standard src layout — `src/aet/` (package), `tests/`, `skills/`,
  `scripts/`, `docs/`, `.agents/`. Import package name: `aet`.
- **Phasing** (from the roadmap): A0 ADRs → A1 package extraction
  (behavior-preserving, no new deps) → A2 test modernization → A3 `skills/`
  move → A4 dependency adoption (independent items) → A5 scripts split.
  A3 is hard-blocked by A1 (no code may live in skills before they move).
- **Dispatcher strategy:** A1 keeps the multicall dispatcher as a thin compat
  layer so the CLI surface never breaks mid-migration; A4's Typer
  consolidation deletes it.
- **Installer caution (learning 2026-07-15):** `aet install` run from inside a
  worktree once re-pointed the global `~/.local/bin/aet` symlink at ephemeral
  paths. Extraction touches installer logic — the existing isolation fixtures
  (`AET_BIN_DIR`/`AET_SKILLS_DIR` per-test tmp dirs) must keep covering every
  spawn site after the move.
- **Conflict to resolve in scope validation:** roadmap-p2 (merged) declared
  "no merging of binaries into one Python program; exec dispatch only" as a
  non-goal. The A0 layout ADR must explicitly supersede that stance.
- **Reality-gap gate:** roadmap-p2's skills-lint validation of documented `aet`
  invocations against the real parser tree must survive the R-8 consolidation —
  the lint target changes, the gate does not.
- **Dev environment:** `uv` is acceptable for local tooling but must not become
  a runtime requirement in Track A; plain `pip install -e .` must work.

## Open Questions

- Typer vs. Click for R-8 — decide at A4 plan time (Typer preferred for
  type-hint-driven UX; either satisfies the requirement).
- `aet migrate` subcommand vs. archived scripts for R-10 — decide at A5 plan
  time.
- Whether `scripts/test-*.sh` and `scripts/test-*.py` migrate into `tests/` or
  stay as repo-maintenance scripts — decide at A5 plan time.

## Risks

- **Installer self-repair regressions** touching the user's real PATH during
  tests (see learning above) — mitigated by keeping isolation fixtures
  mandatory and behavior-preserving phasing.
- **`npx skills add` discovery breakage** after the `skills/` move — mitigated
  by verifying discovery in the A3 plan before the move is considered done
  (R-5 acceptance criterion).
- **Large mechanical diff colliding with open worktrees/branches** — mitigated
  by phasing (A1 lands before A3) and by rebasing independent branches onto
  `origin/main` per existing guardrails.
- **Dependency supply-chain scope creep** in A4 — mitigated by one dependency
  per plan, each with its own security review (vgr-04 precedent: first
  third-party dependency required one).

---

*Stage: scope-validated*
*Next step: run `aet-work` (single-plan or multi-task queue)*
