---
id: aet-self-update
status: scope-validated
---

# PRD: CLI Self-Update & Version Currency Awareness

## Overview

Currently, users who install AE Toolkit via the one-line installer (`curl -fsSL ... | bash`) have no native way to discover when a new version has shipped, nor a simple command to update the CLI and skills in-place. Users must either manually re-run the full installer script or navigate git commands directly.

This feature introduces native version currency awareness and a one-step self-update mechanism into `aet`:

1. Non-blocking, cached (24h TTL) version currency awareness displayed in `aet --version` and `aet setup verify`.
2. A first-class `aet update` command (with `aet setup update` alias) that checks out the latest stable release tag, updates the CLI virtual environment, refreshes skill symlinks, and repairs PATH links.
3. Safe execution-mode detection that distinguishes managed installations (`~/.local/share/ae-toolkit`) from active development working trees (`git status` dirty / editable clones).

## Goals

- **G1**: Users can check for updates and upgrade both the CLI and agent skills in one command: `aet update`.
- **G2**: `aet --version` and `aet setup verify` notify users when a newer version is available without adding latency to everyday commands (24-hour non-blocking disk cache, rate-limit free).
- **G3**: Safe development guardrails: `aet update` refuses to mutate or overwrite active development checkouts or uncommitted work.
- **G4**: Opt-out support via standard environment flags (`AET_NO_UPDATE_CHECK=1` or `CI=1`).
- **G5**: Maintain the proven Git + `uv` installer as primary distribution (ADR-042), keeping skills symlinks reliable.

## Non-Goals

- PyPI publishing (`pip install ae-toolkit`) in this phase.
- External telemetry services or download tracking dashboards.
- Intrusive or blocking network calls on every CLI command execution.
- Auto-updating in the background without explicit user invocation.
- Modifying system-level package managers (Homebrew, apt, pacman).

## Requirements

- **R-1**: Add `src/aet/version_check.py` to handle remote version discovery, version comparison (SemVer), and cache persistence.
- **R-2**: Remote version check queries the official repository release tags via `git ls-remote --tags --sort=-v:refname` (or GitHub release API fallback), requiring zero external dependencies and avoiding GitHub API unauthenticated rate limits (60 req/hr).
- **R-3**: Cache tag query results in `~/.local/share/ae-toolkit/version-cache.json` with a 24-hour time-to-live (TTL). The cache records `latest_version`, `checked_at` (epoch timestamp), and `source`.
- **R-4**: Update checks are strictly suppressed if `AET_NO_UPDATE_CHECK=1`, `CI=1`, or if stdout is not a TTY.
- **R-5**: In `aet --version`, if the cache indicates a newer tag exists (e.g. current `1.19.0` < latest `1.20.0`), print a subtle update notice to stderr:
  `"A newer version of aet is available: v1.20.0 (current: v1.19.0). Run 'aet update' to upgrade."`
- **R-6**: In `aet setup verify`, include a version currency check line:
  - If current: `= aet version: v1.19.0 (up to date)`
  - If outdated: `⚠ aet version: v1.19.0 (update available: v1.20.0; run aet update)`
  - If check failed or offline: `= aet version: v1.19.0 (version check skipped/offline)`

### Self-Update Command (`aet update`)

- **R-7**: Register `aet update` at the CLI top level, and alias under `aet setup update` per ADR-039.
- **R-8**: Provide command flags:
  - `--check`: Query remote tags and print current vs latest version without modifying any files.
  - `--tag <tag>`: Explicitly update to a specific release tag rather than the latest semver tag.
  - `--dry-run`: Output the step-by-step actions that would be performed without executing them.
  - `--yes` (`-y`): Bypass confirmation prompt in interactive mode.
- **R-9**: Detect installation topology:
  - **Managed Installation** (`~/.local/share/ae-toolkit/repo`): Execute update flow.
  - **Development / Editable Installation** (working copy with `.git` and active dev changes): Abort update with a helpful message:
    `"Development checkout detected at <path>. To update, use 'git pull && make install-skills'."`
- **R-10**: The update flow for managed installs executes in sequence:
  1. Fetch latest git tags in managed repo: `git fetch --tags origin`.
  2. Checkout target tag: `git checkout tags/<target_tag>`.
  3. Re-install CLI into managed venv: `uv pip install .` (or fallback to python -m pip).
  4. Re-link skills: invoke `aet setup skills` to ensure new or updated skills are linked to agent directories.
  5. Re-link binary: invoke `aet setup link` to ensure `~/.local/bin/aet` resolves cleanly.
  6. Refresh the version cache with the updated version.
  7. Print success summary including previous and new version numbers.
- **R-11**: The update process is fail-safe: if any intermediate command fails, print the error clearly and do not leave the installation in a half-configured state.

## User Stories

- As a developer using `aet`, I want `aet --version` to let me know if a new version is available so I don't miss new skills and capabilities (satisfies: R-1, R-3, R-5).
- As an engineer with a managed installation, I want to run `aet update` to automatically upgrade both the CLI tool and agent skills without needing to copy-paste the curl installer again (satisfies: R-7, R-10).
- As a contributor working in the `ae-toolkit` source repository, I want `aet update` to protect my working directory and not clobber my local branches or uncommitted changes (satisfies: R-9).
- As an operator in automated CI/CD environments, I want update checks to remain completely silent and fast when `CI=1` or `AET_NO_UPDATE_CHECK=1` is set (satisfies: R-4).
- As a team lead running `aet setup verify`, I want to verify our team's version currency as part of our environment health check (satisfies: R-6).

## Acceptance Criteria

- [ ] `aet version-check` / `src/aet/version_check.py` accurately identifies when remote tag > local version using SemVer rules (satisfies: R-1).
- [ ] Version cache file is created at `~/.local/share/ae-toolkit/version-cache.json` and respects the 24h TTL (satisfies: R-3).
- [ ] Setting `AET_NO_UPDATE_CHECK=1` or `CI=1` bypasses network queries entirely (satisfies: R-4).
- [ ] `aet --version` prints the update notice when a newer version is cached (satisfies: R-5).
- [ ] `aet setup verify` outputs the version status line (satisfies: R-6).
- [ ] `aet update --check` queries remote and reports latest version without mutating files (satisfies: R-8).
- [ ] `aet update --dry-run` shows planned git and uv steps without mutating files (satisfies: R-8).
- [ ] `aet update` executed in a development git clone safely exits with guidance to use `git pull` (satisfies: R-9).
- [ ] `aet update` in a managed install updates the repo, venv, skills symlinks, and PATH link (satisfies: R-10).

## Technical Notes

- **Remote Tag Resolution**: Running `git ls-remote --tags --sort=-v:refname https://github.com/thebrightnest/ae-toolkit` returns the sorted tags directly from the remote Git server. This is natively supported by Git, requires no API tokens, and has no GitHub rate limit.
- **Cache Format**:

  ```json
  {
    "current_version": "1.19.0",
    "latest_version": "1.20.0",
    "last_checked_timestamp": 1729094400,
    "update_available": true
  }
  ```

- **Pip Distribution**: Deferred to a future phase if needed.
- **Managed vs Dev Detection**: Check if `_repo_root()` matches `~/.local/share/ae-toolkit/repo`. If not, or if `.git` contains local branches diverging from tags, treat as dev repository.

## Open Questions

None. Ready for review.

## Divergence Summary

_Recorded: 2026-10-17 — Branch: UPD-01_

### Changed from plan

- Cache format (R-3 vs. Technical Notes): the cache stores `latest_version`, `checked_at`, and `source` as R-3 says, not the `current_version` / `last_checked_timestamp` / `update_available` shape shown in Technical Notes. The current version and update status are computed when the cache is read, so a stale cache cannot report an out-of-date "update available" answer after a local upgrade.
- Remote lookup (R-2): only `git ls-remote` is used. The optional GitHub release API fallback was not built, because git needs no token and has no rate limit. Prerelease and non-SemVer tags are ignored when choosing the latest release.
- Cache population (R-5): `aet --version` reads only the cache and never fills it. Only `aet setup verify` refreshes the cache (one network call, 5s timeout). The `--version` notice therefore appears only if `setup verify` has run within the last 24h.
- `aet setup verify` (R-6): adds a third status line, `= aet version: v<current> (version check skipped/offline)`, for when checks are suppressed or the remote can't be reached. The `⚠ update available` line goes to stderr.

### Added (unplanned)

- PEP 440 version parsing: `parse_semver` accepts `a`/`b`/`rc`/`dev` suffixes as prereleases and ignores `+local` metadata. Source and editable installs report versions like `1.20.1.dev4+g2c2d533d2`, and strict SemVer parsing made comparison silently fail (learning recorded in `.agents/learnings.jsonl`).
- `AET_DATA_DIR` override for the cache location, so it stays consistent with `scripts/install.sh`.

### Deferred

- R-7–R-11 (`aet update`, `--check`, `--dry-run`, dev-clone guard, managed-install update flow, fail-safe): not in UPD-01 scope; left for a follow-up plan. Until it lands, the notices that tell users to "run aet update" point to a command that does not exist yet.

_Stage: synced_
_Next step: run `aet-ship`_
