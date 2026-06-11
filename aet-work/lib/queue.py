"""Queue JSON read/write operations."""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

# Tracks wrapper metadata per queue file so write_queue can preserve it.
_queue_wrappers: dict[str, dict[str, Any]] = {}


def read_queue(queue_file: str) -> list[dict[str, Any]]:
    """Read the queue from JSON.

    Supports both flat list and dict-wrapper formats (e.g.
    {"source_prd": "...", "tasks": [...], "queue_updated_at": "..."}).
    Wrapper metadata is stored so write_queue can restore it.
    """
    _queue_wrappers.pop(queue_file, None)
    if not os.path.exists(queue_file):
        return []
    with open(queue_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        _queue_wrappers[queue_file] = {k: v for k, v in data.items() if k != "tasks"}
        return data.get("tasks", [])
    return data


def write_queue(queue_file: str, queue: list[dict[str, Any]]) -> None:
    """Write the queue back to JSON, preserving any wrapper metadata."""
    os.makedirs(os.path.dirname(queue_file), exist_ok=True)
    wrapper = _queue_wrappers.pop(queue_file, {})
    if wrapper:
        data = {**wrapper, "tasks": queue}
    else:
        data = queue
    with open(queue_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
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


# ---------------------------------------------------------------------------
# Archive helpers
# ---------------------------------------------------------------------------

TERMINAL_STATUSES = {"merged", "done", "abandoned"}


def read_archive(archive_file: str) -> list[dict[str, Any]]:
    """Read the archive from JSON.

    Returns an empty list if the archive file does not exist. The archive
    uses the same dict-wrapper format as the queue:
    {"archived_at": "...", "tasks": [...]}.
    """
    if not os.path.exists(archive_file):
        return []
    with open(archive_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        return data.get("tasks", [])
    return data


def write_archive(archive_file: str, tasks: list[dict[str, Any]]) -> None:
    """Write the archive back to JSON with an archived_at timestamp."""
    os.makedirs(os.path.dirname(archive_file), exist_ok=True)
    data = {
        "archived_at": datetime.now().isoformat(),
        "tasks": tasks,
    }
    with open(archive_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def archive_tasks(
    queue_file: str, archive_file: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Move terminal tasks from the queue to the archive.

    Terminal tasks that have active dependents (tasks in the queue whose
    ``blocked_by`` list includes the terminal task's id) are kept in the
    queue so that ``promote_dependents`` can still unblock them.

    Legacy ``merge_verified`` statuses are normalized to ``merged`` before
    archiving.

    Returns ``(new_queue, archived_tasks)``. The queue file and archive file
    are both updated atomically (queue is read and written once; archive is
    read and written once).
    """
    queue = read_queue(queue_file)
    archive = read_archive(archive_file)

    # Collect ids of all tasks still in the queue to detect active dependents.
    queue_ids = {t.get("id") for t in queue if t.get("id")}
    depended_on = set()
    for task in queue:
        for blocker in task.get("blocked_by", []):
            if blocker in queue_ids:
                depended_on.add(blocker)

    new_queue: list[dict[str, Any]] = []
    archived: list[dict[str, Any]] = []

    for task in queue:
        task_id = task.get("id")
        status = task.get("status", "")

        # Normalize legacy status before any further checks.
        if status == "merge_verified":
            task["status"] = "merged"
            status = "merged"

        if status in TERMINAL_STATUSES and task_id not in depended_on:
            archived.append(task)
        else:
            new_queue.append(task)

    write_queue(queue_file, new_queue)
    write_archive(archive_file, archive + archived)
    return new_queue, archived
