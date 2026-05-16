# Changelog

## Unreleased

### Added

- **aet-implement**: Added visual/CSS verification to the validation strategy. If a plan includes renderer/UI work, the implementation phase now requires verifying that all custom `className` values have corresponding CSS definitions.
- **aet-review**: Added `references/css-completeness-check.md` — a mechanical procedure for verifying CSS completeness during code review.
- **Cross-Cutting Completeness Framework**: Introduced ADR-001 documenting the framework for catching implicit obligations across domains (CSS, i18n, assets, icons, feature flags). CSS completeness is the first proven example.
- **plan-template**: Added a "Renderer / UI Tasks" subsection to the plan template, reminding authors to verify CSS styles for all custom `className` values.

### Fixed

- **aet-ship**: Added stacked branch detection to the `ship` procedure. When a branch was not branched directly from `main`, `aet-ship` now injects a `⚠️ STACKED PR` warning into the PR body and prints a terminal stop-note. Prevents the class of incident where a stacked PR is merged against a stale base after its parent lands in main. ([retro](docs/retros/2026-05-12-stacked-pr-base-not-updated.md))
