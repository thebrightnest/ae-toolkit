"""Drift computation for the board reconcile command.

The reconcile command scans the work queue, the settled history log, and the
mirrored GitHub issues, computes the difference, and optionally heals it.
Queue membership is the explicit sprint-add record; plan frontmatter no longer
determines live-ness. This module holds only the analysis helpers; the GitHub
write path stays in :class:`backends.github_backend.GitHubBackend`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aet.queue import TERMINAL_STATES, read_queue


@dataclass
class DriftItem:
    """One difference between the local live plans and the GitHub board."""

    drift_type: str
    plan_id: str
    issue_number: int | None = None
    expected_label: str | None = None
    actual_labels: list[str] | None = None


def extract_plan_id(body: str) -> str | None:
    """Return the ``aet-id`` embedded in an issue body, if any."""
    match = re.search(r"<!--\s*aet-id:\s*(.+?)\s*-->", body or "")
    return match.group(1).strip() if match else None


def load_tasks(
    plans_dir: str | Path,
    queue_file: str,
    history_file: str,
) -> tuple[dict[str, Any], set[str]]:
    """Load live tasks from the queue and the set of live plan ids.

    Returns a mapping of plan id -> task dict and the set of live plan ids.
    Queue membership is the explicit sprint-add record; only non-terminal
    queue entries are considered live. The ``plans_dir`` argument is retained
    for API compatibility but no longer used to auto-discover plans.
    """
    queue = read_queue(queue_file) if Path(queue_file).exists() else []

    live_tasks = [t for t in queue if t.get("state") not in TERMINAL_STATES]
    tasks_by_id: dict[str, Any] = {t["id"]: t for t in live_tasks if t.get("id")}
    live_ids = set(tasks_by_id.keys())

    return tasks_by_id, live_ids


def compute_drift(
    live_tasks: dict[str, Any],
    live_ids: set[str],
    issues: list[dict[str, Any]],
    label_prefix: str,
    state_label: callable,
    task_state: callable,
) -> list[DriftItem]:
    """Compare live tasks to fetched issues and return drift items.

    ``state_label`` and ``task_state`` are the projection's mapping helpers.
    """
    prefix = f"{label_prefix}:"
    issues_by_id: dict[str, dict[str, Any]] = {}
    for issue in issues:
        plan_id = extract_plan_id(issue.get("body") or "")
        if plan_id:
            issues_by_id[plan_id] = issue

    drift: list[DriftItem] = []
    for plan_id in sorted(live_ids):
        task = live_tasks[plan_id]
        expected_label = state_label(task_state(task))
        issue = issues_by_id.get(plan_id)

        if issue is None:
            drift.append(
                DriftItem(
                    drift_type="missing",
                    plan_id=plan_id,
                    expected_label=expected_label,
                )
            )
            continue

        actual_labels = [
            label for label in issue.get("labels", []) if label.startswith(prefix)
        ]
        if issue.get("state") == "closed":
            drift.append(
                DriftItem(
                    drift_type="closed-live",
                    plan_id=plan_id,
                    issue_number=issue["number"],
                    expected_label=expected_label,
                    actual_labels=actual_labels,
                )
            )
        elif actual_labels != [expected_label]:
            drift.append(
                DriftItem(
                    drift_type="mislabeled",
                    plan_id=plan_id,
                    issue_number=issue["number"],
                    expected_label=expected_label,
                    actual_labels=actual_labels,
                )
            )

    for plan_id, issue in issues_by_id.items():
        if plan_id not in live_ids:
            drift.append(
                DriftItem(
                    drift_type="orphan",
                    plan_id=plan_id,
                    issue_number=issue["number"],
                )
            )

    return drift
