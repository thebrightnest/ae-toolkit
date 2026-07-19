"""Cross-task metrics aggregation over settled history and telemetry.

Read-only analytics: every projection derives from the shared definitions in
``track_record`` (``is_clean_merge``, ``rework_count``) so downstream consumers
(desk, CLI, scoreboard) cannot disagree.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import track_record


def _task_settled_at(task: dict[str, Any]) -> str | None:
    """Return the best available settled timestamp for ``task``, or None."""
    return task.get("settled_at") or task.get("completed_at") or task.get("merged_at")


def _parse_date(date_str: str) -> datetime:
    """Parse a ``YYYY-MM-DD`` string as midnight UTC."""
    return datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def iter_settled_tasks(
    history_file: str | Path,
    since: str | None = None,
) -> list[dict[str, Any]]:
    """Return settled task records from ``history_file``.

    When ``since`` is given (``YYYY-MM-DD``), only tasks whose best available
    settled timestamp is on or after that date are included. Legacy records
    without ``settled_at`` fall back to ``completed_at``, then ``merged_at``;
    records with none of the three are included only when ``since`` is None.
    """
    tasks = track_record.read_history_tasks(history_file)
    if not since:
        return tasks

    since_dt = _parse_date(since)
    filtered: list[dict[str, Any]] = []
    for task in tasks:
        ts = _task_settled_at(task)
        if ts is None:
            continue
        try:
            task_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            continue
        if task_dt >= since_dt:
            filtered.append(task)
    return filtered


def task_cost(
    task_id: str,
    archive_dir: str | Path | None = None,
    project_slug: str | None = None,
) -> dict[str, int | float | None]:
    """Return the summed token and USD cost for ``task_id`` across runs.

    Sums ``token_count`` and ``cost_estimate`` over the task's stage records
    from ``track_record.iter_telemetry_task_records``. When all values for a
    field are null, that field returns ``None``; partial coverage returns the
    sum of known values.
    """
    records = track_record.iter_telemetry_task_records(
        task_id=task_id,
        archive_dir=archive_dir,
        project_slug=project_slug,
    )

    tokens: int | None = None
    usd: float | None = None
    for record in records:
        if record.get("type") == "stage":
            token_count = record.get("token_count")
            if isinstance(token_count, int):
                tokens = (tokens or 0) + token_count
            cost_estimate = record.get("cost_estimate")
            if isinstance(cost_estimate, (int, float)) and not isinstance(cost_estimate, bool):
                usd = (usd or 0.0) + float(cost_estimate)
    return {"tokens": tokens, "usd": usd}


def _empty_bucket() -> dict[str, Any]:
    """Return a fresh aggregate bucket."""
    return {
        "settled": 0,
        "merged": 0,
        "first_pass": 0,
        "first_pass_rate": None,
        "rework": 0,
        "cost": {
            "tokens_total": None,
            "tokens_avg_per_merged": None,
            "usd_total": None,
            "usd_avg_per_merged": None,
            "usd_known_tasks": 0,
        },
    }


def _add_task_to_bucket(
    bucket: dict[str, Any],
    task: dict[str, Any],
    archive_dir: str | Path | None,
    project_slug: str | None,
    reports_dir: str | Path | None,
) -> None:
    """Incorporate one task's contribution into an aggregate bucket."""
    bucket["settled"] += 1
    bucket["rework"] += track_record.rework_count(
        task,
        archive_dir=archive_dir,
        project_slug=project_slug,
    )

    if task.get("state") != "merged":
        return

    bucket["merged"] += 1
    if track_record.is_clean_merge(
        task,
        archive_dir=archive_dir,
        project_slug=project_slug,
        reports_dir=reports_dir,
    ):
        bucket["first_pass"] += 1

    cost = task_cost(
        task["id"],
        archive_dir=archive_dir,
        project_slug=project_slug,
    )
    tokens = cost["tokens"]
    if tokens is not None:
        bucket["cost"]["tokens_total"] = (bucket["cost"]["tokens_total"] or 0) + tokens
    usd = cost["usd"]
    if usd is not None:
        bucket["cost"]["usd_total"] = (bucket["cost"]["usd_total"] or 0.0) + usd
        bucket["cost"]["usd_known_tasks"] += 1


def _finalize_bucket(bucket: dict[str, Any]) -> None:
    """Compute derived fields for a bucket in place."""
    merged = bucket["merged"]
    if merged:
        bucket["first_pass_rate"] = bucket["first_pass"] / merged
        if bucket["cost"]["tokens_total"] is not None:
            bucket["cost"]["tokens_avg_per_merged"] = bucket["cost"]["tokens_total"] / merged
        if bucket["cost"]["usd_total"] is not None:
            bucket["cost"]["usd_avg_per_merged"] = bucket["cost"]["usd_total"] / merged


def aggregate(
    history_file: str | Path,
    since: str | None = None,
    archive_dir: str | Path | None = None,
    project_slug: str | None = None,
    reports_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Return the canonical metrics projection for settled tasks.

    The returned dict has ``overall`` and ``classes`` buckets. Each bucket
    contains counts for settled/merged/first-pass tasks, the first-pass rate,
    total rework, and cost totals with coverage counts.

    Class buckets are data-driven by the ``work_class`` values present in
    ``history_file``; tasks without a work_class land in ``unclassified``.
    """
    tasks = iter_settled_tasks(history_file, since=since)
    overall = _empty_bucket()
    classes: dict[str, dict[str, Any]] = {}

    for task in tasks:
        work_class = task.get("work_class") or "unclassified"
        bucket = classes.setdefault(work_class, _empty_bucket())
        _add_task_to_bucket(
            bucket,
            task,
            archive_dir=archive_dir,
            project_slug=project_slug,
            reports_dir=reports_dir,
        )
        _add_task_to_bucket(
            overall,
            task,
            archive_dir=archive_dir,
            project_slug=project_slug,
            reports_dir=reports_dir,
        )

    _finalize_bucket(overall)
    for bucket in classes.values():
        _finalize_bucket(bucket)

    return {
        "since": since,
        "overall": overall,
        "classes": dict(sorted(classes.items())),
    }
