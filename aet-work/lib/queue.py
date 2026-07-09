"""Queue JSON read/write operations."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

# Tracks whether a queue file was read as a dict wrapper and, if so, its
# non-task metadata so write_queue can preserve the envelope.
_queue_wrappers: dict[str, dict[str, Any] | None] = {}

# Reentrant file-lock state keyed by absolute queue path. These are kept at
# module scope so nested ``queue_lock`` contexts in the same process reuse the
# same open file description and therefore the same fcntl lock.
_lock_files: dict[str, Any] = {}
_lock_counters: dict[str, int] = {}


@contextmanager
def queue_lock(queue_file: str) -> Iterator[None]:
    """Acquire an exclusive advisory lock on a sidecar ``<queue_file>.lock``.

    The lock is blocking and reentrant within the same process. It protects
    the read-modify-write cycles in ``aet-state`` so concurrent children (for
    example the aet-work orchestrator's batch mode) cannot interleave queue
    updates and lose writes.
    """
    queue_abs = os.path.abspath(queue_file)
    lock_path = f"{queue_abs}.lock"
    lock_dir = os.path.dirname(lock_path)
    if lock_dir:
        try:
            os.makedirs(lock_dir, exist_ok=True)
        except OSError:
            # The queue directory may not be writable or even exist (e.g.
            # tests using fake paths). Fall back to a deterministic temp
            # lock file so locking still works within the same process tree.
            digest = hashlib.sha256(queue_abs.encode()).hexdigest()[:16]
            lock_path = os.path.join(tempfile.gettempdir(), f"aet-queue-lock-{digest}.lock")

    key = queue_abs

    if key not in _lock_files:
        _lock_files[key] = open(lock_path, "w", encoding="utf-8")
        _lock_counters[key] = 0

    if _lock_counters[key] == 0:
        fcntl.flock(_lock_files[key].fileno(), fcntl.LOCK_EX)

    _lock_counters[key] += 1
    try:
        yield
    finally:
        _lock_counters[key] -= 1
        if _lock_counters[key] == 0:
            fcntl.flock(_lock_files[key].fileno(), fcntl.LOCK_UN)
            _lock_files[key].close()
            del _lock_files[key]
            del _lock_counters[key]

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

# Legacy status -> canonical state mapping used only on read. New code and
# new queue files must use ``state`` exclusively.
_LEGACY_STATUS_TO_STATE: dict[str | None, str] = {
    None: "planned",
    "planned": "planned",
    "unblocked": "ready",
    "in-progress": "in_progress",
    "blocked": "blocked",
    "done": "awaiting_merge",
    "awaiting_merge": "awaiting_merge",
    "merge_verified": "merged",
    "merged": "merged",
    "abandoned": "abandoned",
    "failed": "failed",
}


def _normalize_task(task: dict[str, Any]) -> dict[str, Any]:
    """Normalize a legacy task record to the canonical ``state`` vocabulary.

    If the task only carries a legacy ``status`` key, derive ``state`` from
    the private literal mapping and remove ``status``. Modern records that
    already have ``state`` are returned with ``status`` stripped.

    The returned dict is the same object, mutated in place.
    """
    state = task.get("state")
    status = task.pop("status", None)
    if state is None and status is not None:
        task["state"] = _LEGACY_STATUS_TO_STATE.get(status, status)
    return task


def current_state(task: dict[str, Any]) -> str | None:
    """Return the task's recorded canonical state.

    Returns ``None`` only when ``state`` is not set (pre-intake).
    """
    return task.get("state")


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
    """Read the queue from JSON and normalize legacy records.

    Supports both flat list and dict-wrapper formats (e.g.
    {"source_prd": "...", "tasks": [...], "queue_updated_at": "..."}).
    Wrapper metadata is stored so write_queue can restore it.

    Legacy ``status``-only records are upgraded in memory to the canonical
    ``state`` vocabulary; the ``status`` key is dropped.
    """
    _queue_wrappers.pop(queue_file, None)
    if not os.path.exists(queue_file):
        return []
    with open(queue_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        _queue_wrappers[queue_file] = {k: v for k, v in data.items() if k != "tasks"}
        tasks = data.get("tasks", [])
    else:
        _queue_wrappers[queue_file] = None
        tasks = data
    return [_normalize_task(task) for task in tasks]


def write_queue(
    queue_file: str, queue: list[dict[str, Any]], wrapper: dict[str, Any] | None = None
) -> None:
    """Write the queue back to JSON, preserving any wrapper metadata.

    If ``wrapper`` is supplied, its keys are merged into the stored wrapper
    (e.g. to update ``source_prd`` or ``queue_updated_at``).

    The legacy ``status`` key is never written. Any task that still carries
    one has it stripped before serialization.

    The write is atomic: data is serialized to a temporary file in the same
    directory and then renamed into place. This prevents concurrent readers
    from seeing a partially-written or truncated file.
    """
    queue_dir = os.path.dirname(queue_file)
    os.makedirs(queue_dir, exist_ok=True)
    stored = _queue_wrappers.pop(queue_file, None)
    was_dict_wrapper = stored is not None
    merged = {**stored} if stored else {}
    if wrapper:
        merged.update(wrapper)

    cleaned = []
    for task in queue:
        copy = dict(task)
        copy.pop("status", None)
        cleaned.append(copy)

    if merged or was_dict_wrapper:
        data = {**merged, "tasks": cleaned}
    else:
        data = cleaned

    fd, tmp_path = tempfile.mkstemp(dir=queue_dir, prefix=".queue-tmp-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, queue_file)
    except Exception:
        try:
            os.unlink(tmp_path)
        except FileNotFoundError:
            pass
        raise


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
# Settled history helpers (append-only JSONL)
# ---------------------------------------------------------------------------

HISTORY_TERMINAL_STATES = {"merged", "abandoned"}


def read_history(history_file: str) -> list[dict[str, Any]]:
    """Read all settled task records from the append-only JSONL history log."""
    if not os.path.exists(history_file):
        return []
    tasks: list[dict[str, Any]] = []
    with open(history_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            tasks.append(json.loads(line))
    return tasks


def append_history_record(history_file: str, task: dict[str, Any]) -> None:
    """Append a settled task record to the append-only JSONL history log."""
    os.makedirs(os.path.dirname(history_file), exist_ok=True)
    record = {**task, "settled_at": datetime.now(timezone.utc).isoformat()}
    with open(history_file, "a", encoding="utf-8") as f:
        json.dump(record, f)
        f.write("\n")


def seal_terminal(queue_file: str, history_file: str, task_id: str) -> dict[str, Any]:
    """Move a terminal task from the live queue to the settled history log.

    Reads the live queue, removes the task identified by ``task_id``, appends
    the full task record (including its transition history) to
    ``history_file`` as one JSONL line, and writes the reduced live queue back.

    Raises ``ValueError`` if the task is not present in the live queue.

    This helper does **not** promote dependents; the caller must already have
    updated the forward frontier before sealing.

    The seal is performed under ``queue_lock`` so concurrent callers cannot
    race on the queue file.
    """
    with queue_lock(queue_file):
        queue = read_queue(queue_file)
        task = next((t for t in queue if t.get("id") == task_id), None)
        if task is None:
            raise ValueError(f"Task {task_id} not found in live queue {queue_file}")

        live = [t for t in queue if t.get("id") != task_id]
        append_history_record(history_file, task)
        write_queue(queue_file, live)
    return task
