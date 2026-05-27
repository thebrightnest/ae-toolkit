# Changelog

## Unreleased

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

### Fixed

- **aet-work**: Runtime detection in `run` now uses agent self-identification instead of a hard-coded PATH/env-var priority list. The agent executing `aet-work run` reports its own CLI command and flags, eliminating mis-detection when multiple agents are installed. ([PRD](docs/prds/aet-work-runtime-self-detection-prd.md))

- **aet-ship**: Added stacked branch detection to the `ship` procedure. When a branch was not branched directly from `main`, `aet-ship` now injects a `⚠️ STACKED PR` warning into the PR body and prints a terminal stop-note. Prevents the class of incident where a stacked PR is merged against a stale base after its parent lands in main. ([retro](docs/retros/2026-05-12-stacked-pr-base-not-updated.md))
