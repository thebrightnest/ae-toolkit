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
    def save(self, queue: list[dict[str, Any]]) -> None:
        """Persist ``queue`` to the backend store."""

    @abstractmethod
    def transition(
        self,
        task_id: str,
        from_state: str | None,
        to_state: str,
        by: str = "system",
        evidence: dict[str, Any] | None = None,
    ) -> bool:
        """Transition a task from ``from_state`` to ``to_state``.

        The transition is validated against the recorded-forward lifecycle.
        Returns ``True`` if the transition was applied, ``False`` otherwise.
        """

    @abstractmethod
    def plan_drift(self, plans_dir: str | Path) -> list[str]:
        """Return a list of plan files that are not tracked in queue or history."""

    @abstractmethod
    def close(self) -> None:
        """Release any resources held by the backend."""
