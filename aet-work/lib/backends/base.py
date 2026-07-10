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
