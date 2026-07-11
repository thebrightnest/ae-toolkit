# Brief: The `aet` Binary — One Entry Point, Linted Skills (Roadmap Phase 2)

## Problem

The toolkit's operational surface is scattered. `aet-work` (frh-05) dispatches only its own family — seven queue commands plus `run`/`run-one` — while `aet-state`, `orchestrator`, `aet-retro`, `mine-learnings`, and `configure-task-backend` occupy their own PATH names and `ship` is path-invoked (`aet-ship/bin/ship`). Doc 01 critical issue 3 (PATH pollution / missing dispatcher) is only half-retired. The bootstrap is its own wound: the standalone `install-aet-binaries` script confused the owner multiple times (gate feedback, 2026-07-11) — a rarely-run manual step whose omission surfaces much later as `command not found`. Worse, nothing checks that skill prose matches the real CLI surface — the #1 systemic wound (docs↔code reality gap). The cli_adapter fake-flag incident (learnings 2026-06-11: three declared flags that no binary accepted) needed a production failure to surface. Skills are the API docs agents execute; today they can drift from the binaries with zero signal until an agent runs a command that does not exist.

## Context

- Roadmap: `content/fable-review/09-2026-07-10-roadmap.md`, Phase 2 (~3 tasks). Exit gate: _no skill references a legacy entry point; skills-lint green in CI; deleting the old bin names breaks nothing._
- ADR-020 names the destination: sequencing is enforced by "the CLI layer (today `aet-work`/`aet-state`; destination: the single `aet` binary)".
- Doc 06 step 3: the wrap is mechanical — "orchestrator becomes `aet run`, state becomes `aet state …`". Doc 06 P5: a **skills-lint** parses every documented invocation against the real argparse tree, turning the reality gap from cultural discipline into a merge failure.
- Repo ground truth at `f50d7b4`: the frh-05 dispatcher exists (`aet-work/bin/aet-work`, exec-based); `aet-ship/bin/ship:31` already resolves siblings via the skills root; all twelve operational binaries are argparse programs; `bin/status` has no `--json`; runtime hints still teach legacy names (`aet-work/lib/queue.py:397` says "run `aet-state audit`"); the installer (`aet-setup/bin/install-aet-binaries`) links/prunes per an allowlist. CI is `make validate` (+ pre-commit); P1's workflow lint (wfd-04) lands there too.
- Phase ordering: every P2 task is downstream of `wfd-04-workflow-lint-variant-proof` via `blocked_by` — P1's exit gate is the phase boundary, enforced by the queue itself, as in P0 → P1.

## Requirements

- **R-1**: A single `aet` multicall binary (`aet-work/bin/aet`) dispatches every operational toolkit command as a subcommand: queue/board (`add`, `review`, `status`, `next`, `sync`, `report`, `init-queue`), execution (`run`, `run-one`), state (`state <audit|heal|validate|transition|set-stage|record-merge>`), closure (`ship`), learning (`retro`, `mine-learnings`), config (`configure-backend`), setup (`install`). Dispatch is exec-based 1:1 wrapping of the existing binaries — no behavior change; no argument re-parsing beyond the existing documented `run`/`run-one` mappings (default queue file; plan-file positional); all other args forward verbatim. `install` is the one subcommand implemented inside `aet` itself (R-5).
- **R-2**: Cross-skill targets resolve via the installed-skills layout (resolved script path → skills root → sibling skill `bin/`), the pattern `ship:31` already uses. A missing sibling fails with a clear error naming the skill to install; an unknown subcommand exits 2 with a usage listing.
- **R-3**: The subcommand → target-binary table is a declarative, importable spec inside the `aet` binary, so tooling (skills-lint) validates against the same source of truth the dispatcher executes.
- **R-4**: `aet status --json` emits machine-readable queue status (documented, stable keys: per-task id/state/stage/blockers plus summary counts); human output and exit codes unchanged. This is the seam future read-only consumers (`aet desk`, any UI) build on.
- **R-5**: The end-state PATH surface is exactly one name: `aet`. `aet install` absorbs `install-aet-binaries`: it links `aet` into `AET_BIN_DIR` (default `~/.local/bin`), prunes all seven AET-managed legacy symlinks (`aet-work`, `aet-state`, `aet-retro`, `orchestrator`, `mine-learnings`, `configure-task-backend`, `install-aet-binaries`), and warns when the bin dir is missing from PATH — editing shell profiles stays manual, the one honest bootstrap step. The standalone `aet-setup/bin/install-aet-binaries` script is deleted; `aet-setup` prose and the Makefile bootstrap by path (`<skills-root>/aet-work/bin/aet install`). No alias, no shim, no deprecation window (owner decisions at the gate, 2026-07-11). Deletion and pruning ship in the final task of the phase (flip); until then the old names stay untouched and fully functional so every intermediate merge stays green.
- **R-6**: Every wrapped binary exposes its ArgumentParser via a `build_parser()` function (`parse_args` refactored to call it); behavior identical. This is what makes "parse against the real argparse tree" literal rather than aspirational.
- **R-7**: skills-lint v1 (`scripts/skills-lint`, wired into `make validate`): extracts every `aet …` invocation from code spans (fenced blocks and inline code) in packaged skill markdown (`aet-*/**/*.md`) and project scaffolding (`.agents/templates/*.md`, `.agents/commands/*.md`, `AGENTS.md`), and validates each against the real parser tree — unknown subcommand or unknown flag fails the build. Placeholder tokens (`<…>`, `{…}`, `…`, `$VARS`) are treated as opaque values. An explicit escape marker pair (`<!-- aet-lint: off -->` / `<!-- aet-lint: on -->`) exempts deliberately historical content (e.g. migration docs).
- **R-8**: skills-lint also fails on any legacy entry-point reference in linted files: command-position `aet-work`, `aet-state`, `orchestrator`, `aet-retro`, `mine-learnings`, `configure-task-backend`, `install-aet-binaries`, or `aet-*/bin/…` path invocations — except paths ending in `aet-work/bin/aet` (the binary itself; by-path bootstrap invocations are `aet` invocations and are lint-validated like any other) and escape-marked blocks. The rule ships warn-only and flips to error in the rewrite task — from then on it _is_ the "deleting the old names breaks nothing" gate, standing in CI.
- **R-9**: Every reference is rewritten to the `aet` surface — skill SKILL.md files, `references/` docs, `.agents/templates/`, `.agents/commands/`, `AGENTS.md`, `README.md`, `docs/CONVENTIONS.md` — and the runtime hint strings printed by the binaries themselves (e.g. `queue.py:397`) say `aet …`, so agents are never taught a legacy name at runtime.
- **R-10**: Tests: dispatcher routing (each subcommand reaches its target; run/run-one mapping; missing-sibling error; unknown subcommand exit 2), `aet install` behavior (fresh link, stale-link repair, legacy prune, idempotency — against a temp bin dir), self-repair on invocation, `build_parser()` importability for all twelve bins, `status --json` schema assertions, and skills-lint fixtures (valid invocation passes; unknown subcommand/flag fails; legacy name fails when strict; escape marker skips). `make validate` green demonstrates the exit gate mechanically.
- **R-11**: `aet` is self-maintaining on PATH: every invocation cheaply verifies its own symlink (one readlink) and silently repairs a missing or stale link, so toolkit updates never require re-running an installer — new subcommands dispatch internally and travel with the file. Multi-checkout resolution keeps today's semantics: the copy invoked wins; `AET_SKILLS_DIR`/`AET_BIN_DIR` override for dev. Repair never edits shell profiles and never touches non-AET files.

## Non-Requirements

- No merging of the binaries into one Python program — exec dispatch preserves behavior byte-for-byte and each binary stays independently testable; consolidation remains possible later behind the stable surface.
- No new capabilities behind subcommands: no `aet gate submit` / `aet hooks install` / git-refs default flip (Phase 3), no `aet desk` / `aet plan validate` (Phase 4), no adapters / `aet doctor` (Phase 6), no `aet eval` (Phase 7).
- No behavior change to any wrapped command except adding `status --json` (R-4) and hint-string text (R-9).
- skills-lint v1 is syntactic (documented invocations parse), not behavioral — agents obeying skills under pressure is `aet eval`, Phase 7.
- Repo-CI scripts (`validate-workflows`, `skills-lint`, `validate-skills.sh`) are make-internal tooling, not `aet` subcommands.
- No packaging, distribution, or rebrand: run-from-checkout symlinks remain dev mode (memory: `aet-skills-symlinked-live`); the naming question re-opens at Phase 8 distribution, not before (doc 06 open question; doc 09).
- No daemon; no MCP server.

## Rejected Alternatives

- **One monolithic Python CLI** (argparse subparsers importing all libs) — rejected: forces merging twelve binaries' import graphs and error handling in one step; doc 06 step 3 calls the wrap "mechanical," and exec dispatch keeps every merge behavior-preserving. Consolidation stays open behind the stable surface.
- **A deprecated `aet-work` alias through a transition window** — rejected by the owner at the gate (2026-07-11): no backward-compatibility shims; upgrade fully. Other AET-consuming repos re-run `aet-upgrade`/`aet install` instead of leaning on an alias; the old dispatcher file dies in the same merge that removes its last reference, so no half-alive name survives the phase.
- **Keeping a standalone installer script** — rejected (owner gate feedback: it confused multiple times). Link management belongs inside the binary that owns the link: one name needs no fleet-linking machinery, and self-repair on invocation removes the "forgot to re-run it" failure mode entirely.
- **Auto-editing shell profiles to put the bin dir on PATH** — rejected: silently mutating user shell config is the wrong kind of magic; a one-line warning with the exact export line is the honest interface.
- **Lint via `--help` text parsing or a hand-maintained spec file** — rejected: help-text parsing is fragile; a separate spec is a second source of truth that drifts — drift is the disease being treated. Import and introspect the real parsers (R-3, R-6).
- **Lint all repo markdown** (docs/, content/) — rejected: the fable-review corpus and historical docs legitimately quote old and future command shapes; the exit gate says _skills_. Scope = packaged skill content + project scaffolding.
- **A new `aet-cli/` skill directory** — rejected: the engine (libs, queue, orchestrator) lives in `aet-work`; a separate home adds cross-skill imports for zero benefit. The identity shift (orchestrator becomes a subcommand) is in the command surface, not the directory layout.
- **Single big-bang task** — rejected: additive-then-flip sequencing (binary lands → parsers exposed → lint lands warn-only → rewrite + flip + prune) keeps every intermediate merge green while skills still work.
- **Wrapping the repo-CI scripts as subcommands** — rejected: they have no operational consumer in projects; wrapping grows the frozen surface for nothing.

## Success Signal

The roadmap's P2 exit gate, machine-checked: every skill invokes `aet …` exclusively; `make validate` runs skills-lint green with the legacy rule at error severity, so reintroducing an old name fails the merge; PATH carries exactly one AET name — `aet`, self-linking and self-repairing — with the old dispatcher and the standalone installer deleted. The old bin names aren't merely deletable, they are deleted, and nothing breaks because nothing references them.

---

_Stage: brief_
_Created: 2026-07-11_
_Traces forward to: `docs/prds/roadmap-p2-aet-binary-prd.md`_
