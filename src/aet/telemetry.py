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
import shutil
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# Re-export the neutral identity helper so existing callers keep working.
from aet import test_runners
from aet.project_id import derive_project_slug, resolve_repo_root  # noqa: F401

DEFAULT_ARCHIVE_DIR = Path.home() / ".aet" / "telemetry"
DEFAULT_DATE_FORMAT = "%Y-%m-%d"

# Maximum number of raw agent-output lines included in a stage record's excerpt.
COMPLETION_REPORT_EXCERPT_LINES = 10


TEST_SCOPE_FULL_SUITE = "full-suite"
TEST_SCOPE_IMPACT = "impact"
TEST_SCOPE_UNKNOWN = "unknown"

# File suffixes that mark a command argument as a specific test file.
_TEST_FILE_SUFFIXES = (".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs")

# Arguments naming these roots run the whole suite, not an impact subset.
_SUITE_ROOT_ARGS = {".", "test", "tests", "./..."}

# The marker `change_scope --explain` prints so a `make` invocation's resolved
# pytest targets survive into the command's output. `make validate` runs pytest
# in a sub-make the session log never sees, so the command string alone cannot
# say how much of the suite ran; this marker is the interface that closes that
# gap (tap-06). The prefix and grammar live here, with the reader, so there is
# one definition of the contract.
TEST_SCOPE_MARKER_PREFIX = "AET_TEST_SCOPE_TARGETS:"

# A resolved target is a path under `tests/`. Matched to reject anything else:
# the marker is data used to pick a label, never executed or path-resolved.
_RESOLVED_TARGET_RE = re.compile(r"^tests/[A-Za-z0-9._-]*(?:/[A-Za-z0-9._-]+)*/?$")


def classify_test_scope(command: str, output: str | None = None) -> str:
    """Classify a test command's scope: ``full-suite``, ``impact``, ``unknown``.

    The single scope heuristic for every ``test_run`` emission site. The
    command is resolved through the shared runner registry
    (``test_runners.resolve_test_command``) — the same parse that feeds
    ``wirelog.is_test_command``. A command naming specific test files or
    subdirectories is ``impact``; a recognized runner invoked bare (or on the
    suite root) is ``full-suite``; anything else is ``unknown``.

    ``make`` is the one runner whose command string cannot say how much of the
    suite ran: ``make validate`` resolves its pytest targets at runtime and
    runs them in a sub-make the session log never sees. For ``make`` only,
    the command's ``output`` is consulted for the
    :data:`TEST_SCOPE_MARKER_PREFIX` marker that ``change_scope --explain``
    prints, and the resolved targets it carries decide the label. Every other
    command — and any ``make`` run whose output has no valid marker — takes
    the pure command-string heuristic, unchanged: auditable, stable, and
    environment-independent.
    """
    resolved = test_runners.resolve_test_command(command)
    if resolved is None:
        return TEST_SCOPE_UNKNOWN
    runner, runner_args = resolved
    if runner == "make":
        marker_scope = _scope_from_marker(output)
        if marker_scope is not None:
            return marker_scope
    for arg in runner_args:
        if _is_scope_narrowing_arg(arg):
            return TEST_SCOPE_IMPACT
    return TEST_SCOPE_FULL_SUITE


def _scope_from_marker(output: str | None) -> str | None:
    """Scope from the resolved-targets marker in a command's output, or None.

    ``None`` means "no usable marker" and leaves the caller on the heuristic
    fallback — the conservative answer under ADR-049's fail-toward-more-tests
    bias.

    Every marker in the output must agree. The output of a ``make validate``
    contains its own pytest run, and pytest echoes captured stdout on failure —
    so a failing ``change_scope`` test reprints a marker naming *its fixture's*
    targets, unindented, below the real one. Trusting the last marker recorded
    such a run as ``impact`` when it had in fact run everything, understating
    suite cost exactly when tests were failing. Repeated identical markers (one
    shell call running ``make validate`` twice) still classify; disagreement is
    not resolvable from the output alone, so it falls back.

    The marker is data. Its targets are matched against the resolved-target
    grammar and used only to pick a label; nothing read here is executed,
    interpolated, or path-resolved, and a single bad token discards the whole
    output rather than half-trusting it.
    """
    if not output:
        return None
    seen: set[tuple[str, ...]] = set()
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped.startswith(TEST_SCOPE_MARKER_PREFIX):
            continue
        targets = stripped[len(TEST_SCOPE_MARKER_PREFIX):].split()
        if not targets or not all(_is_resolved_target(t) for t in targets):
            return None
        seen.add(tuple(targets))
    if len(seen) != 1:
        return None
    if seen == {("tests/",)}:
        return TEST_SCOPE_FULL_SUITE
    return TEST_SCOPE_IMPACT


def _is_resolved_target(token: str) -> bool:
    """Whether a marker token is a well-formed pytest target under ``tests/``."""
    if ".." in token:
        return False
    return _RESOLVED_TARGET_RE.match(token) is not None


def _is_scope_narrowing_arg(arg: str) -> bool:
    """Return True when an argument names a specific test file or directory."""
    if arg.startswith("-"):
        return False
    normalized = arg.rstrip("/")
    if normalized in _SUITE_ROOT_ARGS:
        return False
    if arg.endswith(_TEST_FILE_SUFFIXES):
        return True
    return "/" in normalized


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
        self._run_dir = archive_dir() / self.project_slug / self.date / self.run_id
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
    stages: list[str] | None = None,
    actual_stages: list[str] | None = None,
    failure_class: str | None = None,
    plan_snapshot: dict[str, Any] | None = None,
    attempt: int = 1,
    output_excerpt: str | None = None,
    session_identifier: str | None = None,
    targeted_tests: list[str] | None = None,
) -> dict[str, Any]:
    """Build a per-stage telemetry record.

    ``stage`` is the target stage of the spawned session. For group sessions
    (standard isolation) ``stages`` carries the ordered list of stage names the
    single session spanned; it is ``None`` for exact per-stage sessions.

    ``actual_stages`` is the ordered list of stage names that actually ran in
    the session. When omitted it defaults to ``[stage]`` so consumers can always
    rely on its presence.

    ``failure_class`` carries the nsr-01 taxonomy class for failed sessions and
    is ``None`` for successful sessions.

    ``plan_snapshot`` is a shallow copy of the plan frontmatter fields that
    influence pipeline routing, captured at emission time so analytics do not
    need to re-read plan files.

    ``attempt`` counts how many times this task+stage combination has been
    emitted within the run (starting at 1).

    ``output_excerpt`` is a bounded snippet of raw agent stdout/stderr captured
    on failure; it is displayed by the completion report, never interpreted.

    ``session_identifier`` is an adapter-resolved session identifier (a session
    id for both kimi and Claude) that locates the session log which produced
    this stage record, or ``None`` when the reference could not be resolved
    (ADR-031). The documented resolution rule lives in
    ``docs/telemetry-guide.md``.
    """
    duration_seconds = (_parse_iso(end_time) - _parse_iso(start_time)).total_seconds()
    return {
        "type": "stage",
        "run_id": run_id,
        "task_id": task_id,
        "plan_file": plan_file,
        "stage": stage,
        "stages": stages,
        "actual_stages": actual_stages if actual_stages is not None else [stage],
        "failure_class": failure_class,
        "plan_snapshot": plan_snapshot,
        "attempt": attempt,
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
        "output_excerpt": output_excerpt,
        "session_identifier": session_identifier,
        "targeted_tests": targeted_tests or [],
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
    leftover: dict[str, int] | None = None,
    total_tokens: int | None = None,
    total_cost_usd: float | None = None,
) -> dict[str, Any]:
    """Build a per-run summary telemetry record.

    ``total_tokens`` / ``total_cost_usd`` aggregate the run's stage records
    (summed over non-null values; ``None`` when no stage reported usage).
    """
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
        "leftover": leftover or {},
        "total_tokens": total_tokens,
        "total_cost_usd": total_cost_usd,
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


TEST_RUN_SOURCES = ("wire", "verdict")


def test_run_record(
    run_id: str,
    task_id: str,
    plan_file: str,
    stage: str,
    scope: str,
    test_command: str,
    source: str,
    start_time: str | None,
    end_time: str | None,
    exit_code: int | None,
    tests_total: int | None = None,
    tests_passed: int | None = None,
    tests_failed: int | None = None,
) -> dict[str, Any]:
    """Build an individual test-run telemetry record.

    Null contract: ``start_time``/``end_time`` are optional; ``duration_seconds``
    is ``None`` when either is missing — never estimated. A ``None`` ``exit_code``
    (unmeasured, e.g. a killed or unpaired command) yields ``result: "unknown"``.

    Provenance contract (ADR-051): ``source`` is ``"wire"`` for an observed run
    read off the session log, ``"verdict"`` for a run claimed by a QA verdict.
    It is required and validated so a new emission site cannot omit it and
    readers never have to infer provenance from which fields happen to be set.
    """
    if source not in TEST_RUN_SOURCES:
        raise ValueError(f"source must be one of {TEST_RUN_SOURCES}, got {source!r}")
    duration_seconds = None
    if start_time is not None and end_time is not None:
        duration_seconds = (_parse_iso(end_time) - _parse_iso(start_time)).total_seconds()
    if exit_code == 0:
        result = "success"
    elif exit_code is None:
        result = "unknown"
    else:
        result = "failure"
    return {
        "type": "test_run",
        "run_id": run_id,
        "task_id": task_id,
        "plan_file": plan_file,
        "stage": stage,
        "scope": scope,
        "test_command": test_command,
        "source": source,
        "start_time": start_time,
        "end_time": end_time,
        "duration_seconds": duration_seconds,
        "exit_code": exit_code,
        "result": result,
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


_LEGACY_RUN_DIR_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-(.+)$")


def _parse_date_segment(segment: str) -> datetime | None:
    """Parse a ``YYYY-MM-DD`` archive path segment as midnight UTC, or None."""
    try:
        return datetime.strptime(segment, DEFAULT_DATE_FORMAT).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _iter_project_run_dirs(project_dir: Path):
    """Yield ``(run_dir, date_segment, run_id)`` within one project subtree.

    Current layout: ``{date}/{run-id}/``; legacy layout: ``{date}-{run-id}/``.
    Non-matching directories and symlinks are skipped — a symlinked dir must
    never become a recursive-deletion target.
    """
    if not project_dir.is_dir():
        return
    for child in sorted(project_dir.iterdir()):
        if child.is_symlink() or not child.is_dir():
            continue
        legacy = _LEGACY_RUN_DIR_RE.match(child.name)
        if legacy:
            yield child, legacy.group(1), legacy.group(2)
            continue
        if _parse_date_segment(child.name) is None:
            continue
        for run_dir in sorted(p for p in child.iterdir() if p.is_dir() and not p.is_symlink()):
            yield run_dir, child.name, run_dir.name


def _iter_run_dirs(root: Path):
    """Yield ``(run_dir, date_segment, run_id)`` across all projects under ``root``."""
    if not root.exists():
        return
    for project_dir in sorted(p for p in root.iterdir() if p.is_dir() and not p.is_symlink()):
        yield from _iter_project_run_dirs(project_dir)


def find_run_dir(run_id: str, repo_root: str | Path | None = None) -> Path | None:
    """Locate a telemetry run directory by ``run_id``.

    Searches the telemetry archive under the project slug derived from
    ``repo_root``. Returns ``None`` when the archive or run id is not found.
    """
    root = archive_dir()
    slug = derive_project_slug(repo_root) if repo_root is not None else derive_project_slug()
    project_dir = root / slug
    if not project_dir.is_dir():
        return None
    for date_dir in sorted(project_dir.iterdir(), reverse=True):
        if not date_dir.is_dir():
            continue
        candidate = date_dir / run_id
        if candidate.is_dir():
            return candidate
    return None


def _newest_mtime(path: Path) -> float:
    """Return the newest mtime within ``path``, including the dir itself."""
    newest = path.stat().st_mtime
    for entry in path.rglob("*"):
        try:
            newest = max(newest, entry.stat().st_mtime)
        except OSError:
            continue
    return newest


def _dir_size(path: Path) -> int:
    """Return the total size in bytes of all files under ``path``."""
    total = 0
    for entry in path.rglob("*"):
        try:
            if entry.is_file():
                total += entry.stat().st_size
        except OSError:
            continue
    return total


def _protected_run_id(run_dir: Path, run_id: str, protected: frozenset) -> bool:
    """Return True if the run dir's id or its summary's run_id is protected."""
    if run_id in protected:
        return True
    summary = run_dir / "last-run.json"
    if summary.is_file():
        try:
            data = json.loads(summary.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = None
        if isinstance(data, dict) and data.get("run_id") in protected:
            return True
    return False


def prune_archive(
    days: int,
    root: str | Path | None = None,
    force: bool = False,
    protected_run_ids: frozenset | set | None = None,
) -> dict[str, Any]:
    """Prune telemetry run dirs older than ``days``, protecting active runs.

    A run dir is a deletion candidate only when both its date path segment
    parses before the cutoff and its newest recursive mtime is older than the
    cutoff — a live run's dir always has a fresh mtime and therefore survives
    (the wfd-03 incident class). Runs in ``protected_run_ids`` (lease holder,
    ``AET_RUN_ID``) are never deleted. ``force=False`` (default) deletes
    nothing and only reports. ``root`` narrows the walk to a single project
    subtree (``{archive}/{project}``) and must resolve inside the archive
    root — anything else raises ``ValueError``, since prune performs
    recursive deletion and must never escape the archive. ``days`` must be
    non-negative; a negative value would place the cutoff in the future and
    mark every run as a candidate, so it raises ``ValueError``. Returns a
    dict with ``candidates``, ``deleted``, ``kept_protected``, and
    ``bytes_reclaimed``.
    """
    if days < 0:
        raise ValueError(f"prune days must be non-negative, got {days}")
    protected = frozenset(protected_run_ids or ())
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    cutoff_ts = cutoff.timestamp()
    if root is not None:
        scope = Path(root).expanduser()
        resolved = scope.resolve()
        archive_root = archive_dir().resolve()
        if not (resolved == archive_root or resolved.is_relative_to(archive_root)):
            raise ValueError(f"prune root escapes the telemetry archive: {scope}")
        run_dirs = _iter_project_run_dirs(scope)
    else:
        scope = archive_dir()
        run_dirs = _iter_run_dirs(scope)

    candidates: list[str] = []
    deleted: list[str] = []
    kept_protected: list[str] = []
    bytes_reclaimed = 0

    for run_dir, date_segment, run_id in run_dirs:
        dir_date = _parse_date_segment(date_segment)
        if dir_date is None or dir_date >= cutoff:
            continue
        if _newest_mtime(run_dir) >= cutoff_ts:
            continue
        if _protected_run_id(run_dir, run_id, protected):
            kept_protected.append(str(run_dir))
            continue
        candidates.append(str(run_dir))
        if force:
            bytes_reclaimed += _dir_size(run_dir)
            shutil.rmtree(run_dir)
            deleted.append(str(run_dir))

    if force:
        deleted.extend(_sweep_stale_empty_dirs(scope, cutoff_ts))

    return {
        "candidates": candidates,
        "deleted": deleted,
        "kept_protected": kept_protected,
        "bytes_reclaimed": bytes_reclaimed,
    }


def _sweep_stale_empty_dirs(root: Path, cutoff_ts: float) -> list[str]:
    """Delete empty date/project dirs whose mtime predates the cutoff."""
    removed: list[str] = []
    if not root.exists():
        return removed
    # Deepest-first so date dirs empty out before their project dir is checked.
    # rmdir refuses non-empty dirs, so emptiness is enforced by the attempt.
    for dirpath, _dirnames, _filenames in os.walk(root, topdown=False):
        path = Path(dirpath)
        if path == root:
            continue
        try:
            if path.stat().st_mtime >= cutoff_ts:
                continue
            path.rmdir()
        except OSError:
            continue
        removed.append(str(path))
    return removed


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
            if _parse_iso(r.get("start_time") or r.get("timestamp") or "1970-01-01T00:00:00Z") >= since_dt
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
                    if _parse_iso(r.get("start_time") or r.get("timestamp") or "1970-01-01T00:00:00Z") >= since_dt
                ]
            summaries = [r for r in records if r.get("type") == "run_summary"]
            stages = [r for r in records if r.get("type") == "stage"]
            environment_issues = [r for r in records if r.get("type") == "environment_issue"]
            return _format_report(summaries, stages, environment_issues, 1 if records else 0)

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
    environment_issues = [r for r in records if r.get("type") == "environment_issue"]

    runs_observed = len({r.get("run_id") for r in records if r.get("run_id")})
    return _format_report(summaries, stages, environment_issues, runs_observed)


def _format_report(
    summaries: list[dict[str, Any]],
    stages: list[dict[str, Any]],
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
        f"Environment issues: {len(environment_issues)}",
    ]
    return "\n".join(lines) + "\n"
