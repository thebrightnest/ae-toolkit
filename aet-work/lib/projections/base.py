"""Abstract projection interface for aet-work task mirrors."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Projection(ABC):
    """Pluggable one-way mirror of task state to an external system.

    Projections are separate from :class:`backends.base.TaskBackend`. A
    projection never loads or saves the canonical queue; it only observes
    lifecycle events and mirrors them. Failures inside a projection must be
    caught by the dispatcher so storage writes remain fail-closed.
    """

    @abstractmethod
    def on_add(self, task: dict[str, Any], is_new: bool) -> None:
        """Notify the projection that a task was added (``is_new=True``)
        or refreshed (``is_new=False``).

        For a GitHub Issues projection this creates or updates the issue.
        """

    @abstractmethod
    def on_transition(
        self,
        task_id: str,
        from_state: str | None,
        to_state: str,
        evidence: dict[str, Any] | None = None,
    ) -> None:
        """Notify the projection of a non-terminal state transition."""

    @abstractmethod
    def on_close(
        self, task_id: str, evidence: dict[str, Any] | None = None
    ) -> None:
        """Notify the projection that a terminal task was sealed."""

    @abstractmethod
    def ensure_labels(self) -> None:
        """Ensure any required external labels exist."""

    @abstractmethod
    def reconcile(self) -> None:
        """Heal drift between the local queue and the external mirror."""
