# Telemetry Guide for AET Projects

This guide explains how telemetry works in projects that run the AE Toolkit
(`aet-work`). Telemetry is **local-first** and written directly to the user-level
archive so it survives project worktree deletion. `aet-evolve mine-learnings`
reads the archive when you want cross-project analysis.

## What gets recorded

When `aet-work` runs a task, the orchestrator writes directly to:

```
~/.aet/telemetry/<main-worktree-dir>/<worktree-label>/{date}/{run-id}/
    ├── last-run.json
    ├── {task-id}.jsonl
    └── ...
```

Task logs are therefore **five levels** below the archive root, not four: the
`{project-slug}` spans the first *two* segments. A reader that treats it as one
directory level (`{project-slug}/{date}/{run-id}/*.jsonl`) matches nothing and
reports an empty archive rather than an error.

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
`tests_failed`). Every verdict also carries a required `tree_hash` — a git
tree-object fingerprint of the working tree it attests to, auto-stamped by
`write_verdict` (ADR-025). `evidence.validation_freshness` compares it against
the current tree and returns `run` (revalidate), `lint-only` (only docs or
Markdown changed), or `skip` (tree unchanged since the last pass). Beyond that
derived record, the orchestrator does not emit
per-loop or per-test-run records; those are produced by other skills (for
example, `aet-retro` emits learning candidates).

`.agents/work-history.jsonl` remains project-local for now. A copy is archived
with each run so terminal task history is preserved alongside execution logs.

No external service is used. Logs stay on your local filesystem.

## What counts as a test run

Detection (which Bash calls in a session log are test invocations) and
scope classification (`full-suite` / `impact` / `unknown`) are two readings of
one parse. Both resolve commands through the shared runner registry in
`src/aet/test_runners.py` — there is exactly one runner table, so a command
the detector recognises is classifiable by construction.

Session-log extraction is adapter-dispatched, mirroring `usage.parse_usage`.
`src/aet/session_log.py` selects the reader for the current CLI:

- `kimi` — reads `agents/*/wire.jsonl` under a kimi session directory
  (`src/aet/wirelog.py`).
- `claude` — reads Claude Code's transcript JSONL at
  `~/.claude/projects/<cwd-slug>/<sessionId>.jsonl`
  (`src/aet/session_log_claude.py`).

Each reader returns the same shape (`command`, `start_time`, `end_time`,
`duration_seconds`, `exit_code`) and applies the same defensive rules: oversized
lines, malformed JSON, missing pairs, and missing timestamps are skipped or
recorded as null — never estimated. An adapter without a reader returns no
observed records; that is an explicit property of the seam, not incidental
silence (ADR-050).

Before matching, the command is normalised:

- compound commands are split on `&&`, `;`, `|`; leading setup segments
  (`cd …`, `source …`, `. …`) are dropped and the last remaining segment is
  the candidate;
- leading `VAR=value` environment assignments are stripped;
- a `*/bin/` path prefix on a recognised runner is reduced to the bare runner
  name (`.venv/bin/python -m pytest` → `python -m pytest`); a path-prefixed
  head that is not a recognised runner (`./run_tests.sh`) never matches;
- runner wrappers are unwrapped a layer at a time: `poetry run`, `uv run`,
  `bundle exec`, `npx` (with flags), `time`.

The runner table then anchors on the normalised head: `pytest`,
`python -m pytest`, `python -m unittest`, `vitest`, `jest`, `rspec`,
`phpunit`, `php artisan test`, `dotnet test`, `gradle test`, `make` with a
`test`/`validate` target, `npm test`, `npm run test`, `yarn test`,
`pnpm test`, `cargo test`, `go test`.

Anchoring is deliberate: a runner merely *mentioned* in an unrelated command
(`grep -r pytest .`, `git commit -m "fix pytest"`, `echo "run pytest"`) does
not match. Where normalisation is ambiguous the resolver declines to match —
a missed run costs telemetry volume, but a wrong match would record a
fabricated one.

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
etc.), record the symlinks in `.agents/aet-config.json`:

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
small Starlette + uvicorn server that lets the browser read the archive
directly:

```bash
aet panel                        # serves panel + ~/.aet/telemetry, opens your browser
python3 -m aet.panel.serve       # direct module invocation (same behavior)
```

The panel source lives in `src/aet/panel/`. You can also open
`src/aet/panel/index.html` directly and pick the telemetry folder manually,
but the launcher is the intended path.

In-flight runs are first-class in served mode (lvp-01): a just-started run
appears on load even before its first stage record lands, and any run without
`last-run.json` is labeled **live** (archive activity fresher than 30 minutes)
or **incomplete** (stale) instead of a fake success — crashed or abandoned
runs become visible for the first time. Live rows sort to the top of the Runs
table, and plan rows in the Plans lens show a live dot while a contributing
run is live. The folder-picker fallback has no dir listing, so live-run
visibility requires the launcher.

For a quick text summary of recent runs:

```bash
aet-work report
aet-work report --since 2026-06-01
aet-work report --run-dir ~/.aet/telemetry/my-project/2026-06-30/<run-id>
```

This prints run and task counts, wall-clock time, the average isolation level,
and environment issues.

## Cross-task metrics (`aet metrics`)

`aet report` is run-centric; for cross-run settled-task analytics use:

```bash
aet metrics                          # human report over all settled history
aet metrics --since 2026-07-01       # only tasks settled on/after a date
aet metrics --json                   # machine-readable projection
aet metrics --history-file path.jsonl  # default .agents/work-history.jsonl
```

The human report has three sections — **First-pass merge rate**, **Rework**,
**Cost per merged task** — each with an `overall` line plus one row per work
class present in the history (tasks without a `work_class` land in
`unclassified`).

The `--json` projection is the canonical output of
`aet-work/lib/metrics.py::aggregate`:

```json
{
  "since": "2026-07-01",
  "overall": { "settled": 0, "merged": 0, "first_pass": 0, "first_pass_rate": null, "rework": 0, "cost": { ... } },
  "classes": { "<work_class>": { ...same bucket shape... } }
}
```

Null and coverage semantics:

- `first_pass_rate` is `null` when a bucket has no merged tasks; the human
  report renders nulls as `-`.
- Cost fields (`tokens_total`, `tokens_avg_per_merged`, `usd_total`,
  `usd_avg_per_merged`) are `null` when no telemetry values exist;
  `usd_known_tasks` counts how many merged tasks contributed a USD estimate,
  shown in the human report as `(n known)`.
- An empty or missing history is a valid state, not an error: the human
  report prints `No settled tasks found` and `--json` prints the zeroed
  projection, both with exit code 0. The only exit-code-1 path is a malformed
  `--since` (expected `YYYY-MM-DD`).

## Delivered-size measurement loop (`aet size`)

At task closure the orchestrator records the actual diff size for the task's
`merge_commit`. `aet size` exposes that measurement loop to operators:

```bash
aet size report                          # distribution by declared S/M/L label
aet size report --json                   # machine-readable projection
aet size report --since 2026-07-01       # only tasks settled on/after a date
aet size backfill                        # measure historical records idempotently
aet size backfill --min-yield 267        # fail if fewer than N records resolve
```

The report answers one question per declared label: how many plans delivered a
measurable diff, what were the median and p90 headline sizes, and what share
exceeded the label's band? The headline size excludes planning artifacts
(`docs/`, `.agents/`, `content/`, `reports/`) so the numbers are comparable to
the S/M/L bands defined in `docs/CONVENTIONS.md`.

The `--json` projection is the canonical output of
`aet.metrics.aggregate_delivered_size`:

```json
{
  "since": "2026-07-01",
  "sample_size": 147,
  "labels": {
    "S": {"n": 12, "median": 81.0, "p90": 384.0, "exceeds_band": 0.42},
    "M": {"n": 117, "median": 405.0, "p90": 836.0, "exceeds_band": 0.71},
    "L": {"n": 18, "median": 832.0, "p90": 6244.0, "exceeds_band": 0.0}
  }
}
```

Backfill is idempotent: records that already carry a `delivered_size` are
skipped, records with a resolvable `merge_commit` are measured via
`git diff <merge_commit>^1..<merge_commit>`, and unresolvable records are
counted with a reason breakdown rather than silently dropped. Run it whenever
`delivered_size` measurement is added or fixed so the historical distribution
is up to date.

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
scripts/archive/migrate-telemetry-slugs.py thebrightnest/ae-toolkit aiskills/main
scripts/archive/migrate-telemetry-slugs.py thebrightnest/artifactsh artifactsh/main

# then apply
scripts/archive/migrate-telemetry-slugs.py thebrightnest/ae-toolkit aiskills/main --apply
scripts/archive/migrate-telemetry-slugs.py thebrightnest/artifactsh artifactsh/main --apply
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
| Dependency warmup does not run                        | Verify `.agents/aet-config.json` exists and the source paths are correct.         |
| Junk projects (`tests`, `tmp*`) appear in the archive | Pre-thp-01 pollution from test runs; the suite is isolated now — delete the dirs. |

## Panel implementation notes

The panel is implemented as a single self-contained `src/aet/panel/index.html`
(React 18 UMD, Babel standalone, Tailwind Play CDN) plus a Starlette server in
`src/aet/panel/serve.py` run by uvicorn. There is no build step. The server is
localhost-only (bound to `127.0.0.1`), refuses path traversal, and exposes two
JSON endpoints: `GET /api/list` (files plus run directories with activity
mtimes) and `GET /api/file?p=<relpath>`. The `aet panel` subcommand dispatches
to the same module, so editable installs, wheels, and direct source invocation
all serve the bundled HTML identically.
