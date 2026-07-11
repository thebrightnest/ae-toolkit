---
id: thp-03-archive-slug-migration
size: M
blocked_by:
  - thp-02-worktree-project-slug
pipeline: standard
status: approved
security_review: required
security_review_reason: script renames directories inside the user's home archive — verify path containment under the archive root, collision refusal, and no traversal via crafted slug arguments
docs_sync: required
docs_sync_reason: telemetry guide gains the migration runbook (one-shot rename commands for this machine's archive)
---

# Plan: Archive Slug Migration Helper

## Context

- PRD: `docs/prds/telemetry-hygiene-plan-panel-prd.md` (R-3)
- After thp-02, **new** runs file under `<main-dir>/<worktree>` slugs, but existing history sits under origin-derived names (`thebrightnest/ae-toolkit`, `thebrightnest/artifactsh`). Records do not embed the slug (verified — only paths under the archive encode it), so migration is pure directory renames; `aet-work report` and the panel follow automatically because they share `derive_project_slug()` / scan the tree.
- Junk projects (`tests`, `demo/project`, `tmp*`, `T/tmp*`) are **not** migrated — thp-01 stops new ones and thp-04 retention ages the rest out.
- The rename is executed manually by the owner against the live `~/.aet` archive; the script ships in-repo (precedent: `scripts/migrate-plans-to-frontmatter.py`) so QA exercises it against a fixture archive, never the real one.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Locked design

- `scripts/migrate-telemetry-slugs.py OLD_SLUG NEW_SLUG [--apply] [--archive PATH] [--reports PATH]`
  - Migrates the project dirs under **both roots** (validation finding: gate evidence shares the slug via `evidence.py:96`): telemetry root from `AET_TELEMETRY_ARCHIVE_DIR` or `~/.aet/telemetry` (`telemetry.archive_dir()`), reports root from `AET_REPORTS_DIR` or `~/.aet/reports` (`evidence.reports_dir()`), via the `aet-work/lib` import path. A missing project dir under either root is fine (reports may not exist for old projects).
  - **Dry-run by default**: prints each `old → new` run-dir move and a summary; `--apply` performs them.
  - Slug args are validated: relative, no `..`, ≤ 2 segments; resolved destination must stay under the archive root.
  - Moves `{archive}/OLD_SLUG` → `{archive}/NEW_SLUG` creating parents; if NEW exists, merge date dirs; if a destination **run dir** already exists, refuse that move, report it, exit non-zero (never clobber).
  - Idempotent: OLD absent + NEW present → "nothing to do", exit 0. Empty OLD parent dirs are removed after a successful apply.
- Runbook documented in `docs/telemetry-guide.md`:

  ```bash
  scripts/migrate-telemetry-slugs.py thebrightnest/ae-toolkit aiskills/main --apply
  scripts/migrate-telemetry-slugs.py thebrightnest/artifactsh artifactsh/main --apply
  ```

## Rejected Alternatives

- **Auto-detecting the mapping from local clones** — rejected: the script cannot know every checkout on the machine; explicit OLD NEW pairs are auditable and match the two known renames.
- **Building migration into `aet-work report`** — rejected: one-shot operational action, not a recurring report concern; keeps thp-04's surface clean.
- **Symlinking old → new names** — rejected: no-backward-compat rule; scanners would double-count runs.

## Task List

1. ✓ Write `scripts/migrate-telemetry-slugs.py` per Locked design (argparse, dry-run default, containment validation, collision refusal, idempotency) — M (traces: R-3)
2. ✓ Add `tests/test_migrate_telemetry_slugs.py` with the three named tests (below) running the script via `subprocess` against a tmp archive — includes the CLI smoke/exit-code coverage the 2026-07-06 `mine-learnings` learning calls for — S (traces: R-3)
3. ✓ Add the migration runbook to `docs/telemetry-guide.md` (the two commands above + dry-run-first instruction) — S (traces: R-3)
4. Merge branch to main and verify integration — S [Deferred: to `aet-ship` per the standard pipeline]

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] Not a near-identical addition (single operational script)
- [x] Diff ~175 lines / 3 files
- [x] Cannot share a branch with thp-02: blocked on its merged slug semantics; batching would push the pair past M

## Files to Modify

- `scripts/migrate-telemetry-slugs.py` (new)
- `tests/test_migrate_telemetry_slugs.py` (new)
- `docs/telemetry-guide.md`

## Validation Steps

- [x] `tests/test_migrate_telemetry_slugs.py::test_dry_run_lists_renames_and_touches_nothing` — integration: fixture archive unchanged after default invocation; stdout names every pending move
- [x] `tests/test_migrate_telemetry_slugs.py::test_apply_renames_and_is_idempotent` — integration: `--apply` moves run dirs (contents intact); second `--apply` exits 0 with "nothing to do"
- [x] `tests/test_migrate_telemetry_slugs.py::test_collision_refuses_overwrite` — integration: pre-existing destination run dir → move refused, exit non-zero, source intact
- [x] `tests/test_migrate_telemetry_slugs.py::test_apply_renames_reports_tree_too` — integration: fixture reports root with `{OLD}/{task-id}/verdict.json` ends up under `{NEW}/`; absent reports dir is not an error
- [ ] Manual (owner, post-merge): dry-run both runbook commands, then `--apply`; panel folder filter shows `aiskills`/`artifactsh`; `aet-work report --project aiskills/main` returns the historical runs
- [x] R-trace coverage: R-3 by tasks 1–3; no unknown R-ids cited
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Code: revert the merge commit. Data: the script's dry-run output is the executed move list — replay it inverted (`NEW OLD --apply`) to restore original names; no file contents are modified.

---

_Stage: synced_
_Next step: run `aet-ship`_
