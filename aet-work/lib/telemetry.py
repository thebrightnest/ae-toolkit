"""Execution telemetry for the AE Toolkit orchestrator.

Provides append-only JSONL logging for stage and run-summary records.
Logs are written directly to the user-level telemetry archive so they survive
project worktree deletion. The old project-local ``.agents/execution.log.jsonl``
path is no longer used.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_ARCHIVE_DIR = Path.home() / ".aet" / "telemetry"
DEFAULT_DATE_FORMAT = "%Y-%m-%d"


def iso_now() -> str:
    """Return the current UTC time as an ISO-8601 string with a Z suffix."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_iso(ts: str) -> datetime:
    """Parse an ISO-8601 timestamp, accepting both '+00:00' and 'Z' suffixes."""
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def archive_dir() -> Path:
    """Return the telemetry archive root, respecting ``AET_TELEMETRY_ARCHIVE_DIR``."""
    env = os.environ.get("AET_TELEMETRY_ARCHIVE_DIR")
    return Path(env).expanduser() if env else DEFAULT_ARCHIVE_DIR


def resolve_repo_root(repo_root: str | Path | None = None) -> Path:
    """Resolve the repository root from args, env, git, or cwd."""
    if repo_root is not None:
        return Path(repo_root).resolve()

    env_root = os.environ.get("AET_REPO_ROOT")
    if env_root:
        return Path(env_root).resolve()

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return Path(result.stdout.strip()).resolve()
    except FileNotFoundError:
        pass

    return Path.cwd().resolve()


def derive_project_slug(repo_root: str | Path | None = None) -> str:
    """Derive owner/repo slug from the origin remote or directory name."""
    env_slug = os.environ.get("AET_PROJECT_ID") or os.environ.get("AET_REPO_SLUG")
    if env_slug:
        return env_slug

    repo_root = resolve_repo_root(repo_root)

    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            url = result.stdout.strip()
            if url.endswith(".git"):
                url = url[:-4]
            if ":" in url and "//" not in url:
                url = url.split(":", 1)[-1]
            parts = url.rstrip("/").split("/")
            return "/".join(parts[-2:])
    except FileNotFoundError:
        pass

    return repo_root.name


def _sanitize(value: Any, repo_root: Path) -> Any:
    """Recursively replace absolute repo and home paths with placeholders."""
    home = str(Path.home())
    root = str(repo_root)

    if isinstance(value, str):
        text = re.sub(re.escape(root), "{REPO_ROOT}", value)
        text = re.sub(re.escape(home), "{HOME}", text)
        return text
    if isinstance(value, list):
        return [_sanitize(item, repo_root) for item in value]
    if isinstance(value, dict):
        return {key: _sanitize(item, repo_root) for key, item in value.items()}
    return value


def new_run_id() -> str:
    """Generate a unique run identifier."""
    return str(uuid.uuid4())


class RunLogger:
    """One logger per orchestrator run.

    Writes per-task JSONL files directly into the telemetry archive so logs are
    preserved independently of project worktrees.
    """

    def __init__(
        self,
        repo_root: str | Path,
        run_id: str | None = None,
        date: str | None = None,
    ):
        self.repo_root = resolve_repo_root(repo_root)
        self.run_id = run_id or new_run_id()
        self.date = date or datetime.now(timezone.utc).strftime(DEFAULT_DATE_FORMAT)
        self.project_slug = derive_project_slug(self.repo_root)
        self._run_dir = (
            archive_dir() / self.project_slug / self.date / self.run_id
        )
        self._run_dir.mkdir(parents=True, exist_ok=True)

    @property
    def run_dir(self) -> Path:
        """Return the archive directory for this run."""
        return self._run_dir

    def task_log_path(self, task_id: str) -> Path:
        """Return the per-task JSONL path."""
        return self._run_dir / f"{task_id}.jsonl"

    def append_record(self, record: dict[str, Any], task_id: str) -> Path:
        """Append a single sanitized record to the task's log file."""
        path = self.task_log_path(task_id)
        sanitized = _sanitize(record, self.repo_root)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(sanitized, default=str) + "\n")
        return path

    def write_last_run(self, record: dict[str, Any]) -> Path:
        """Write the run completion summary as ``last-run.json``."""
        path = self._run_dir / "last-run.json"
        sanitized = _sanitize(record, self.repo_root)
        path.write_text(
            json.dumps(sanitized, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
        return path

    def copy_work_history(self, source: str | Path) -> Path | None:
        """Optionally copy the project's work-history JSONL into the run archive."""
        src = Path(source)
        if not src.exists():
            return None
        dest = self._run_dir / "work-history.jsonl"
        sanitized = _sanitize(src.read_text(encoding="utf-8"), self.repo_root)
        dest.write_text(sanitized, encoding="utf-8")
        return dest


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
    outcome: str | None = None,
    exit_code: int | None = None,
    task_ids: list[str] | None = None,
    final_stage: str | None = None,
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
        "outcome": outcome,
        "exit_code": exit_code,
        "task_ids": task_ids or [],
        "final_stage": final_stage,
    }


def loop_record(
    run_id: str,
    task_id: str,
    plan_file: str,
    stage: str,
    loop_type: str,
    iteration: int,
    start_time: str,
    end_time: str,
    exit_code: int,
    detail: str | None = None,
) -> dict[str, Any]:
    """Build a loop telemetry record (e.g., test retry or format fix)."""
    duration_seconds = (_parse_iso(end_time) - _parse_iso(start_time)).total_seconds()
    return {
        "type": "loop",
        "run_id": run_id,
        "task_id": task_id,
        "plan_file": plan_file,
        "stage": stage,
        "loop_type": loop_type,
        "iteration": iteration,
        "start_time": start_time,
        "end_time": end_time,
        "duration_seconds": duration_seconds,
        "exit_code": exit_code,
        "result": "success" if exit_code == 0 else "failure",
        "detail": detail,
    }


def environment_issue_record(
    run_id: str,
    task_id: str,
    plan_file: str,
    issue_type: str,
    dependency: str,
    resolved: bool = False,
    message: str | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Build an environment/dependency issue telemetry record."""
    return {
        "type": "environment_issue",
        "run_id": run_id,
        "task_id": task_id,
        "plan_file": plan_file,
        "timestamp": timestamp or iso_now(),
        "issue_type": issue_type,
        "dependency": dependency,
        "resolved": resolved,
        "message": message,
    }


def test_run_record(
    run_id: str,
    task_id: str,
    plan_file: str,
    stage: str,
    scope: str,
    test_command: str,
    start_time: str,
    end_time: str,
    exit_code: int,
    tests_total: int | None = None,
    tests_passed: int | None = None,
    tests_failed: int | None = None,
) -> dict[str, Any]:
    """Build an individual test-run telemetry record."""
    duration_seconds = (_parse_iso(end_time) - _parse_iso(start_time)).total_seconds()
    return {
        "type": "test_run",
        "run_id": run_id,
        "task_id": task_id,
        "plan_file": plan_file,
        "stage": stage,
        "scope": scope,
        "test_command": test_command,
        "start_time": start_time,
        "end_time": end_time,
        "duration_seconds": duration_seconds,
        "exit_code": exit_code,
        "result": "success" if exit_code == 0 else "failure",
        "tests_total": tests_total,
        "tests_passed": tests_passed,
        "tests_failed": tests_failed,
    }


def learning_candidate_record(
    run_id: str,
    task_id: str,
    plan_file: str,
    stage: str,
    pattern_type: str,
    description: str,
    evidence: dict[str, Any] | None = None,
    confidence: float | None = None,
) -> dict[str, Any]:
    """Build a learning-candidate telemetry record for aet-evolve mining."""
    return {
        "type": "learning_candidate",
        "run_id": run_id,
        "task_id": task_id,
        "plan_file": plan_file,
        "stage": stage,
        "pattern_type": pattern_type,
        "description": description,
        "evidence": evidence or {},
        "confidence": confidence,
    }


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    """Read and parse a JSONL file, skipping malformed lines."""
    path = Path(path)
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


def _scan_records(root: Path, since: str | None = None) -> list[dict[str, Any]]:
    """Read all task JSONL records under a directory tree."""
    records: list[dict[str, Any]] = []
    if not root.exists():
        return records

    for path in root.rglob("*.jsonl"):
        records.extend(read_jsonl(path))

    if since:
        since_dt = _parse_iso(since)
        records = [
            r
            for r in records
            if _parse_iso(
                r.get("start_time") or r.get("timestamp") or "1970-01-01T00:00:00Z"
            )
            >= since_dt
        ]

    return records


def report(
    target: str | Path | None = None,
    since: str | None = None,
    project_slug: str | None = None,
) -> str:
    """Generate a text summary of recorded executions.

    ``target`` may be:
    - a project slug (scans the whole project archive)
    - a run directory path (scans that run)
    - a single task JSONL file
    - ``None`` (derives project slug from cwd and scans its archive)
    """
    root: Path

    if target is not None:
        path = Path(target).expanduser()
        if path.is_file() and path.suffix == ".jsonl":
            records = read_jsonl(path)
            if since:
                since_dt = _parse_iso(since)
                records = [
                    r
                    for r in records
                    if _parse_iso(
                        r.get("start_time") or r.get("timestamp") or "1970-01-01T00:00:00Z"
                    )
                    >= since_dt
                ]
            summaries = [r for r in records if r.get("type") == "run_summary"]
            stages = [r for r in records if r.get("type") == "stage"]
            loops = [r for r in records if r.get("type") == "loop"]
            environment_issues = [r for r in records if r.get("type") == "environment_issue"]
            return _format_report(summaries, stages, loops, environment_issues, 1 if records else 0)

        if path.is_dir():
            root = path
        else:
            root = archive_dir() / path
    elif project_slug:
        root = archive_dir() / project_slug
    else:
        root = archive_dir() / derive_project_slug()

    records = _scan_records(root, since=since)
    summaries = [r for r in records if r.get("type") == "run_summary"]
    stages = [r for r in records if r.get("type") == "stage"]
    loops = [r for r in records if r.get("type") == "loop"]
    environment_issues = [r for r in records if r.get("type") == "environment_issue"]

    runs_observed = len({r.get("run_id") for r in records if r.get("run_id")})
    return _format_report(
        summaries, stages, loops, environment_issues, runs_observed
    )


def _format_report(
    summaries: list[dict[str, Any]],
    stages: list[dict[str, Any]],
    loops: list[dict[str, Any]],
    environment_issues: list[dict[str, Any]],
    runs_observed: int,
) -> str:
    total_runs = len(summaries)
    total_wall = sum(r.get("wall_clock_seconds", 0.0) for r in summaries)
    total_spawned = sum(r.get("tasks_spawned", 0) for r in summaries)
    total_succeeded = sum(r.get("tasks_succeeded", 0) for r in summaries)
    total_failed = sum(r.get("tasks_failed", 0) for r in summaries)

    lines = [
        "AE Toolkit Execution Report",
        "=" * 40,
        f"Runs: {total_runs}",
        f"Runs observed: {runs_observed}",
        f"Tasks spawned: {total_spawned}",
        f"Succeeded: {total_succeeded}",
        f"Failed: {total_failed}",
        f"Wall-clock time: {total_wall:.1f}s",
        f"Average isolation level: {_average_isolation_level(stages)}",
        f"Loops: {len(loops)}",
        f"Environment issues: {len(environment_issues)}",
    ]
    return "\n".join(lines) + "\n"
