"""Queue JSON read/write operations."""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any


def read_queue(queue_file: str) -> list[dict[str, Any]]:
    """Read the queue from JSON."""
    if not os.path.exists(queue_file):
        return []
    with open(queue_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        return data.get("tasks", data)
    return data


def write_queue(queue_file: str, queue: list[dict[str, Any]]) -> None:
    """Write the queue back to JSON."""
    os.makedirs(os.path.dirname(queue_file), exist_ok=True)
    with open(queue_file, "w", encoding="utf-8") as f:
        json.dump(queue, f, indent=2)
        f.write("\n")


def get_next_unblocked(queue: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Return the first unblocked task."""
    for task in queue:
        if task.get("status") == "unblocked":
            return task
    return None


def has_pending_tasks(queue: list[dict[str, Any]]) -> bool:
    """Check if any tasks are not in a terminal state."""
    for task in queue:
        status = task.get("status", "")
        if status in ("unblocked", "blocked", "in-progress"):
            return True
    return False


def mark_status(
    queue: list[dict[str, Any]],
    task_id: str,
    status: str,
    stage: str | None = None,
) -> None:
    """Update a task's status and optional failed stage."""
    for task in queue:
        if task.get("id") == task_id:
            task["status"] = status
            if stage:
                task["failed_stage"] = stage


def mark_completed(queue: list[dict[str, Any]], task_id: str) -> None:
    """Mark a task as completed with timestamp."""
    for task in queue:
        if task.get("id") == task_id:
            task["status"] = "done"
            task["completed_at"] = datetime.now().isoformat()


def promote_dependents(queue: list[dict[str, Any]]) -> None:
    """Promote blocked tasks whose dependencies are done/merged."""
    done_ids = {
        t["id"]
        for t in queue
        if t.get("status") in ("done", "merged", "merge_verified")
    }
    for task in queue:
        if task.get("status") == "blocked":
            blockers = task.get("blocked_by", [])
            if all(b in done_ids for b in blockers):
                task["status"] = "unblocked"


def record_task_meta(
    queue: list[dict[str, Any]],
    task_id: str,
    worktree: str | None,
    branch: str | None,
) -> None:
    """Record worktree and branch metadata for a task."""
    for task in queue:
        if task.get("id") == task_id:
            task["worktree"] = worktree
            task["branch"] = branch
