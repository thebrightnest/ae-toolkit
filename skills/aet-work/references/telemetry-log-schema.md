# Telemetry Log Schema

The orchestrator writes execution telemetry directly to the user-level archive:

```
~/.aet/telemetry/{project-slug}/{date}/{run-id}/
    ├── last-run.json
    ├── {task-id}.jsonl
    └── ...
```

`{project-slug}` is the worktree-based slug derived by
`aet-work/lib/telemetry.py::derive_project_slug`:
`<main-worktree-dir>/<worktree-label>` (e.g. `aiskills/main`). The primary
worktree is labelled `main`; a linked worktree contributes its own directory
name. The `AET_PROJECT_ID` / `AET_REPO_SLUG` environment variables override
the derivation; a non-git directory falls back to its own basename (a single
path segment). The full on-disk layout is therefore
`~/.aet/telemetry/<main-worktree-dir>/<worktree-label>/{date}/{run-id}/{task-id}.jsonl`.
Readers (aet-retro, mine-learnings) import `derive_project_slug` from the
writer rather than re-deriving it — do not implement a second derivation.

Each `{task-id}.jsonl` file is append-only and newline-delimited JSON. Each line is a self-contained record. `last-run.json` is a single JSON object containing the run summary.

For instructions on enabling telemetry and mining it across projects, see `../../docs/telemetry-guide.md`.

## Record Types

### `stage`

One record per spawned agent session. Under `standard` isolation a single
session may span several stages, so `stage` is the session's target stage and
`stages` carries the ordered span; `full`/`minimal` isolation yield exact
per-stage records and `stages` is `null`.

| Field                 | Type                 | Description                                                                                                                                                                                                                              |
| --------------------- | -------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `type`                | string               | `"stage"`                                                                                                                                                                                                                                |
| `run_id`              | string               | UUID of the parent orchestrator run                                                                                                                                                                                                      |
| `task_id`             | string               | Queue task identifier                                                                                                                                                                                                                    |
| `plan_file`           | string               | Path to the plan markdown file                                                                                                                                                                                                           |
| `stage`               | string               | Session target stage, e.g. `implemented`, `reviewed`                                                                                                                                                                                     |
| `stages`              | list[string] \| null | Ordered stage span for group sessions; `null` otherwise                                                                                                                                                                                  |
| `agent_cli`           | string               | CLI used for the spawned session, e.g. `kimi`, `claude`                                                                                                                                                                                  |
| `isolation_level`     | string               | `minimal`, `standard`, or `full`                                                                                                                                                                                                         |
| `start_time`          | string               | ISO-8601 UTC timestamp                                                                                                                                                                                                                   |
| `end_time`            | string               | ISO-8601 UTC timestamp                                                                                                                                                                                                                   |
| `duration_seconds`    | float                | Computed from `start_time` and `end_time`                                                                                                                                                                                                |
| `exit_code`           | integer              | Process exit code from the stage session                                                                                                                                                                                                 |
| `result`              | string               | `"success"` if `exit_code == 0`, otherwise `"failure"`                                                                                                                                                                                   |
| `files_modified`      | list[string]         | Paths changed during the stage (optional)                                                                                                                                                                                                |
| `commits_created`     | integer \| null      | Number of commits produced (optional)                                                                                                                                                                                                    |
| `worktree_size_bytes` | integer \| null      | Size of the task worktree (optional)                                                                                                                                                                                                     |
| `token_count`         | integer \| null      | Total tokens (input incl. cache + output) from the CLI's usage source: `claude` `--output-format json` envelope; `kimi` post-exit parse of `~/.kimi-code` wire files (`step.end`, deduped by `uuid`); `null` otherwise — never estimated |
| `cost_estimate`       | float \| null        | Cost in USD: `claude` reports `total_cost_usd`; `kimi` derives it from a local price table keyed by `modelAlias` (`null` for subscription aliases like `kimi-code/kimi-for-coding` — never an invented number)                           |

### `run_summary`

One record per orchestrator run, stored as `last-run.json`.

| Field                         | Type            | Description                                                                                   |
| ----------------------------- | --------------- | --------------------------------------------------------------------------------------------- |
| `type`                        | string          | `"run_summary"`                                                                               |
| `run_id`                      | string          | UUID of the run                                                                               |
| `start_time`                  | string          | ISO-8601 UTC timestamp                                                                        |
| `end_time`                    | string          | ISO-8601 UTC timestamp                                                                        |
| `wall_clock_seconds`          | float           | Total elapsed run time                                                                        |
| `tasks_spawned`               | integer         | Tasks that entered the pipeline                                                               |
| `tasks_succeeded`             | integer         | Tasks that completed successfully                                                             |
| `tasks_failed`                | integer         | Tasks that failed                                                                             |
| `parallel_conflicts_detected` | integer         | Potential parallel-worktree conflicts detected                                                |
| `concurrency_cap`             | integer         | Maximum parallel tasks allowed                                                                |
| `total_tokens`                | integer \| null | Sum of non-null stage `token_count` values for this run; `null` when no stage reported usage  |
| `total_cost_usd`              | float \| null   | Sum of non-null stage `cost_estimate` values for this run; `null` when no stage reported cost |

### `environment_issue`

One record per environment or dependency problem detected in the worktree, such as a missing dependency directory that requires warmup.

| Field        | Type    | Description                                    |
| ------------ | ------- | ---------------------------------------------- |
| `type`       | string  | `"environment_issue"`                          |
| `run_id`     | string  | UUID of the parent orchestrator run            |
| `task_id`    | string  | Queue task identifier                          |
| `plan_file`  | string  | Path to the plan markdown file                 |
| `timestamp`  | string  | ISO-8601 UTC timestamp                         |
| `issue_type` | string  | E.g. `missing_dependency`                      |
| `dependency` | string  | Dependency path or identifier                  |
| `resolved`   | boolean | Whether the issue was resolved during this run |
| `message`    | string  | Optional human-readable description            |

### `test_run`

One record per test invocation, capturing command, scope, and outcome.

Records have two provenances:

- **Wire-derived** — after a kimi session exits, the orchestrator extracts
  every Bash test invocation from the session's wire log
  (`~/.kimi-code/sessions/<workDirKey>/<sessionId>/agents/*/wire.jsonl`) via
  `aet-work/lib/wirelog.py::extract_test_invocations`: each `tool.call` whose
  command matches the test-runner match list, paired with its `tool.result`
  event. `start_time`/`end_time` come from the wire events' top-level `time`
  (epoch millis, converted to ISO-8601), so `duration_seconds` is real.
  Non-kimi CLIs and unresolvable sessions emit nothing.
- **Verdict-derived** — a passing `qa` evidence verdict derives one record
  carrying the verdict's `generated_at` as both timestamps (duration is
  unmeasurable from a single timestamp).

`scope` is assigned by the single shared heuristic
`aet-work/lib/telemetry.py::classify_test_scope` — no emission site hardcodes
a scope value:

| Value        | Meaning                                                                                                            |
| ------------ | ------------------------------------------------------------------------------------------------------------------ |
| `full-suite` | Recognized test runner invoked bare or on the suite root (e.g. `pytest tests/`, `make validate`, `go test ./...`)  |
| `impact`     | Command names specific test files or subdirectories (e.g. `pytest tests/test_panel_serve.py`, `go test ./pkg/foo`) |
| `unknown`    | Command did not match a recognized runner shape                                                                    |

Null contract (R-3: unmeasured fields stay `null` — no zeros, no estimates):

- `start_time`/`end_time` are `null` when the corresponding wire event is
  absent (unpaired call) or lacks a usable `time`.
- `duration_seconds` is `null` whenever either timestamp is `null`.
- `exit_code` is `null` when the command failed without a parseable code
  (killed by timeout, premature close) or the call was never paired.
- `result` is `"unknown"` when `exit_code` is `null`.

| Field              | Type            | Description                                                                     |
| ------------------ | --------------- | ------------------------------------------------------------------------------- |
| `type`             | string          | `"test_run"`                                                                    |
| `run_id`           | string          | UUID of the parent orchestrator run                                             |
| `task_id`          | string          | Queue task identifier                                                           |
| `plan_file`        | string          | Path to the plan markdown file                                                  |
| `stage`            | string          | Pipeline stage where tests ran                                                  |
| `scope`            | string          | `full-suite`, `impact`, or `unknown` (see `classify_test_scope`)                |
| `test_command`     | string          | Shell command that was executed                                                 |
| `source`           | string          | `"wire"` (observed) or `"verdict"` (claimed) — see provenance below            |
| `start_time`       | string \| null  | ISO-8601 UTC timestamp; `null` when unmeasured                                  |
| `end_time`         | string \| null  | ISO-8601 UTC timestamp; `null` when unmeasured                                  |
| `duration_seconds` | float \| null   | Computed from `start_time` and `end_time`; `null` when either is missing        |
| `exit_code`        | integer \| null | Process exit code from the test command; `null` when unmeasured                 |
| `result`           | string          | `"success"` if `exit_code == 0`, `"failure"` if non-zero, `"unknown"` if `null` |
| `tests_total`      | integer \| null | Total tests executed (optional)                                                 |
| `tests_passed`     | integer \| null | Tests that passed (optional)                                                    |
| `tests_failed`     | integer \| null | Tests that failed (optional)                                                    |

Provenance contract (ADR-051): `source` is set by the emitter and is required.
`"wire"` records are **observed** — the command AET saw run, with real
timestamps and exit code and no test counts. `"verdict"` records are
**claimed** — derived from a passing `aet-qa` verdict, carrying the only test
counts in the archive with `start_time`, `end_time`, and `exit_code` all
`null`. The two are never aggregated together: timing and pass-rate figures
read `"wire"`, count figures read `"verdict"`, and records written before
ADR-051 have no `source`, are read as provenance-unknown, and are excluded from
both. Provenance is never inferred at read time from which fields are set.

### `learning_candidate`

One record per pattern that `aet-evolve` may mine for toolkit-level learnings.

| Field          | Type                   | Description                                   |
| -------------- | ---------------------- | --------------------------------------------- |
| `type`         | string                 | `"learning_candidate"`                        |
| `run_id`       | string                 | UUID of the parent orchestrator run           |
| `task_id`      | string                 | Queue task identifier                         |
| `plan_file`    | string                 | Path to the plan markdown file                |
| `stage`        | string                 | Pipeline stage where the pattern was observed |
| `pattern_type` | string                 | E.g. `repeated_format_fix`, `slow_stage`      |
| `description`  | string                 | Human-readable pattern description            |
| `evidence`     | dict[str, Any] \| null | Supporting data for the pattern (optional)    |
| `confidence`   | float \| null          | Confidence score from 0.0 to 1.0 (optional)   |

## Reading the Log

Use the `aet report` command to print a text summary:

```bash
aet report
aet report --since 2026-06-15T00:00:00Z
aet report --run-dir ~/.aet/telemetry/my-project/main/2026-06-30/<run-id>
```

Or read the log programmatically via `aet-work/lib/telemetry.py`:

```python
from telemetry import RunLogger, report

logger = RunLogger("/path/to/repo")
logger.append_record({...}, task_id="FEAT-001")

# Summarize the current project's archive
print(report())
```

## Guarantees

- Append-only: existing lines are never modified.
- Null-safe: optional fields may be `null` but are always present in the schema.
- Resilient: malformed lines are skipped when reading.
- Per-task files: each task writes to its own JSONL file, eliminating concurrent-write races.
