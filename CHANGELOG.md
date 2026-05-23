# Changelog

## Unreleased

### Changed

- **aet-pipeline-plan**: Removed `aet-discover` from the pipeline sequence. The pipeline now runs `aet-plan → aet-validate-ui (optional) → aet-validate-scope` for validated ideas and known tasks. `aet-discover` remains a standalone skill for raw, unvalidated ideas. ([PRD](docs/prds/pipeline-plan-remove-discover-prd.md))

- **aet-pipeline-plan**: Integrated `aet-validate-ui` as an optional step in the planning pipeline. Added skip logic for no-UI features, a hard gate for blocking UI/UX findings, and `ui-validated` as a resumable stage.

- **aet-work**: Unified `run` command with OS-process isolation. Removed the broken cooperative `run` loop and the `run-scripted` command. The new `run` generates a bash orchestrator that spawns fresh OS processes per task — the proven mechanism formerly known as `run-scripted`. Updated `references/context-isolation.md` to explain why cooperative clearing failed. Added ADR-004 documenting the decision.

### Added

- **aet-implement**: Added visual/CSS verification to the validation strategy. If a plan includes renderer/UI work, the implementation phase now requires verifying that all custom `className` values have corresponding CSS definitions.
- **aet-review**: Added `references/css-completeness-check.md` — a mechanical procedure for verifying CSS completeness during code review.
- **Cross-Cutting Completeness Framework**: Introduced ADR-001 documenting the framework for catching implicit obligations across domains (CSS, i18n, assets, icons, feature flags). CSS completeness is the first proven example.
- **plan-template**: Added a "Renderer / UI Tasks" subsection to the plan template, reminding authors to verify CSS styles for all custom `className` values.

### Fixed

- **aet-work**: Runtime detection in `run` now uses agent self-identification instead of a hard-coded PATH/env-var priority list. The agent executing `aet-work run` reports its own CLI command and flags, eliminating mis-detection when multiple agents are installed. ([PRD](docs/prds/aet-work-runtime-self-detection-prd.md))

- **aet-ship**: Added stacked branch detection to the `ship` procedure. When a branch was not branched directly from `main`, `aet-ship` now injects a `⚠️ STACKED PR` warning into the PR body and prints a terminal stop-note. Prevents the class of incident where a stacked PR is merged against a stale base after its parent lands in main. ([retro](docs/retros/2026-05-12-stacked-pr-base-not-updated.md))
