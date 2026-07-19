# Roadmap: AET Package Extraction & Repository Reorganization

**Status:** Active — Track A in planning, Track B deferred
**Created:** 2026-07-19
**Context:** The `aet` CLI outgrew the skills it lives in. Today the tool's code is
fragmented across four skill directories (`aet-work/bin` + `lib` + `panel`,
`aet-ship/bin`, `aet-evolve/bin`, `aet-setup/bin` + `lib`) plus root `tests/` and
`scripts/`. Skills are content; the tool is runtime. This roadmap separates them.

## Decision Summary (agreed 2026-07-19)

1. **The tool becomes a real Python package.** The "zero runtime dependencies"
   decision is dropped. Dependencies are allowed where they replace hand-rolled
   formats/protocols/UI (YAML, locking, CLI framework, HTTP). Stdlib remains fine
   for glue.
2. **Distribution moves to an `aet`-centered model later** (curl installer,
   auto-updatable CLI, skills bundled as package data). Valuable, not needed now.
   `npx skills add ... --all` remains the install path until Track B lands.
3. **Skills move to `./skills/`** as part of Track A, once no code lives inside
   skill directories anymore.

## Superseded / Affected Decisions

| Decision | Where | Fate |
| --- | --- | --- |
| "Markdown-only repo" | `AGENTS.md` decision log | Supersede (ADR) — repo is content + Python package |
| "Runtime code has no Python dependencies" | `AGENTS.md` decision log, `requirements-dev.txt` | Supersede (ADR) — real deps allowed, declared in `pyproject.toml` |
| ADR-016 "not changing the directory layout" | `docs/adr/016-*.md` | Amend (ADR) — layout now changes; distribution narrative unchanged until Track B |
| "No CI" | `AGENTS.md` decision log | **Unchanged for now** — revisited in Track B |

---

## Track A — Reorganization (current)

Phases are sequential; each phase decomposes into atomic plans in `docs/plans/`
via the normal PRD/plan pipeline before implementation.

### Phase A0 — Decision records

Write the ADRs that legitimize everything below. Docs-only, cheap, unblocks the rest.

- [ ] ADR: repo is content + Python package (supersedes "markdown-only")
- [ ] ADR: runtime dependencies policy (supersedes "no runtime deps"); principle:
      stdlib for glue, dependencies for formats, protocols, and UI
- [ ] ADR: directory layout change (amends ADR-016 caveat)

**Done when:** ADRs merged; `AGENTS.md` decision log updated to point at them.

### Phase A1 — Package extraction (behavior-preserving)

Move the tool into a `src/aet/` package with `pyproject.toml`. **No behavior
change, no new dependencies in this phase** — pure relocation.

- [ ] `pyproject.toml` with console entry point(s); editable install works
      (`pip install -e .` / `uv pip install -e .`)
- [ ] `aet-work/lib/*` → `aet/` core modules (queue, backends, telemetry,
      breaker, workflow, verifier, plan parsing, ...)
- [ ] `aet-work/bin/*` → `aet/cli/` subcommand modules; multicall dispatcher kept
      as thin compatibility layer during transition
- [ ] `aet-ship/bin/ship`, `aet-evolve/bin/*`, `aet-setup/bin/*`,
      `aet-setup/lib/harness_guard.py` → corresponding `aet/cli/` / `aet/` modules
- [ ] `aet-work/panel/` → `aet/panel/`
- [ ] All `sys.path.insert` hacks deleted; real package imports
- [ ] `make validate` green; `aet install` and all subcommands work from an
      editable install exactly as before

**Done when:** no Python file remains inside any skill directory; the full test
suite passes unmodified in behavior (import paths may change).

### Phase A2 — Test suite modernization

- [ ] `tests/conftest.py` `sys.path` hack removed; tests use `from aet... import`
- [ ] `tests/` reorganized by domain mirroring the package (e.g.
      `tests/backends/`, `tests/telemetry/`, `tests/cli/`)
- [ ] Dev dependencies moved from `requirements-dev.txt` into
      `pyproject.toml` optional-dependencies group

**Done when:** `make test` and `make validate` green with zero path hacks.

### Phase A3 — Skills move to `skills/`

Only possible after A1 (no code inside skills). Content-only relocation.

- [ ] All `aet-*/` skill directories move to `skills/aet-*/`
- [ ] `scripts/validate-skills.sh` updated; new rule: skill directories contain
      no executable code (markdown + assets only)
- [ ] `Makefile` (`install-skills`, `add-skill`), `skills-lint`, test fixtures updated
- [ ] `README.md` skill table, `docs/CONVENTIONS.md` project-structure section,
      `AGENTS.md` directory-structure section updated
- [ ] Cross-skill relative links verified by the validator

**Done when:** repo root shows `skills/`, `src/`, `tests/`, `scripts/`, `docs/`,
`.agents/`; `npx skills add ... --all` discovery confirmed still working;
`make validate` green.

### Phase A4 — Dependency adoption (incremental, one plan per item)

Each is an independent atomic plan; order by pain, not by list position.

- [ ] PyYAML replaces hand-rolled frontmatter/YAML parsing (`plan_parser.py`)
- [ ] `filelock` replaces hand-rolled queue/worktree locking
- [ ] Typer (or Click) consolidates the 19 argparse binaries; multicall
      dispatcher and `SUBCOMMANDS` exec-dispatch deleted
- [ ] Panel server moved off raw `BaseHTTPRequestHandler` onto a small framework

**Done when (per item):** hand-rolled implementation deleted, tests green,
behavior unchanged.

### Phase A5 — Scripts cleanup

- [ ] `scripts/` split: repo-maintenance (`validate-skills.sh`, `skills-lint`,
      `test-*.sh`) vs. one-off migrations (`migrate-*.py` — archive or fold into
      the package as `aet migrate`)

---

## Track B — Distribution (deferred)

Not scheduled. Captured here so the design direction isn't lost; each bullet
becomes a PRD when Track B opens.

- ADR superseding "No CI"; release pipeline (tag → build → publish PyPI/GitHub
  Releases, checksums)
- Skills bundled as package data, versioned with the CLI (kills version skew by
  construction); `aet install` materializes skills into agent skill dirs,
  `--dev` mode symlinks from a working tree
- Bootstrap installer: `curl -fsSL <domain>/install.sh | bash` → bootstraps
  `uv` → `uv tool install aet` → `aet install`
- Update channel design: auto-check + nag vs. silent auto-update (CLI vs. skill
  content may warrant different policies); `aet update` / `aet doctor`
- `aet skills` lifecycle commands (`list` / `add` / `update` / `remove`),
  replacing `npx skills add` including third-party skill sources
- Migration path: detect and replace npx-style installs and repo symlinks
  (legacy-pruning logic already exists in the dispatcher)
- Open question to settle early in Track B: PyPI package name and a stable
  domain for the install script

---

## Status Tracker

| Phase | State | Notes |
| --- | --- | --- |
| A0 — ADRs | pending | Docs-only; start here |
| A1 — Package extraction | pending | Blocked by A0 |
| A2 — Test modernization | pending | Blocked by A1 |
| A3 — Skills move | pending | Blocked by A1 |
| A4 — Dependency adoption | pending | Blocked by A1; items independent |
| A5 — Scripts cleanup | pending | Independent; any time after A1 |
| B — Distribution | deferred | See Track B |
