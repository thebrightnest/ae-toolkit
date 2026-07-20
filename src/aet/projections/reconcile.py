"""Drift computation for the board reconcile command.

The reconcile command scans committed plan files and the mirrored GitHub
issues, computes the difference, and optionally heals it. This module holds
only the analysis helpers; the GitHub write path stays in
:class:`backends.github_backend.GitHubBackend`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aet import plan_parser
from aet.queue import TERMINAL_STATES, read_history, read_queue


@dataclass
class LivePlan:
    """A plan that is still live (has a non-terminal status)."""

    plan_id: str
    title: str
    status: str
    plan_file: str
    blocked_by: list[str] = field(default_factory=list)


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


def load_live_plans(plans_dir: str | Path) -> list[LivePlan]:
    """Return every plan whose committed status is non-terminal.

    Plans with no ``status`` field are treated as settled (legacy
    grandfathering, R-6). Terminal statuses end the lifecycle and should have
    no open issue.
    """
    plans_dir = Path(plans_dir)
    live: list[LivePlan] = []
    for path in sorted(plans_dir.glob("*.md")):
        frontmatter = plan_parser.parse_frontmatter(path)
        status = frontmatter.get("status")
        if status is None or not isinstance(status, str):
            continue
        if status in TERMINAL_STATES:
            continue
        blocked_by = frontmatter.get("blocked_by") or []
        if not isinstance(blocked_by, list):
            blocked_by = []
        live.append(
            LivePlan(
                plan_id=path.stem,
                title=plan_parser.title_from_plan(path),
                status=status,
                plan_file=str(path),
                blocked_by=[str(b) for b in blocked_by],
            )
        )
    return live


def _derive_queue_state(plan: LivePlan, live_ids: set[str], terminal_ids: set[str]) -> str:
    """Derive the queue state for a plan that is not currently in the queue.

    Draft/approved plans map to backlog labels inside the projection and do
    not need a real queue state. For queued plans we recompute ``ready`` vs
    ``blocked`` from blockers, matching :func:`aet_queue.build_blocks`.
    """
    if plan.status == "queued":
        for blocker in plan.blocked_by:
            if blocker in live_ids or blocker not in terminal_ids:
                return "blocked"
        return "ready"
    if plan.status == "in_progress":
        return "in_progress"
    if plan.status == "awaiting_merge":
        return "awaiting_merge"
    return "planned"


def build_task_for_plan(
    plan: LivePlan,
    live_ids: set[str],
    terminal_ids: set[str],
) -> dict[str, Any]:
    """Build a task dict that the projection can use for a live plan."""
    return {
        "id": plan.plan_id,
        "title": plan.title,
        "status": plan.status,
        "state": _derive_queue_state(plan, live_ids, terminal_ids),
        "plan_file": plan.plan_file,
        "blocked_by": plan.blocked_by,
    }


def load_tasks(
    plans_dir: str | Path,
    queue_file: str,
    history_file: str,
) -> tuple[dict[str, Any], set[str]]:
    """Load live plans and the best-effort task state for each.

    Returns a mapping of plan id -> task dict and the set of live plan ids.
    Queue entries take precedence; missing live plans get a synthetic task
    derived from their frontmatter so the projection can create or update an
    issue.
    """
    plans_dir = Path(plans_dir)
    live_plans = load_live_plans(plans_dir)
    live_ids = {p.plan_id for p in live_plans}

    queue = read_queue(queue_file) if Path(queue_file).exists() else []
    history = read_history(history_file) if Path(history_file).exists() else []
    terminal_ids = {
        t["id"]
        for t in history
        if t.get("id") and t.get("state") in TERMINAL_STATES
    }

    tasks_by_id: dict[str, Any] = {t["id"]: t for t in queue if t.get("id")}
    for plan in live_plans:
        if plan.plan_id not in tasks_by_id:
            tasks_by_id[plan.plan_id] = build_task_for_plan(plan, live_ids, terminal_ids)

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
