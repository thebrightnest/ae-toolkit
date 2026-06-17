# Telemetry Log Schema

The orchestrator writes execution telemetry to `.agents/execution.log.jsonl`. The log is append-only and newline-delimited JSON. Each line is a self-contained record.

## Record Types

### `stage`

One record per pipeline stage executed for a task.

| Field                 | Type            | Description                                               |
| --------------------- | --------------- | --------------------------------------------------------- |
| `type`                | string          | `"stage"`                                                 |
| `run_id`              | string          | UUID of the parent orchestrator run                       |
| `task_id`             | string          | Queue task identifier                                     |
| `plan_file`           | string          | Path to the plan markdown file                            |
| `stage`               | string          | Stage name, e.g. `implemented`, `reviewed`, `qa-complete` |
| `agent_cli`           | string          | CLI used for the spawned session, e.g. `kimi`, `claude`   |
| `isolation_level`     | string          | `minimal`, `standard`, or `full`                          |
| `start_time`          | string          | ISO-8601 UTC timestamp                                    |
| `end_time`            | string          | ISO-8601 UTC timestamp                                    |
| `duration_seconds`    | float           | Computed from `start_time` and `end_time`                 |
| `exit_code`           | integer         | Process exit code from the stage session                  |
| `result`              | string          | `"success"` if `exit_code == 0`, otherwise `"failure"`    |
| `files_modified`      | list[string]    | Paths changed during the stage (optional)                 |
| `commits_created`     | integer \| null | Number of commits produced (optional)                     |
| `worktree_size_bytes` | integer \| null | Size of the task worktree (optional)                      |
| `token_count`         | integer \| null | Estimated token usage (optional)                          |
| `cost_estimate`       | float \| null   | Estimated cost in USD (optional)                          |

### `run_summary`

One record per orchestrator run.

| Field                         | Type    | Description                                    |
| ----------------------------- | ------- | ---------------------------------------------- |
| `type`                        | string  | `"run_summary"`                                |
| `run_id`                      | string  | UUID of the run                                |
| `start_time`                  | string  | ISO-8601 UTC timestamp                         |
| `end_time`                    | string  | ISO-8601 UTC timestamp                         |
| `wall_clock_seconds`          | float   | Total elapsed run time                         |
| `tasks_spawned`               | integer | Tasks that entered the pipeline                |
| `tasks_succeeded`             | integer | Tasks that completed successfully              |
| `tasks_failed`                | integer | Tasks that failed                              |
| `parallel_conflicts_detected` | integer | Potential parallel-worktree conflicts detected |
| `concurrency_cap`             | integer | Maximum parallel tasks allowed                 |

## Reading the Log

Use the `aet-work report` command to print a text summary:

```bash
python3 ~/.claude/skills/aet-work/bin/report
python3 ~/.claude/skills/aet-work/bin/report --since 2026-06-15T00:00:00Z
```

Or read the log programmatically via `aet-work/lib/telemetry.py`:

```python
from telemetry import read_log, report

records = read_log(".agents/execution.log.jsonl")
print(report(".agents/execution.log.jsonl"))
```

## Guarantees

- Append-only: existing lines are never modified.
- Null-safe: optional fields may be `null` but are always present in the schema.
- Resilient: malformed lines are skipped when reading.
