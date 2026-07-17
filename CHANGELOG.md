# Changelog

## [1.2.0] — 2026-07-17

### Added

- **Night-shift runtime resilience suite** — Phase 5 adds per-task and systemic circuit breakers, a stall watchdog on event silence, failure-taxonomy classification, `--on-failure=triage` requeue/quarantine routing, a quarantined task state, and per-task cost rollup to the ledger (nsr-01…07).
- **Phase 5 exit-gate rehearsal** — end-to-end unattended rehearsal that injects failure and stall scenarios and verifies the orchestrator routes them correctly (nsr-07).
- **`aet plan validate` four-family check suite** — validate plans against structure, scope, dependency, and traceability rules from the CLI (twe-04).
- **Intake fail-closed gates** — `aet add`, `init-queue`, and `sync` now run the plan-validate suite and reject malformed plans at intake (twe-05).
- **Zero-review mechanism** — optional auto-merge eligibility based on track-record, with `desk --eligibility`, policy configuration, and an orchestrator hook; off by default (twe-06).
- **`aet desk` risk-ranked awaiting-merge view** — sort tasks by risk and bundle merge evidence for easier ship decisions (twe-02).
- **`aet desk` actions** — merge and abandon tasks directly from the desk TUI (twe-03).
- **Per-provider merge-guard harness** — detect provider-specific merge guards and adapt ship behavior, starting with a Claude adapter (twe-09).
- **Work-class plan attribute** — plans now record `work_class` and intake validates it, enabling richer routing and risk scoring (twe-01).
- **Phase 4 exit-gate rehearsal** — end-to-end rehearsal with an audit doc capturing the unattended run evidence (twe-07).
- **Autonomous-merge governance** — documented fail-closed governance and ship merge-neutral hygiene for future auto-merge paths (twe-08).

### Changed

- **Validation-freshness guard** — `aet gate submit` now stamps `tree_hash` before validating the submit payload, preventing stale verdicts from being accepted.
- **Worktree-aware install tests** — `aet install` tests now pass when invoked from inside a git worktree.

### Documentation

- Added Phase 4 and Phase 5 plan sets and PRDs (twe-01..09, nsr-01..07).
- Synced multiple plans to implementation reality after closure.

---

## [1.1.0] — 2026-07-15

### Added

- **Live-run panel** — `aet-work` exposes live-run visibility with a dirs API, honest status, and a panel that auto-refreshes every 5 seconds with incremental dir merging and tab-visibility-aware polling (lvp-01/02).
- **Usage-cost telemetry** — parses kimi wire files and captures agent CLI usage into the telemetry archive, with a cost view in the telemetry panel (uct-01).
- **`aet gate submit` verdict writer** — record skill verdicts directly from the CLI so the orchestrator can gate completion on structured evidence (ewl-01).
- **Pre-push hook gate** — `aet-setup` can install and check a pre-push gate that blocks pushes until skill verdicts pass (ewl-03).
- **git-refs as default written backend** — `aet-work` now writes queue state to git refs by default, with backend sealing and a parity suite (ewl-04).
- **git-refs tamper-evidence** — git-refs backend gains tamper-evident mutations for trustworthy unattended state (ewl-05).
- **Non-invasive external config root** — support an external config root without invasive repository changes (ewl-07).
- **Validation freshness primitive** — verdicts carry a `tree_hash` and a validation-freshness query so stale evidence can be detected (pfe-01).
- **QA-freshness clause injection** — orchestrator stage prompts now inject QA-freshness requirements into each stage (pfe-02).
- **Wire-log test-run extraction** — extract structured `test_run` records from wire logs for richer telemetry (ttf-01).
- **Verdict-derived test_run scope classification** — classify `test_run` scope from verdicts with honest nulls when evidence is missing (ttf-02).
- **Structural pattern mining** — `mine-learnings` and `aet-retro` can surface recurring structural patterns across projects (ttf-03).

### Changed

- **Slimmer scaffolded gates** — `aet-setup` no longer scaffolds Prettier into the default gate set (vgr-05).
- **Faster test suite** — pytest suite is now parallelized with `pytest-xdist` (vgr-04).
- **Slim markdown quality gates** — `make validate` uses lighter markdown gates and fails fast on the first problem (vgr-01).
- **Status command readability** — `aet-work status` renders the task list as a markdown table, shows only pending blockers, and prints a dependency table.

### Fixed

- **Global `aet` symlink safety** — worktree copies no longer hijack the global `aet` symlink (#116).
- **Untracked plan intake** — `aet-work` refuses untracked plans at `aet add` instead of silently accepting them.
- **Telemetry reader alignment** — `aet-retro` and `mine-learnings` readers are now aligned with the telemetry writer layout (tele-07).
- **Queue integrity recovery** — the queue integrity envelope is recoverable via audit/heal.
- **Integrity refusal cleanup** — cleaned up integrity refusals, hygiene sidecars, and foreground validations.

### Documentation

- Added ADR-026 documenting slim markdown quality gates (vgr-02).
- Added enforcement-walls adversarial rehearsal documentation (ewl-06).
- Added plan-durability hardening PRD and pdh-01/pdh-02 plans.
- Added usage-cost telemetry plan and ADR-025 on freshness.
- Added validate-gate-review PRD and vgr-01..05 plans.
- Recovered and landed telemetry-fidelity PRD and plans.
- Synced multiple plans to implementation reality after closure.

---

## [1.0.0] — 2026-07-12

**First stable release.** This is a major version bump: the legacy per-skill binaries are retired in favor of the unified `aet` multicall binary, which is a breaking change for any scripts or muscle memory that invoke the old binaries directly.

### Added

- **`aet` unified binary** — a single multicall dispatcher that routes to all toolkit subcommands, with an `aet install` subcommand and on-invocation PATH self-repair. Replaces the collection of separate legacy binaries (cli-01…05).
- **Machine-readable status** — toolkit bins expose `build_parser()` and a `status --json` output for scripted inspection (cli-02).
- **skills-lint invocation checker** — a new lint that validates skill invocation patterns (cli-03).
- **Workflow-as-data pipelines** — pipeline stage sequences are now declared in a packaged workflow file with a schema and loader, and plans route gated stages from YAML frontmatter (wfd-01…03).
- **Workflow lint** — `make validate` now lints workflow definitions, with a team-variant exit-gate proof (wfd-04).
- **Telemetry panel** — a local, stdlib-launched archive viewer with a Plans lens: plan model, tabs, plan list, and plan detail with a pipeline spine, consolidated timeline, and run chips (thp-05/06).
- **Telemetry retention pruning** — a prune CLI with active-run protection, a worktree-based project slug, and an archive slug migration helper (thp-02/03/04).
- **git-refs task backend** — `aet-work` can store task state in git refs as an alternative to the local JSON queue, with backend sealing and a parity suite (frh-13/14).
- **Curated sprint intake** — `aet-work` sync no longer auto-adds plans; intake parks them as ready or blocked for explicit curation (frh-15).
- **R-trace decision templates** — `aet-plan` gains requirement-traceability templates and prose, backed by ADR-020 and ADR-021 (rdm-01/02).

### Changed

- **aet-work orchestrator hardening** — locked, atomic queue writes; a tamper-evident mutation guard with a run lease; and evidence-gated task completion that requires a structured gate verdict (frh-01/02/10/11/17).
- **Live frontier batch exit** — the orchestrator widens the scheduling frontier and exits cleanly when idle instead of spinning (frh-16).
- **Process isolation** — batch children spawn in a new session and are killed by process group on timeout or shutdown (frh-03).
- **aet-retro telemetry** — now emits structured `learning_candidate` records for downstream mining (frh-12).
- **`make validate`** — wires pytest and ruff into the validation gate (frh-04).

### Fixed

- **Orchestrator false-completion** — the orchestrator now requires commits before marking a task complete and reconciles `pending_blockers` against settled history.
- **Verifier stage detection** — the verifier reads the footer stage instead of scanning body mentions.
- **Per-kind verdict paths** — verdicts are published to per-kind paths so stages read the correct evidence.
- **Worktree reuse** — `aet-work` reuses existing worktrees that are up-to-date or dirty instead of recreating them.

### Removed

- **Legacy skill binaries** — the many separate per-skill binaries are retired in favor of the `aet` multicall binary (cli-05).
- **Hardcoded pipeline module** — `pipeline.py` deleted; stage sequencing now lives in the workflow file (wfd-03).
- **Legacy status vocabulary** — retired from the queue library, read side, and state layer (frh-06/07).
- **Dead orchestrator layer** — removed unused dead code (frh-08).

### Documentation

- Added ADR-019, ADR-020, and ADR-021, and indexed the ADR set.
- Added PRDs and plan suites for fable-review hardening (frh-01…18), workflow-as-data extraction (wfd-01…04), the `aet` binary (cli-01…05), and telemetry hygiene & the plan-centric panel (thp-01…06).
- Added the p3 enforcement-walls plan set (ewl-01…06) and PRD; retired the abandoned ewl-02 plan while retaining its trail.

---

## [0.10.0] — 2026-07-09

### Added

- **aet-retro command** — `aet-evolve` now includes an automated run-review command that reads per-task telemetry archives and narrative reports to surface errors, performance issues, and actionable improvements after every `aet-work run`.
- **GitHub Issues task backend** — `aet-work` can now use GitHub Issues as the queue backend instead of local JSON files. Plans pushed to the queue become GitHub issues with labels, and state transitions sync bidirectionally.
- **Impact-scoped QA tests** — `aet-qa` defaults to tests that touch the changed files, with an exact fallback to the full suite when the scoped run does not cover every modified path.
- **Stage-failure triage checklist** — `aet-qa` adds a structured triage checklist for failures during plan, review, QA, or ship stages.
- **Review scope noise filter** — `aet-review` tightens its scope lens and adds a project-level noise filter so reviewers focus on the current change instead of unrelated project patterns.
- **Manual merge closure** — `aet-ship` and `aet-state` can close a task from a CLI-supplied branch or merge commit when a PR is merged outside the orchestrator.
- **Queue self-heal audit** — `aet-state heal` reconciles queued tasks against git ground truth and can repair stale state.
- **Testing strategy template** — `aet-setup` scaffolds a `docs/references/testing-strategy.md` example for new projects.

### Changed

- **aet-work orchestrator reliability** — per-task wall-clock timeout, inner heartbeat, and guaranteed cleanup/summary reporting replace the single outer-shell timeout.
- **Worktree freshness** — `aet-work` refreshes `origin/main` before creating or reusing a worktree, and rebases existing worktrees in place when `origin/main` advances.
- **Hygiene noise reduction** — queue mutations detected during hygiene checks are now informational instead of blocking, and plan-drift warnings are logged without halting the run.
- **aet-setup scaffolding** — `docs/references/` now includes a reference-README example, and the skill/checklist guide projects through the new docs scaffolding.

### Fixed

- **aet-work orchestrator crash** — eliminated `NameError: read_queue` by using the configured backend to load queue state.
- **Stale queue writes** — `aet-work` re-reads queue state after `aet-state` transitions to avoid overwriting concurrent updates.
- **Plan closure commits** — `aet-state record-merge` now auto-commits plan footer updates after merge verification.
- **Merged footer formatting** — plan merged footers use consistent underscore emphasis.
- **aet-retro telemetry source** — `aet-retro` reads per-task telemetry archives instead of the removed single `.agents/execution.log.jsonl`.
- **aet-evolve mine-learnings** — restored missing `sys` import.

### Removed

- **aet-discover skill** removed from the toolkit. Discovery workflows remain possible with `aet-plan` and manual product-definition artifacts.

### Documentation

- Added ADR-013 and the QES plan suite documenting the ephemeral sprint-board model.
- Added GitHub Issues task backend PRD and implementation plans.
- Updated `docs/CONVENTIONS.md` and skill guidance to describe the toolkit as a distributed system rather than individual skills.
- Added upgrade guides index and linked it from `README.md`.
- Documented retro learnings from the telemetry-driven skill hardening run.

---

## [0.9.1] — 2026-07-06

### Fixed

- **README**: installation commands now point to the correct repository (`https://github.com/thebrightnest/ae-toolkit`).
- **README**: `npx skills` examples use the `.agents/skills` standard path and omit `.git` from URLs.
- **README**: corrected AET binary installation instructions.

### Changed

- Removed accidentally committed presentation files from the repository.

---

## [0.9.0] — 2026-06-30

### Added

- **Direct telemetry archive** — the orchestrator writes per-task JSONL logs directly to `~/.aet/telemetry/{project-slug}/{date}/{run-id}/`, so telemetry survives project worktree deletion.
- **Per-task telemetry files** — each task writes to its own JSONL file, eliminating concurrent-write races on a shared project log.
- **Run completion status** — every orchestrator run writes a `last-run.json` summary with outcome, task counts, and wall-clock time.
- **Plan-level pipeline override** — plans can declare `pipeline: minimal|standard|full` in YAML frontmatter to control orchestrator isolation per task.

### Changed

- **aet-evolve**: `mine-learnings` now reads the dated archive layout directly; `ingest-telemetry` is no longer required.
- **aet-work**: `report` summarizes telemetry from the archive instead of `.agents/execution.log.jsonl`.
- **aet-plan**: plan frontmatter now documents the optional `pipeline` field.
- **aet-validate-scope**: validates `pipeline` frontmatter values when present.

### Removed

- **aet-evolve**: Removed `ingest-telemetry`; the orchestrator archives telemetry automatically at write time.
- **aet-work**: No longer creates `.agents/execution.log.jsonl`.

### Documentation

- Updated `docs/telemetry-guide.md` for the direct-archive flow.
- Added ADR-012 documenting the direct telemetry archive and per-task logs.

---

## [0.8.0] — 2026-06-22

### Added

- **Telemetry learning system** — six-part update that enriches the telemetry schema, warms worktree dependencies, reuses stage-group sessions, scopes tests to the diff, archives learnings across projects, and packages the whole flow. See `docs/telemetry-guide.md`.
- **aet-setup**: Centralized AET skill binary installation (`install-aet-binaries`) so skills expose their executables on `PATH` consistently.
- **aet-evolve**: `mine-learnings` now parses narrative markdown reports (QA, review, CSO, verification) in addition to structured JSONL records.

### Changed

- **aet-work**: `init-queue` now reconciles terminal state from `.agents/work-history.jsonl` and git, and reconciles plan footer stages on intake.
- **aet-work**: `sync` only validates candidate plans and tolerates legacy dependency sections in already-queued plans.
- **aet-state**: `record-merge` and `derive` now accept merge verification by `merge_commit` alone, removing the requirement for a local branch.

### Fixed

- **aet-work**: Skip main-hygiene check in batch-spawned children so unattended orchestrator runs don't deadlock on already-pulled `origin/main`.
- **Build**: `aet-work/bin/report` is now executable so the installer exposes it on `PATH`.

### Documentation

- Added `docs/telemetry-guide.md` with the telemetry ingestion, archive, and mining workflow plus cross-references from affected skills.

---

## [0.7.0] — 2026-06-19

### Added

- **aet-work**: Forward-only deterministic work state. State is recorded forward through `aet-state transition`, stored in `state` with `history[]`, and terminal tasks are sealed to `.agents/work-history.jsonl`.
- **aet-work**: Validated frontmatter contract for plans (`id`, `blocked_by`, `size`). Intake now fails closed on malformed or legacy plan files.
- **aet-work**: `aet-state record-merge` resolves real squash-merge SHAs and records merge commits deterministically.
- **aet-work**: `run-one` hardening with plan-presence guard, worktree/branch hygiene gate, and telemetry.
- **aet-design-system-creation**: Commands section for design-system, design-review, and design-check workflows.
- **aet-validate-scope**: Closure checks for planning and validation skills.

### Changed

- **aet-work**: `status`, `next`, and the orchestrator now read stored `state` with zero git calls; the old `derive` path becomes an explicit human-run `audit`.
- **aet-work**: Pipeline stages are now recorded as `in_progress` sub-states instead of plan-footer breadcrumbs.
- **aet-work**: `init-queue` and `sync` now consult `.agents/work-history.jsonl` to skip already-settled plans.
- **aet-release-prep**: Fixed version-bump detection and `v`-prefix handling when tags are the version source.

### Fixed

- **aet-ship**: Stage-aware review/CSO gate.
- **aet-work**: Orchestrator no longer enters a runaway spawn loop.
- **aet-work**: Batch worktree is reused in single-task orchestrator subprocess.
- **aet-work**: Task IDs are derived without the hard-coded `-plan.md` suffix.
- **Build**: Skill packaging is now deterministic.

### Documentation

- Added deprecation and backward-compatibility inventory (`docs/audits/deprecation-inventory.md`).
- Added upgrade guide for existing AET projects (`aet-work/references/upgrading-existing-project.md`).
- Added ADR-011 documenting forward-only deterministic work state and settled-history semantics.

---

## [0.6.0] — 2026-06-16

### Added

- **aet-work**: Active-only status view. `status` now reports only active tasks and highlights discrepancies between stored and derived statuses.
- **aet-work**: `cleanup` now archives terminal tasks atomically before removing their worktrees.
- **Unified orchestrator**: Finalized orchestrator cleanup and routed `aet-plan` implementation flows through `aet-work`.

### Changed

- **aet-work**: `status` view now includes `done` tasks in active reporting and removes the archived-tasks note.
- **docs/CONVENTIONS.md**: Added Package-Deliverable Rules section requiring all runtime skill rules to live inside skill packages.

### Fixed

- **aet-ship** and **aet-work**: Worktrees now branch from `origin/main`, independent branches are rebased onto `origin/main` before shipping, stacked branches open against their parent, and PR scope audits flag global files.
- **Orchestrator**: Fixed CLI adapter to use real `kimi`/`claude` flags, preserved queue dict-wrapper format on write, and copied untracked plan/PRD files into worktrees.
- **aet-state**: `derive` now verifies `merge_commit` ancestry before marking tasks as merged.
- **aet-work**: Removed project-specific `app/node_modules` symlink from worktree setup.

### Documentation

- Added `docs/retros/2026-06-16-aet-work-pr-scope-retro.md` documenting the worktree/ship hygiene incident.
- Updated `.agents/reference/skill-writing-guide.md` with package-deliverable checklist items.

---

## [0.5.1] — 2026-06-11

### Added

- **AGENTS.md**: Analysis-to-action discipline guardrail. When analysis identifies a principle violation, the agent must state the conclusion and propose the fix — not offer options that preserve the violation.

### Changed

- **aet-work**: `aet-state` helper is now centralized in `aet-work/bin/aet-state` alongside the orchestrator. `aet-setup` no longer scaffolds a per-project copy.
- **aet-setup**: Scaffold template now includes the analysis-to-action discipline guardrail.

---

## [0.5.0] — 2026-06-11

### Added

- **aet-verify**: New skill for conditional live verification. Three modes — foundation smoke checks, feature evidence capture, and bug reproduction with step-by-step evidence capture.
- **aet-upgrade**: New skill for dependency and framework upgrade planning. Analyzes changelogs, greps codebase for affected patterns, classifies risk per breaking change, and produces a risk-mapped upgrade plan.
- **aet-work**: Unified orchestrator with session-isolated pipeline. Replaces the standalone `aet-pipeline-implement` skill with a centralized Python orchestrator that spawns fresh agent sessions per pipeline stage, eliminating context leakage between skills.
- **aet-work**: Ground-truth status derivation via centralized `aet-state` helper. Queue commands now compute derived statuses from git ground truth and surface discrepancies between stored and actual states.
- **aet-prime**: Repurposed as triage front door. Added work-class routing and active PRD/plan stage tracking to classify incoming requests before context loading.
- **aet-evolve**: Added trigger schema for learnings (keyword-based matching), retro debt check (verify past retro action items), and escalation ladder for unresolved systemic issues.
- **aet-validate-scope**: Integrated UI Coverage Lens from `aet-validate-ui`. Seven-category UI/UX validation with blocking/warning severity ratings.
- **Build system**: New `scripts/build-skills.py` with incremental packaging, dependency graph validation, and comprehensive build system test suite.
- **Validation**: Enhanced `scripts/validate-skills.sh` with composition contradiction detection and improved guardrails.
- **Testing**: Added unit tests for orchestrator lib modules (`tests/test_*.py`).

### Changed

- **aet-work**: `run` command now invokes the centralized Python orchestrator instead of generating bash scripts. Improved worktree isolation and parallel execution semantics.
- **aet-pipeline-plan**: Streamlined pipeline sequence. Removed `aet-pipeline-implement` references; all implementation flows now route through `aet-work`.
- **aet-setup**: Enhanced with additional guardrails and setup validation procedures.
- **aet-ship**: Updated branch lifecycle and release gating procedures.
- **aet-bug-report**: Updated investigation procedures and reference materials.
- **aet-plan**: Enhanced validation strategy gate with explicit test coverage requirements per source file.
- **aet-tdd**: Added coverage completeness hard gate before `tdd-complete`.
- **aet-implement**: Updated execution routing to use `aet-work`.
- **docs/CONVENTIONS.md**: Synced with v1.2 toolkit conventions and clarified planning artifact directory rules.

### Removed

- **aet-pipeline-implement**: Skill removed. Functionality unified into `aet-work` orchestrator.
- **aet-validate-ui**: Standalone skill removed. UI validation folded into `aet-validate-scope`.

### Fixed

- **aet-verify**: Resolved validation errors for preamble formatting and trigger collision.
- **aet-work**: Orchestrator now verifies commits exist before marking tasks as done.

---

## [0.4.0] — 2026-06-08

### Added

- **aet-review**: Rewrote the **Tests** lens into a concrete two-part coverage completeness check. New source files without test coverage are classified as `fix-now`; diffs introducing both backend routes and frontend API clients without an API boundary test are also `fix-now`. Added `references/test-coverage-check.md` with the mechanical procedure. ([PR #33](https://github.com/thebrightnest/ae-toolkit/pull/33))
- **aet-tdd**: Added **Coverage Completeness** hard gate before `tdd-complete`. The `plan-tests` step now enumerates every new source file introduced by the plan and mandates at least one named test per file. Added **API boundary integration test** mandate for vertical slices touching both frontend and backend. Added `references/api-boundary-tests.md` and `docs/adr/008-test-coverage-completeness.md`. ([PR #34](https://github.com/thebrightnest/ae-toolkit/pull/34))
- **aet-plan**: Added **Validation strategy gate** to the `plan` command procedure. Plans must now name at least one specifically named test for each new source file or module, and distinguish between unit, integration, and API boundary tests. Frames under the Cross-Cutting Completeness framework (ADR-001). Updated `.agents/templates/plan-template.md` with structured checklist items replacing the generic "Manual verification step". ([PR #35](https://github.com/thebrightnest/ae-toolkit/pull/35))
- **aet-qa**: Added **coverage gate** to the QA procedure. After the automated test suite runs, the agent now checks coverage thresholds and flags any new source files with 0% coverage. Added coverage tooling note with language-appropriate defaults (Laravel, React, etc.). ([PR #36](https://github.com/thebrightnest/ae-toolkit/pull/36))

### Fixed

- **aet-work**: `cleanup` command now correctly handles the legacy `merge_verified` status by normalizing it to `merged` before removal.

## [0.3.0] — 2026-06-02

### Added

- **aet-release-prep**: New skill for automated release preparation. Analyzes commits since the last tag, detects versioning scheme, suggests semantic version bumps, and updates `CHANGELOG.md`.
- **aet-pipeline-implement**: Terminal resilience improvements. Added step-budget mode for long-running pipelines, temporary report files for progress tracking, and `gitignore` safety checks to prevent leaking generated artifacts.
- **aet-work**: Queue state hardening. Added `merged` and `abandoned` terminal statuses; `done` is deprecated but retained for backwards compatibility. New `mark-terminal` command enforces `merge_verified: true` before marking `merged`, and requires a `reason` for `abandoned`. `status` now validates `worktree` fields and flags stale entries. `cleanup` repairs stale worktree fields (missing directories or 0 commits ahead of main). Orchestrator template updated to record `worktree`/`branch` metadata and `completed_at` timestamps. ([PRD](docs/prds/workflow-audit-fixes-prd.md))
- **aet-work**: Orchestrator auto-removes empty worktrees. After a task exits (success or failure), the orchestrator checks if the worktree has 0 commits ahead of main. If so, it removes the worktree and clears the queue's `worktree` field, preventing disk-space leaks from failed or no-op tasks.
- **aet-work**: Orchestrator copies untracked plan and PRD files into worktrees read-only. This ensures agents can reference new plans that exist in the main working directory but have not yet been committed.
- **aet-plan**, **aet-pipeline-implement**: Added explicit guardrails against creating `docs/plans/plans/` or any nested duplicate directory. Agents are instructed to write plan files directly to `docs/plans/{filename}` only.
- **Repo hooks**: Pre-push deletion short-circuit. Added a safety hook that prevents accidental deletion of protected branches during push operations.

### Changed

- **aet-ship**: Branch lifecycle & release gating. Improved branch tracking through the shipping pipeline with clearer release readiness checks and gating logic.
- **docs/adr/003-toolkit-level-branch-safety.md**: Accepted. Validated by Coverage Batch 2 cleanup findings.

### Fixed

- **aet-work**: Fixed orchestrator timeout on long-running `aet-pipeline-implement` tasks. The skill now explicitly specifies `timeout=7200` (2 hours) when spawning the orchestrator, and instructs agents to use `--afk` (or equivalent headless mode) instead of `--yolo` so approval gates auto-dismiss in unattended background jobs. Updated reference orchestrator template and generated script accordingly. ([Bug Report](docs/bugs/2026-06-01-orchestrator-timeout-bug-report.md))

## 0.2.0

### Changed

- **aet-work**, **aet-plan**, **aet-pipeline-plan**: Enforced plan atomicity boundary. `docs/plans/` is now explicitly for atomic, implementable task plans only. Roadmaps, audits, and meta-plans must be stored in `docs/roadmaps/` or `docs/audits/`. `aet-work sync` now validates atomicity and skips non-atomic documents. `AGENTS.md` workflow guardrails updated to reflect the new directory convention. ([PRD](docs/prds/work-queue-atomicity-boundary-prd.md))

- **docs/CONVENTIONS.md**: Added "Planning Artifact Directories" section documenting the directory convention for atomic plans, roadmaps, audits, and PRDs. Created ADR-006 recording the structural boundary decision and its consequences. ([ADR](docs/adr/006-work-queue-atomicity-boundary.md))

- **aet-pipeline-plan**: Removed `aet-discover` from the pipeline sequence. The pipeline now runs `aet-plan → aet-validate-ui (optional) → aet-validate-scope` for validated ideas and known tasks. `aet-discover` remains a standalone skill for raw, unvalidated ideas. ([PRD](docs/prds/pipeline-plan-remove-discover-prd.md))

- **aet-pipeline-plan**: Integrated `aet-validate-ui` as an optional step in the planning pipeline. Added skip logic for no-UI features, a hard gate for blocking UI/UX findings, and `ui-validated` as a resumable stage.

- **aet-work**: Unified `run` command with OS-process isolation. Removed the broken cooperative `run` loop and the `run-scripted` command. The new `run` generates a bash orchestrator that spawns fresh OS processes per task — the proven mechanism formerly known as `run-scripted`. Updated `references/context-isolation.md` to explain why cooperative clearing failed. Added ADR-004 documenting the decision.

### Added

- **Execution Mode Interaction Model**: Introduced `AET_EXECUTION_MODE=unattended` as the formal signal for unattended orchestration, replacing the ad-hoc `AET_ORCHESTRATOR=1` env var. Added ADR-005, updated `docs/CONVENTIONS.md` and `.agents/reference/skill-writing-guide.md` with the contract and bypass protocol. Updated `aet-implement`, `aet-pipeline-implement`, `aet-work`, and `aet-setup` skills to detect and respect the new variable. Added a validator rule in `scripts/validate-skills.sh` to flag skills with interactive approval gates that don't mention `AET_EXECUTION_MODE`. ([PRD](docs/prds/execution-mode-interaction-model-prd.md))

- **Task Size Guardrails**: Introduced a dual-limit model (human-time + AI-complexity) across all planning skills. `aet-plan` now auto-splits oversized stories and tasks, `aet-work` validates sizes on queue sync, and `aet-implement` refuses to start `⚠️ ATOMIC OVERSIZED` tasks without explicit override. Documented in `docs/CONVENTIONS.md`. ([PRD](docs/prds/task-size-guardrails-prd.md))

- **aet-implement**: Added visual/CSS verification to the validation strategy. If a plan includes renderer/UI work, the implementation phase now requires verifying that all custom `className` values have corresponding CSS definitions.
- **aet-review**: Added `references/css-completeness-check.md` — a mechanical procedure for verifying CSS completeness during code review.
- **Cross-Cutting Completeness Framework**: Introduced ADR-001 documenting the framework for catching implicit obligations across domains (CSS, i18n, assets, icons, feature flags). CSS completeness is the first proven example.
- **plan-template**: Added a "Renderer / UI Tasks" subsection to the plan template, reminding authors to verify CSS styles for all custom `className` values.

- **aet-work parallel execution**: `aet-work run` now executes independent tasks in parallel using bash job control. Default concurrency cap is 4 jobs (override via `AET_WORK_JOBS`), with a hard ceiling of 8. Features drain-on-failure (running tasks finish, new spawns halt), orphaned in-progress detection on resume, and end-of-run summary. Added 16 integration tests in `scripts/test-orchestrator.sh`. ([PRD](docs/prds/aet-work-parallel-execution-prd.md))

### Fixed

- **aet-work**: Runtime detection in `run` now uses agent self-identification instead of a hard-coded PATH/env-var priority list. The agent executing `aet-work run` reports its own CLI command and flags, eliminating mis-detection when multiple agents are installed. ([PRD](docs/prds/aet-work-runtime-self-detection-prd.md))

- **aet-ship**: Added stacked branch detection to the `ship` procedure. When a branch was not branched directly from `main`, `aet-ship` now injects a `⚠️ STACKED PR` warning into the PR body and prints a terminal stop-note. Prevents the class of incident where a stacked PR is merged against a stale base after its parent lands in main. ([retro](docs/retros/2026-05-12-stacked-pr-base-not-updated.md))
