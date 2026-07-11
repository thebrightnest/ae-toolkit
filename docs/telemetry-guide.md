# Telemetry Guide for AET Projects

This guide explains how telemetry works in projects that run the AE Toolkit
(`aet-work`). Telemetry is **local-first** and written directly to the user-level
archive so it survives project worktree deletion. `aet-evolve mine-learnings`
reads the archive when you want cross-project analysis.

## What gets recorded

When `aet-work` runs a task, the orchestrator writes directly to:

```
~/.aet/telemetry/{project-slug}/{date}/{run-id}/
    ├── last-run.json
    ├── {task-id}.jsonl
    └── ...
```

The `{project-slug}` is worktree-based: `<main-worktree-dir>/<worktree-label>`,
derived from the local checkout rather than the git remote. The primary
worktree is labelled `main` (for example, `aiskills/main`); a linked worktree
contributes its own directory name (`.worktrees/aet-panel` →
`aiskills/aet-panel`). The `AET_PROJECT_ID` / `AET_REPO_SLUG` environment
variables override the derived slug — use them to merge two clones into one
project. Outside a git repository the slug falls back to the directory
basename. Accepted trade-offs of local-path identity: two clones of one repo
are two separate projects, two unrelated repos with the same directory name
under different parents merge into one, and moving or renaming the folder
starts the project fresh.

Each task JSONL file contains:

- one stage record per spawned agent session — start/end timestamps, exit code,
  files modified, and commits created. The deterministic unit is the **session**:
  under `standard` isolation a single session may span several stages, so the
  record carries the session's target `stage` plus a `stages` list capturing the
  span. `full` and `minimal` isolation yield exact per-stage records (`stages`
  is `null`).
- environment/dependency issues raised during worktree warmup

`last-run.json` records the run outcome, task counts, and wall-clock time.

When a checking stage passes, the orchestrator gates on the structured verdict
and, for a passing `aet-qa` verdict, derives an individual `test_run` record
from its fields (`test_command`, `tests_total`, `tests_passed`,
`tests_failed`). Beyond that derived record, the orchestrator does not emit
per-loop or per-test-run records; those are produced by other skills (for
example, `aet-retro` emits learning candidates).

`.agents/work-history.jsonl` remains project-local for now. A copy is archived
with each run so terminal task history is preserved alongside execution logs.

No external service is used. Logs stay on your local filesystem.

## Enabling telemetry in a project

1. Make sure the project has the latest AET skills installed:

   ```bash
   make install-skills
   ```

2. Run any plan with `aet-work`:

   ```bash
   aet-work run-one docs/plans/some-plan.md
   ```

   The orchestrator creates the archive directory automatically on first run
   and prints the path when it finishes.

3. Add `~/.aet/telemetry/` and `aet-work.log` to your personal ignore rules if
   desired. These paths are outside the project, so no project `.gitignore`
   changes are required for telemetry.

## Configuring worktree dependency warmup

If new worktrees are missing dependency directories (`node_modules`, `vendor`,
etc.), record the symlinks in `.agents/aet-work.json`:

```json
{
  "symlink_dependencies": [
    {
      "name": "app-node_modules",
      "source": "app/node_modules",
      "target": "app/node_modules"
    },
    { "name": "api-vendor", "source": "api/vendor", "target": "api/vendor" }
  ]
}
```

The orchestrator creates these symlinks once per task, before any stage runs,
and emits an `environment_issue` telemetry event so the pattern can be mined
later.

## Mining telemetry for systemic patterns

To surface recurring patterns across projects:

```bash
aet-evolve mine-learnings
```

This scans `~/.aet/telemetry/` and produces a ranked markdown report of:

- repeated environment/dependency issues
- test loops and retry clusters
- repeated full-suite test runs
- review/CSO noise classifications
- stage failure patterns

With `--propose`, it prints suggested edits to skill files but **never writes
them directly**.

## Reviewing a single run

For a visual overview, launch the telemetry panel — a single HTML file plus a
tiny stdlib-only server that lets the browser read the archive directly:

```bash
python3 aet-work/panel/serve   # serves panel + ~/.aet/telemetry, opens your browser
```

(You can also open `aet-work/panel/index.html` directly and pick the telemetry
folder manually, but the launcher is the intended path.)

For a quick text summary of recent runs:

```bash
aet-work report
aet-work report --since 2026-06-01
aet-work report --run-dir ~/.aet/telemetry/my-project/2026-06-30/<run-id>
```

This prints run and task counts, wall-clock time, the average isolation level,
and environment issues.

## Telemetry during test runs

The toolkit's pytest suite spawns the real orchestrator, but it never writes to
your real archive: an autouse fixture in `tests/conftest.py` points
`AET_TELEMETRY_ARCHIVE_DIR` (and the `DEFAULT_ARCHIVE_DIR` fallback, for tests
that wipe `os.environ` in-process) at a per-test tmp dir, and every subprocess
spawn inherits it. A test opts out only by setting `AET_TELEMETRY_ARCHIVE_DIR`
explicitly itself.

## Migrating historical slugs

Runs archived before the worktree-based slug scheme (thp-02) sit under
origin-derived names like `thebrightnest/ae-toolkit`. Records do not embed the
slug — only the archive paths do — so migration is pure directory renames, and
`aet-work report` and the panel follow automatically. Use the in-repo helper:

```bash
# dry-run first (default): lists every pending move, touches nothing
scripts/migrate-telemetry-slugs.py thebrightnest/ae-toolkit aiskills/main
scripts/migrate-telemetry-slugs.py thebrightnest/artifactsh artifactsh/main

# then apply
scripts/migrate-telemetry-slugs.py thebrightnest/ae-toolkit aiskills/main --apply
scripts/migrate-telemetry-slugs.py thebrightnest/artifactsh artifactsh/main --apply
```

The script renames the project dirs under **both** roots (`~/.aet/telemetry`
and `~/.aet/reports`; override with `--archive` / `--reports`). It refuses any
move whose destination run dir already exists (never clobbers), is idempotent
(OLD absent + NEW present → nothing to do), and validates slug args against
path traversal. To roll back, replay the dry-run output inverted
(`NEW OLD --apply`).

## Privacy and retention

- Telemetry is stored on the local filesystem only.
- Absolute paths are sanitized to `{REPO_ROOT}` and `{HOME}` placeholders at
  write time.
- Secrets are not collected; if a secret appears in a log, treat the file as
  sensitive and delete it.
- Retention is handled by the prune CLI. Dry-run first, then delete:

  ```bash
  aet-work report --prune 30           # dry run: lists candidates, deletes nothing
  aet-work report --prune 30 --force   # actually delete runs older than 30 days
  aet-work report --prune 30 --project <slug>  # scope to one project subtree
  ```

  A run dir is pruned only when both its date path segment and its newest file
  mtime are older than the cutoff, so a live run (even an empty, summary-less
  dir) always survives. **Never prune the active run:** the CLI automatically
  protects the run holding `.agents/work-queue.lease` and the run named by
  `AET_RUN_ID`. Deletion is irreversible — always review the dry run before
  passing `--force`. The gate-evidence reports tree (`~/.aet/reports`) is not
  covered by prune.

## Troubleshooting

| Symptom                                               | Fix                                                                               |
| ----------------------------------------------------- | --------------------------------------------------------------------------------- |
| `~/.aet/telemetry/` is empty                          | Run `aet-work run-one` or `aet-work run` at least once.                           |
| `mine-learnings` finds no patterns                    | Run more tasks or extend the date range.                                          |
| Dependency warmup does not run                        | Verify `.agents/aet-work.json` exists and the source paths are correct.           |
| Junk projects (`tests`, `tmp*`) appear in the archive | Pre-thp-01 pollution from test runs; the suite is isolated now — delete the dirs. |
