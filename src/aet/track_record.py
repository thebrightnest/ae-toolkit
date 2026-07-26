"""Track-record reader and zero-review policy logic.

Computes per-class clean-merge counts from the telemetry archive and the
settled history log, and decides whether a task qualifies for zero-review
auto-merge. The shipped default policy is empty: nothing auto-merges.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable

from aet import (
    evidence,  # noqa: I001
    plan_parser,  # noqa: I001
    telemetry,  # noqa: I001
)

REQUIRED_VERDICT_KINDS = ("qa", "review", "cso", "sync-docs")

DEFAULT_POLICY_PATH = ".agents/review-policy.json"


def read_history_tasks(history_file: str | Path) -> list[dict[str, Any]]:
    """Read settled task records from the append-only history log."""
    path = Path(history_file)
    if not path.exists():
        return []
    tasks: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                tasks.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return tasks


def iter_telemetry_task_records(
    task_id: str,
    archive_dir: str | Path | None = None,
    project_slug: str | None = None,
) -> Iterable[dict[str, Any]]:
    """Yield stage/test_run records for ``task_id`` across the telemetry archive.

    Only ``type`` values that describe a stage or test execution are yielded
    (``stage``, ``test_run``). Run summaries and learning candidates are
    ignored for clean-merge analysis.
    """
    root = Path(archive_dir).expanduser() if archive_dir else telemetry.archive_dir()
    slug = project_slug if project_slug else telemetry.derive_project_slug()
    project_dir = root / slug
    if not project_dir.exists():
        return
    for run_dir, _date_segment, _run_id in telemetry._iter_project_run_dirs(project_dir):
        log = run_dir / f"{task_id}.jsonl"
        if not log.exists():
            continue
        with open(log, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if record.get("type") in ("stage", "test_run"):
                    yield record


def _has_failed_stage(records: Iterable[dict[str, Any]]) -> bool:
    """Return True if any stage telemetry record reports a failure."""
    for record in records:
        if record.get("type") != "stage":
            continue
        if record.get("result") == "failure":
            return True
        if record.get("exit_code") not in (0, None):
            return True
    return False


def _stage_names(record: dict[str, Any]) -> list[str]:
    """Return the stage names represented by a record.

    Prefer the explicit ``actual_stages`` list when present (telemetry schema
    v2); otherwise fall back to the legacy single ``stage`` field.
    """
    actual = record.get("actual_stages")
    if isinstance(actual, list) and all(isinstance(s, str) for s in actual):
        return actual
    stage = record.get("stage")
    if isinstance(stage, str):
        return [stage]
    return []


def _repeated_stage_count(records: Iterable[dict[str, Any]]) -> int:
    """Return the number of stage telemetry records beyond the first per stage."""
    counts: dict[str, int] = {}
    for record in records:
        if record.get("type") != "stage":
            continue
        for stage in _stage_names(record):
            counts[stage] = counts.get(stage, 0) + 1
    return sum(max(0, count - 1) for count in counts.values())


def _has_repeated_stage(records: Iterable[dict[str, Any]]) -> bool:
    """Return True if any stage name appears more than once."""
    return _repeated_stage_count(records) > 0


def _failed_reentry_count(history: list[dict[str, Any]]) -> int:
    """Return the number of history transitions that re-enter after failure."""
    return sum(1 for entry in history if entry.get("from") == "failed")


def _has_reentry_from_failed(history: list[dict[str, Any]]) -> bool:
    """Return True if the task was ever re-started after entering failed."""
    return _failed_reentry_count(history) > 0


def rework_count(
    task: dict[str, Any],
    archive_dir: str | Path | None = None,
    project_slug: str | None = None,
) -> int:
    """Return the total rework count for a task.

    Rework is the sum of:
      - repeated stage telemetry records beyond the first per stage name
      - history transitions with ``from == "failed"``
    """
    task_id = task.get("id")
    records: Iterable[dict[str, Any]] = []
    if task_id:
        records = iter_telemetry_task_records(
            task_id=task_id,
            archive_dir=archive_dir,
            project_slug=project_slug,
        )
    history = task.get("history", [])
    return _repeated_stage_count(records) + _failed_reentry_count(history)


def _required_verdicts_pass(
    task: dict[str, Any],
    project_slug: str | None,
    reports_dir: str | Path | None,
) -> bool:
    """Return True when every required verdict file exists and is 'pass'.

    Required verdict kinds are derived from the task's plan file so they
    respect routing-aware gate rules. If the plan file is missing or unreadable,
    fall back to the historical ``REQUIRED_VERDICT_KINDS`` default (all four
    gates) to preserve existing behavior for legacy settled tasks.

    Uses the canonical archive path (not the run-time env-var precedence) so
    historical ledger reads are not redirected by a current stage's evidence
    environment.
    """
    plan_file = task.get("plan_file")
    if plan_file:
        try:
            plan_data = plan_parser.parse_frontmatter(Path(plan_file))
            required_kinds = plan_parser.required_verdict_kinds(plan_data)
        except OSError:
            required_kinds = list(REQUIRED_VERDICT_KINDS)
    else:
        required_kinds = list(REQUIRED_VERDICT_KINDS)

    task_id = task.get("id")
    if not task_id:
        return False

    for kind in required_kinds:
        path = evidence.evidence_path(
            task_id=task_id,
            kind=kind,
            project_slug=project_slug,
            reports_root=reports_dir,
        )
        if not path.exists():
            return False
        try:
            with open(path, "r", encoding="utf-8") as f:
                record = json.load(f)
        except (OSError, json.JSONDecodeError):
            return False
        if record.get("verdict") != "pass":
            return False
    return True


def is_clean_merge(
    task: dict[str, Any],
    archive_dir: str | Path | None = None,
    history_file: str | Path | None = None,
    reports_dir: str | Path | None = None,
    project_slug: str | None = None,
) -> bool:
    """Return True when ``task`` is a clean merge per the PRD definition.

    Clean merge = task reached ``merged`` (terminal), every required stage
    verdict is ``pass``, no failed stage telemetry record exists, and no rework
    (no re-entry from ``failed``, no repeated stage telemetry record).
    """
    if task.get("state") != "merged":
        return False

    task_id = task.get("id")
    if not task_id:
        return False

    if not _required_verdicts_pass(
        task=task, project_slug=project_slug, reports_dir=reports_dir
    ):
        return False

    records = list(
        iter_telemetry_task_records(
            task_id=task_id,
            archive_dir=archive_dir,
            project_slug=project_slug,
        )
    )
    if _has_failed_stage(records):
        return False
    if _has_repeated_stage(records):
        return False

    history = task.get("history", [])
    if _has_reentry_from_failed(history):
        return False

    return True


def count_clean_merges(
    work_class: str,
    archive_dir: str | Path | None = None,
    history_file: str | Path | None = None,
    reports_dir: str | Path | None = None,
    project_slug: str | None = None,
) -> int:
    """Return the number of clean merges for ``work_class``."""
    tasks = read_history_tasks(history_file) if history_file else []
    count = 0
    for task in tasks:
        if task.get("work_class") != work_class:
            continue
        if is_clean_merge(
            task,
            archive_dir=archive_dir,
            history_file=None,
            reports_dir=reports_dir,
            project_slug=project_slug,
        ):
            count += 1
    return count


def load_policy(path: str | Path = DEFAULT_POLICY_PATH) -> dict[str, Any]:
    """Load the zero-review policy, defaulting to empty/off when missing.

    The empty default is the fail-safe guarantee: nothing auto-merges until a
    class is explicitly enabled and its threshold configured.
    """
    path = Path(path)
    default: dict[str, Any] = {"enabled_classes": {}, "thresholds": {}}
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return default
    if not isinstance(data, dict):
        return default
    policy = dict(default)
    if "enabled_classes" in data and isinstance(data["enabled_classes"], dict):
        policy["enabled_classes"] = dict(data["enabled_classes"])
    if "thresholds" in data and isinstance(data["thresholds"], dict):
        policy["thresholds"] = dict(data["thresholds"])
    return policy


def class_eligibility(
    work_class: str,
    policy: dict[str, Any] | None = None,
    archive_dir: str | Path | None = None,
    history_file: str | Path | None = None,
    reports_dir: str | Path | None = None,
    project_slug: str | None = None,
) -> dict[str, Any]:
    """Return eligibility metadata for a work class."""
    policy = policy if policy is not None else load_policy()
    count = count_clean_merges(
        work_class,
        archive_dir=archive_dir,
        history_file=history_file,
        reports_dir=reports_dir,
        project_slug=project_slug,
    )
    enabled = bool(policy.get("enabled_classes", {}).get(work_class))
    threshold = policy.get("thresholds", {}).get(work_class)
    try:
        threshold_met = enabled and threshold is not None and count >= int(threshold)
    except (TypeError, ValueError):
        threshold_met = False
    return {
        "work_class": work_class,
        "count": count,
        "enabled": enabled,
        "threshold": threshold,
        "threshold_met": threshold_met,
    }


def is_eligible_for_auto_merge(
    task: dict[str, Any],
    policy: dict[str, Any] | None = None,
    archive_dir: str | Path | None = None,
    history_file: str | Path | None = None,
    reports_dir: str | Path | None = None,
    project_slug: str | None = None,
) -> bool:
    """Return True when ``task`` may be auto-merged without human review.

    Eligibility requires:
      - a non-unclassified work_class
      - that class is explicitly enabled in policy
      - the class clean-merge count meets the configured threshold
    """
    work_class = task.get("work_class")
    if not work_class or work_class == "unclassified":
        return False

    policy = policy if policy is not None else load_policy()
    meta = class_eligibility(
        work_class,
        policy=policy,
        archive_dir=archive_dir,
        history_file=history_file,
        reports_dir=reports_dir,
        project_slug=project_slug,
    )
    return meta["enabled"] and meta["threshold_met"]


def perform_auto_merge(
    task: dict[str, Any],
    queue_file: str,
    repo_root: str,
) -> bool:
    """Auto-merge ``task`` by merging its branch to main and recording closure.

    Drives the existing ``aet-state record-merge`` path so ``merged`` stays a
    single-writer transition. Returns True on success, False on any failure.
    """
    task_id = task.get("id")
    branch = task.get("branch")
    if not task_id or not branch:
        return False

    script_dir = Path(__file__).resolve().parent.parent / "bin"
    aet_state_bin = str(script_dir / "aet-state")

    def _run_git(*args: str) -> tuple[int, str, str]:
        result = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        return result.returncode, result.stdout, result.stderr

    steps = [
        ("fetch", "origin"),
        ("checkout", "main"),
        ("merge", "--no-ff", "-m", f"auto-merge({task_id})", branch),
        ("push", "origin", "main"),
    ]
    for step in steps:
        rc, _out, err = _run_git(*step)
        if rc != 0:
            print(
                f"   ⚠️  Auto-merge git step failed for {task_id}: git {' '.join(step)}: {err.strip()}",
                file=sys.stderr,
            )
            return False

    rc, out, _err = _run_git("rev-parse", "HEAD")
    if rc != 0:
        return False
    merge_commit = out.strip()
    if not merge_commit:
        return False

    result = subprocess.run(
        [
            sys.executable,
            aet_state_bin,
            "record-merge",
            task_id,
            "--merge-commit",
            merge_commit,
            queue_file,
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(
            f"   ⚠️  Auto-merge record-merge failed for {task_id}: {result.stderr.strip()}",
            file=sys.stderr,
        )
        return False

    print(f"   ✅ Auto-merged {task_id} via closure path")
    return True


def format_eligibility_report(
    policy: dict[str, Any] | None = None,
    archive_dir: str | Path | None = None,
    history_file: str | Path | None = None,
    reports_dir: str | Path | None = None,
    project_slug: str | None = None,
) -> list[str]:
    """Return human-readable eligibility lines for every known work class."""
    policy = policy if policy is not None else load_policy()
    lines = ["Zero-review eligibility (clean-merge count / enabled / threshold):"]
    for work_class in ("trivial", "normal", "critical"):
        meta = class_eligibility(
            work_class,
            policy=policy,
            archive_dir=archive_dir,
            history_file=history_file,
            reports_dir=reports_dir,
            project_slug=project_slug,
        )
        enabled = "yes" if meta["enabled"] else "no"
        threshold = meta["threshold"] if meta["threshold"] is not None else "-"
        met = "met" if meta["threshold_met"] else "not met"
        lines.append(
            f"  {work_class:8} count={meta['count']:3} enabled={enabled:3} "
            f"threshold={threshold} ({met})"
        )
    return lines
