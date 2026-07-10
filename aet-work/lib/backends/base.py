"""Abstract backend interface for aet-work task storage."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class TaskBackend(ABC):
    """Pluggable backend for loading, saving, and mutating the work queue.

    Implementations may target local JSON files, GitHub issues, or a composite
    of multiple stores. Callers should use the public methods here rather than
    importing queue helpers directly.
    """

    @abstractmethod
    def load(self) -> dict[str, Any]:
        """Return the current queue and settled history.

        Returns a dict with at least ``queue`` (list of task dicts) and
        ``history`` (list of settled task dicts).
        """

    @abstractmethod
    def save(
        self, queue: list[dict[str, Any]], wrapper: dict[str, Any] | None = None
    ) -> None:
        """Persist ``queue`` to the backend store.

        ``wrapper`` contains optional envelope metadata (e.g. ``source_prd``,
        ``queue_updated_at``) that JSON-backed stores may merge into the file.
        """

    @abstractmethod
    def plan_drift(self, plans_dir: str | Path) -> list[str]:
        """Return a list of plan files that are not tracked in queue or history."""

    @abstractmethod
    def close(self) -> None:
        """Release any resources held by the backend."""

    @abstractmethod
    def sync_task(self, task: dict[str, Any], is_new: bool) -> None:
        """Notify the backend that a task was synced.

        ``is_new`` is ``True`` when the task was just appended to the queue
        and ``False`` when it already existed. GitHub-backed implementations
        can create or update issues here; JSON-backed implementations can
        leave this as a no-op.
        """

    def on_transition(
        self,
        task_id: str,
        from_state: str | None,
        to_state: str,
        evidence: dict[str, Any] | None = None,
    ) -> None:
        """Optional hook called after a transition has been persisted.

        Backends such as GitHub Issues can override this to update labels or
        other external state. The default implementation does nothing.
        """
        return

    def close_task(
        self, task_id: str, evidence: dict[str, Any] | None = None
    ) -> None:
        """Optional hook called after a terminal task is sealed.

        Backends such as GitHub Issues can override this to close the
        corresponding external issue. The default implementation does nothing.
        """
        return

    def seal(self, task_id: str, history_file: str) -> dict[str, Any]:
        """Move a terminal task from the live queue to the settled history log.

        The default implementation targets the local JSON files (``queue_file``
        and ``history_file``) and mirrors ``queue.seal_terminal``: it removes
        the task from the live queue and appends the full record (including its
        transition history) to ``history_file`` as one JSONL line.

        Backends that store live tasks elsewhere (for example git refs) override
        this to drop their per-task record before appending to the shared
        history JSONL, so ``aet-state`` can route sealing through the backend
        interface instead of assuming a file-backed queue.

        The caller (``aet-state``) already holds the queue lock, so this method
        does not re-acquire it: the queue module is loaded twice in-process
        (as ``aet_queue`` by ``aet-state`` and as ``queue`` by the backends),
        and a second independent ``flock`` file descriptor to the same lock file
        would self-deadlock under POSIX ``flock`` semantics.
        """
        from queue import append_history_record, read_queue, write_queue

        queue = read_queue(self.queue_file)
        task = next((t for t in queue if t.get("id") == task_id), None)
        if task is None:
            raise ValueError(
                f"Task {task_id} not found in live queue {self.queue_file}"
            )
        live = [t for t in queue if t.get("id") != task_id]
        append_history_record(history_file, task)
        write_queue(self.queue_file, live)
        return task
