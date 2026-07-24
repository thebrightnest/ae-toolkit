---
id: cfg-01-config-resolution-overhaul
size: M
blocked_by: []
pipeline: standard
status: queued
security_review: required
security_review_reason: changes config-resolution precedence and file locations; a precedence bug could silently read the wrong config or fail open into trunk-based defaults
docs_sync: required
docs_sync_reason: CONVENTIONS.md config section and CONTEXT.md reference the old filename and cwd-relative resolution; must be synced after landing
---

# Plan: Config Resolution Overhaul (rename, root anchor, worktree-independent slug)

## Context

- PRD: `docs/prds/aet-config-file-overhaul-prd.md` (R-1, R-2, R-3, R-4)
- Prior art: ewl-07 (external-first precedence, `docs/plans/ewl-07-non-invasive-config-root.md`),
  ADR-022 (slug derivation), ADR-044/045 (branch model).
- Verified pain (2026-07-24 consumer report): in-tree config resolves relative to
  cwd (`src/aet/backends/factory.py:83-85`), so subdirectory invocations miss it;
  the external config slug is worktree-labelled (`src/aet/project_id.py:64-66`),
  so `~/.aet/{slug}/config.json` is invisible from linked worktrees.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Locked design

- **Clean rename, fail closed.** `DEFAULT_CONFIG_PATH` becomes
  `.agents/aet-config.json`. When the legacy `.agents/aet-work.json` exists and
  the new file does not, `resolve_config` raises a `LegacyConfigError` naming
  `aet configure --migrate` as the fix. No silent read of the old file, no
  silent fall-through to defaults.
- **Root-anchored in-tree resolution.** The in-tree path is resolved against
  `git rev-parse --show-toplevel` (via the existing `resolve_repo_root` in
  `src/aet/project_id.py`), never the process cwd.
- **Config identity drops the worktree label.** New `derive_config_slug()` in
  `project_id.py` returns the main-worktree identity (label always `main`);
  `resolve_config` uses it for the external path. `derive_project_slug()` is
  untouched — telemetry/reports keep per-worktree granularity.
- **Precedence unchanged:** `AET_WORK_CONFIG` env → external → in-tree →
  defaults (R-4 is a documentation + regression-test requirement, not a
  behavior change).
- **`aet configure --migrate`** renames legacy → new, content-preserving,
  using `git mv` when the file is tracked, plain `mv` otherwise; refuses to
  overwrite an existing new file.
- **Every reader moves, not just the factory default.** Scope-validation
  (2026-07-24) found direct readers beyond `DEFAULT_CONFIG_PATH`:
  `src/aet/cli/orchestrator.py` passes the old path explicitly to
  `resolve_config` (two call sites), `src/aet/worktree.py` reads
  `.agents/aet-work.json` directly for `symlink_dependencies` (two sites),
  and `src/aet/cli/reconcile.py` / `src/aet/cli/sprint.py` reference the
  filename. All are updated to the new path; the orchestrator call sites
  switch to the repo-root-anchored default rather than naming a path.

## Rejected Alternatives

- **Silent fallback read of the old file for one release** — rejected: the
  owner explicitly chose no fallback; a silent read delays the rename forever
  and hides the upgrade from agents running unattended.
- **Warning instead of hard error on legacy file** — rejected (PRD open
  question, settled): warnings scroll past in agent-driven runs and the
  failure mode is a silent revert to trunk-based mode.
- **Changing `derive_project_slug` itself** — rejected: telemetry and reports
  consumers rely on the worktree label (ADR-022); a config-specific identity
  avoids a cross-cutting telemetry migration.

## Task List

1. ✓ Rename `DEFAULT_CONFIG_PATH` to `.agents/aet-config.json`; add
   `LegacyConfigError` (fail-closed, names `aet configure --migrate`) when only
   the legacy file exists — S (traces: R-1)
2. ✓ Anchor in-tree resolution to `resolve_repo_root()` instead of cwd — S
   (traces: R-2)
3. ✓ Add `derive_config_slug()` (main-worktree identity) in `project_id.py` and
   use it for the external config path in `factory.py` — S (traces: R-3)
4. ✓ Sweep remaining readers to the new filename: `orchestrator.py` (2 explicit
   `resolve_config` call sites — switch to anchored default), `worktree.py`
   (`symlink_dependencies`, 2 sites), `reconcile.py`, `sprint.py` — S
   (traces: R-1)
5. ✓ Add `aet configure --migrate` (git-aware rename, no overwrite, prints the
   resolved result) — S (traces: R-1)
6. ✓ Regression tests (see Validation Steps), including updating the existing
   tests that write the old filename (`test_single_pr_loop.py`,
   `test_integration_push.py`, `test_orchestrator.py`,
   `test_status_liveness_contract.py`) — M (traces: R-1, R-2, R-3, R-4)
7. Merge branch to main and verify integration — S [Deferred: ship stage]

**Size definitions:** S ≤ 2 hr / ≤ 150 lines; M ≤ 1 day / ≤ 600 lines; L must be re-evaluated.

### Floor Check

- [x] Stands alone: after this plan the new file model works end-to-end
  (read + migrate); later plans only add a nicer writer and docs.
- [x] Expected diff ~250-350 lines incl. tests — exceeds branch overhead.

## Files to Modify

- `src/aet/backends/factory.py`
- `src/aet/project_id.py`
- `src/aet/cli/configure_backend.py`
- `src/aet/cli/main.py` (wire `--migrate`)
- `src/aet/cli/orchestrator.py` (explicit-path call sites)
- `src/aet/worktree.py` (`symlink_dependencies` readers)
- `src/aet/cli/reconcile.py`, `src/aet/cli/sprint.py` (filename references)
- `tests/backends/test_integration_mode_config.py` (extend)
- `tests/backends/test_config_resolution_overhaul.py` (new)
- `tests/orchestrator/test_single_pr_loop.py`, `test_integration_push.py`,
  `test_orchestrator.py`, `test_status_liveness_contract.py` (old filename)

## Validation Steps

- [x] `make validate` passes
- [x] New coverage in `tests/backends/test_config_resolution_overhaul.py`:
  - `test_legacy_file_only_fails_closed_naming_migrate` (unit)
  - `test_new_file_resolves_from_subdirectory` (unit, chdir into subdir)
  - `test_external_config_resolves_from_linked_worktree` (integration:
    temp repo + `git worktree add`, HOME redirected)
  - `test_migrate_renames_and_preserves_contents` (unit)
  - `test_migrate_refuses_overwrite_of_existing_new_file` (unit)
- [x] Extended precedence regression in `test_integration_mode_config.py`:
  env > external > in-tree > defaults unchanged (R-4)
- [x] Default-mode regression: `tests/orchestrator/test_pr_per_task_unchanged.py` stays green
- [x] R-trace coverage: R-1 by tasks 1, 4, 5; R-2 by tasks 2, 5; R-3 by tasks 3, 5; R-4 by task 5; no unknown R-ids
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main` [Deferred: ship stage]

## Rollback Plan

Revert the merge commit. Installs that already ran `--migrate` keep working:
their `.agents/aet-config.json` is simply not read by the reverted code (they
rename back by hand — one file, called out in the upgrade guide).

---

_Stage: synced_
_Next step: run `aet-ship`_
