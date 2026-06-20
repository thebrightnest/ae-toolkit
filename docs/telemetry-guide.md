# Telemetry Guide for AET Projects

This guide explains how to enable, archive, and use telemetry from projects that run the AE Toolkit (`aet-work`). The telemetry is **opt-in per project**, local-first, and designed to feed `aet-evolve` so the toolkit can learn from recurring loops, environment issues, and pipeline inefficiencies across projects.

## What gets recorded

When `aet-work` runs a task, it writes three kinds of artifacts:

- `.agents/execution.log.jsonl` — append-only events emitted by the orchestrator:
  - stage start/end
  - internal loops (test retries, format fixes, etc.)
  - environment/dependency issues
  - individual test runs
  - learning candidates
- `.agents/work-history.jsonl` — settled (merged or abandoned) tasks.
- `/tmp/aet-reports/{task-id}/` — markdown reports from QA, review, CSO, and verification stages.

No external service is used. Logs stay in the project until you explicitly archive them.

## Enabling telemetry in a project

1. Make sure the project has the latest AET skills installed:

   ```bash
   make install-skills
   ```

2. Run any plan with `aet-work`:

   ```bash
   aet-work run-one docs/plans/some-plan.md
   ```

   The orchestrator creates `.agents/execution.log.jsonl` automatically on first run.

3. Add `.agents/execution.log.jsonl` and `/tmp/aet-reports/` to `.gitignore`:

   ```gitignore
   .agents/execution.log.jsonl
   /tmp/aet-reports/
   ```

   Logs are not meant to be committed.

## Configuring worktree dependency warmup

If new worktrees are missing dependency directories (`node_modules`, `vendor`, etc.), record the symlinks in `.agents/aet-work.json`:

```json
{
  "symlink_dependencies": [
    { "from": "app/node_modules", "to": "../app/node_modules" },
    { "from": "api/vendor", "to": "../api/vendor" }
  ]
}
```

The orchestrator creates these symlinks once per task, before any stage runs, and emits an `environment_issue` telemetry event so the pattern can be mined later.

## Archiving telemetry for cross-project learning

To copy a project's telemetry into the user-level archive:

```bash
aet-evolve ingest-telemetry
```

By default this reads:

- `.agents/execution.log.jsonl`
- `.agents/work-history.jsonl`
- `/tmp/aet-reports/**/*.md`

and writes a sanitized copy to:

```
~/.aet/telemetry/{project-slug}/{date}-{run-id}/
```

Repository paths are hashed and a `project_id`/`repo_slug` header is added. Originals are left untouched.

### When to archive

- After a meaningful milestone.
- Before deleting old reports or pruning `/tmp/aet-reports/`.
- Whenever you want `aet-evolve mine-learnings` to include recent runs.

## Mining archived runs

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

With `--propose`, it prints suggested edits to skill files but **never writes them directly**.

## Reviewing a single run

For a quick text summary of recent runs:

```bash
aet-work report
aet-work report --since 2026-06-01
```

This prints counts of stages, loops, environment issues, and wall-clock time.

## Privacy and retention

- Telemetry is stored on the local filesystem only.
- Absolute paths are hashed during ingest.
- Secrets are not collected; if a secret appears in a report, treat the report as sensitive and delete it.
- Retention is manual: delete old directories under `~/.aet/telemetry/` when no longer needed.

## Troubleshooting

| Symptom                              | Fix                                                                     |
| ------------------------------------ | ----------------------------------------------------------------------- |
| `~/.aet/telemetry/` is empty         | Run `aet-evolve ingest-telemetry` from the project directory.           |
| Reports are missing from the archive | Ensure `/tmp/aet-reports/` has not been cleaned yet.                    |
| `mine-learnings` finds no patterns   | Archive more runs or extend the date range.                             |
| Dependency warmup does not run       | Verify `.agents/aet-work.json` exists and the source paths are correct. |
