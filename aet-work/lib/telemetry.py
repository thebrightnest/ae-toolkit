"""Execution telemetry for the AE Toolkit orchestrator.

Provides append-only JSONL logging for stage and run-summary records,
null-safe handling of optional token/cost fields, and a simple text report.
"""

from __future__ import annotations

import json
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_LOG_PATH = ".agents/execution.log.jsonl"


def iso_now() -> str:
    """Return the current UTC time as an ISO-8601 string with a Z suffix."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_iso(ts: str) -> datetime:
    """Parse an ISO-8601 timestamp, accepting both '+00:00' and 'Z' suffixes."""
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _ensure_log_path(path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def append_record(record: dict[str, Any], log_path: str | Path = DEFAULT_LOG_PATH) -> None:
    """Append a single JSON record to the telemetry log."""
    path = _ensure_log_path(log_path)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=str) + "\n")


def new_run_id() -> str:
    """Generate a unique run identifier."""
    return str(uuid.uuid4())


def stage_record(
    run_id: str,
    task_id: str,
    plan_file: str,
    stage: str,
    agent_cli: str,
    isolation_level: str,
    start_time: str,
    end_time: str,
    exit_code: int,
    files_modified: list[str] | None = None,
    commits_created: int | None = None,
    worktree_size_bytes: int | None = None,
    token_count: int | None = None,
    cost_estimate: float | None = None,
) -> dict[str, Any]:
    """Build a per-stage telemetry record."""
    duration_seconds = (_parse_iso(end_time) - _parse_iso(start_time)).total_seconds()
    return {
        "type": "stage",
        "run_id": run_id,
        "task_id": task_id,
        "plan_file": plan_file,
        "stage": stage,
        "agent_cli": agent_cli,
        "isolation_level": isolation_level,
        "start_time": start_time,
        "end_time": end_time,
        "duration_seconds": duration_seconds,
        "exit_code": exit_code,
        "result": "success" if exit_code == 0 else "failure",
        "files_modified": files_modified or [],
        "commits_created": commits_created,
        "worktree_size_bytes": worktree_size_bytes,
        "token_count": token_count,
        "cost_estimate": cost_estimate,
    }


def run_summary_record(
    run_id: str,
    start_time: str,
    end_time: str,
    tasks_spawned: int,
    tasks_succeeded: int,
    tasks_failed: int,
    parallel_conflicts_detected: int = 0,
    concurrency_cap: int = 4,
) -> dict[str, Any]:
    """Build a per-run summary telemetry record."""
    wall_clock_seconds = (_parse_iso(end_time) - _parse_iso(start_time)).total_seconds()
    return {
        "type": "run_summary",
        "run_id": run_id,
        "start_time": start_time,
        "end_time": end_time,
        "wall_clock_seconds": wall_clock_seconds,
        "tasks_spawned": tasks_spawned,
        "tasks_succeeded": tasks_succeeded,
        "tasks_failed": tasks_failed,
        "parallel_conflicts_detected": parallel_conflicts_detected,
        "concurrency_cap": concurrency_cap,
    }


def read_log(log_path: str | Path = DEFAULT_LOG_PATH) -> list[dict[str, Any]]:
    """Read and parse the telemetry log, skipping malformed lines."""
    path = Path(log_path)
    if not path.exists():
        return []

    records: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def _average_isolation_level(stages: list[dict[str, Any]]) -> str:
    """Return the nearest isolation level from the observed stage records."""
    levels = [s.get("isolation_level") for s in stages if s.get("isolation_level")]
    if not levels:
        return "n/a"

    level_values = {"minimal": 1, "standard": 2, "full": 3}
    counts = Counter(levels)
    total_value = sum(level_values.get(level, 0) * count for level, count in counts.items())
    avg_value = total_value / len(levels)
    return min(level_values, key=lambda level: abs(level_values[level] - avg_value))


def report(log_path: str | Path = DEFAULT_LOG_PATH, since: str | None = None) -> str:
    """Generate a text summary of recorded executions."""
    records = read_log(log_path)

    if since:
        since_dt = _parse_iso(since)
        records = [
            r
            for r in records
            if _parse_iso(r.get("start_time", "1970-01-01T00:00:00Z")) >= since_dt
        ]

    summaries = [r for r in records if r.get("type") == "run_summary"]
    stages = [r for r in records if r.get("type") == "stage"]

    total_runs = len(summaries)
    total_wall = sum(r.get("wall_clock_seconds", 0.0) for r in summaries)
    total_spawned = sum(r.get("tasks_spawned", 0) for r in summaries)
    total_succeeded = sum(r.get("tasks_succeeded", 0) for r in summaries)
    total_failed = sum(r.get("tasks_failed", 0) for r in summaries)

    lines = [
        "AE Toolkit Execution Report",
        "=" * 40,
        f"Runs: {total_runs}",
        f"Tasks spawned: {total_spawned}",
        f"Succeeded: {total_succeeded}",
        f"Failed: {total_failed}",
        f"Wall-clock time: {total_wall:.1f}s",
        f"Average isolation level: {_average_isolation_level(stages)}",
    ]
    return "\n".join(lines) + "\n"
