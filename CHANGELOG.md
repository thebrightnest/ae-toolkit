# Changelog

## Unreleased

### Fixed

- **aet-ship**: Added stacked branch detection to the `ship` procedure. When a branch was not branched directly from `main`, `aet-ship` now injects a `⚠️ STACKED PR` warning into the PR body and prints a terminal stop-note. Prevents the class of incident where a stacked PR is merged against a stale base after its parent lands in main. ([retro](docs/retros/2026-05-12-stacked-pr-base-not-updated.md))
