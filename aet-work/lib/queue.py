"""Queue JSON read/write operations."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

# Tracks wrapper metadata per queue file so write_queue can preserve it.
_queue_wrappers: dict[str, dict[str, Any]] = {}

# ---------------------------------------------------------------------------
# Forward-only deterministic state model (ADR-011)
# ---------------------------------------------------------------------------

STATES = {
    "planned",
    "ready",
    "blocked",
    "in_progress",
    "awaiting_merge",
    "merged",
    "abandoned",
    "failed",
}

TERMINAL_STATES = {"merged", "abandoned"}

# Legal transitions for the recorded-forward lifecycle.  ``None`` is the
# pre-intake state used only during initial sync.  ``abandoned`` is a terminal
# human-initiated transition allowed from every non-terminal state.
LEGAL_TRANSITIONS: dict[str | None, set[str]] = {
    None: {"planned"},
    # ``run-one`` may start a queued task directly from ``planned`` when the
    # user explicitly selects a plan, bypassing the normal ``ready`` step.
    "planned": {"blocked", "ready", "in_progress", "abandoned"},
    "blocked": {"ready", "abandoned"},
    "ready": {"in_progress", "failed", "abandoned"},
    "in_progress": {"in_progress", "awaiting_merge", "failed", "abandoned"},
    "awaiting_merge": {"merged", "abandoned"},
    "merged": set(),
    "abandoned": set(),
    "failed": {"in_progress", "ready", "blocked", "abandoned"},
}

# Coexistence shim: map between the new ``state`` field and the legacy
# ``status`` field until the migration in fods-06 retires ``status``.
_STATE_TO_STATUS: dict[str | None, str] = {
    None: "planned",
    "ready": "unblocked",
    "in_progress": "in-progress",
}

_STATUS_TO_STATE: dict[str | None, str] = {
    None: "planned",
    "unblocked": "ready",
    "in-progress": "in_progress",
    "done": "awaiting_merge",
    "merge_verified": "awaiting_merge",
}


def state_to_status(state: str | None) -> str:
    """Return the legacy status that corresponds to ``state``."""
    return _STATE_TO_STATUS.get(state, state or "planned")


def status_to_state(status: str | None) -> str:
    """Return the canonical state that corresponds to legacy ``status``."""
    return _STATUS_TO_STATE.get(status, status or "planned")


def current_state(task: dict[str, Any]) -> str | None:
    """Return the task's recorded state, falling back to legacy status.

    Returns ``None`` only when neither ``state`` nor ``status`` is set
    (pre-intake).
    """
    state = task.get("state")
    if state is not None:
        return state
    status = task.get("status")
    if status is not None:
        return status_to_state(status)
    return None


def append_history(
    task: dict[str, Any],
    frm: str | None,
    to: str,
    by: str,
    evidence: dict[str, Any] | None = None,
) -> None:
    """Append a transition entry to the task's append-only history."""
    entry: dict[str, Any] = {
        "from": frm,
        "to": to,
        "at": datetime.now(timezone.utc).isoformat(),
        "by": by,
    }
    if evidence:
        entry["evidence"] = evidence
    task.setdefault("history", []).append(entry)


def pending_blockers(task: dict[str, Any]) -> int:
    """Return the number of blockers still pending for this task.

    If the counter has not been initialized, derive it from ``blocked_by``.
    """
    pb = task.get("pending_blockers")
    if pb is not None:
        return pb
    return len(task.get("blocked_by", []))


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


def write_queue(
    queue_file: str, queue: list[dict[str, Any]], wrapper: dict[str, Any] | None = None
) -> None:
    """Write the queue back to JSON, preserving any wrapper metadata.

    If ``wrapper`` is supplied, its keys are merged into the stored wrapper
    (e.g. to update ``source_prd`` or ``queue_updated_at``).
    """
    os.makedirs(os.path.dirname(queue_file), exist_ok=True)
    stored = _queue_wrappers.pop(queue_file, {})
    merged = {**stored}
    if wrapper:
        merged.update(wrapper)
    if merged:
        data = {**merged, "tasks": queue}
    else:
        data = queue
    with open(queue_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def get_next_unblocked(queue: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Return the first stored-ready task."""
    for task in queue:
        if current_state(task) == "ready":
            return task
    return None


def has_pending_tasks(queue: list[dict[str, Any]]) -> bool:
    """Check if any tasks are not in a terminal state."""
    terminal = {"merged", "abandoned"}
    for task in queue:
        state = current_state(task)
        if state is not None and state not in terminal:
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


def mark_awaiting_merge(queue: list[dict[str, Any]], task_id: str) -> None:
    """Mark a finished-but-unmerged task as awaiting merge."""
    for task in queue:
        if task.get("id") == task_id:
            task["status"] = "awaiting_merge"
            task["completed_at"] = datetime.now().isoformat()


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
    queue so that derived blocker-aware state remains resolvable.

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
