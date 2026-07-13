# Telemetry Log Schema

The orchestrator writes execution telemetry directly to the user-level archive:

```
~/.aet/telemetry/{project-slug}/{date}/{run-id}/
    ├── last-run.json
    ├── {task-id}.jsonl
    └── ...
```

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

| Field              | Type            | Description                                            |
| ------------------ | --------------- | ------------------------------------------------------ |
| `type`             | string          | `"test_run"`                                           |
| `run_id`           | string          | UUID of the parent orchestrator run                    |
| `task_id`          | string          | Queue task identifier                                  |
| `plan_file`        | string          | Path to the plan markdown file                         |
| `stage`            | string          | Pipeline stage where tests ran                         |
| `scope`            | string          | E.g. `full`, `impact`                                  |
| `test_command`     | string          | Shell command that was executed                        |
| `start_time`       | string          | ISO-8601 UTC timestamp                                 |
| `end_time`         | string          | ISO-8601 UTC timestamp                                 |
| `duration_seconds` | float           | Computed from `start_time` and `end_time`              |
| `exit_code`        | integer         | Process exit code from the test command                |
| `result`           | string          | `"success"` if `exit_code == 0`, otherwise `"failure"` |
| `tests_total`      | integer \| null | Total tests executed (optional)                        |
| `tests_passed`     | integer \| null | Tests that passed (optional)                           |
| `tests_failed`     | integer \| null | Tests that failed (optional)                           |

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
aet report --run-dir ~/.aet/telemetry/my-project/2026-06-30/<run-id>
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
