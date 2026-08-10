"""JSON file backend for the aet-work queue."""

from __future__ import annotations

from typing import Any

from aet.backends.base import TaskBackend
from aet.queue import (
    read_history,
    read_queue,
    write_queue,
)


class JsonBackend(TaskBackend):
    """Local JSON file implementation of the task backend interface."""

    def __init__(
        self,
        queue_file: str = ".agents/work-queue.json",
        history_file: str = ".agents/work-history.jsonl",
    ) -> None:
        self.queue_file = queue_file
        self.history_file = history_file

    def load(self, verify: bool = True) -> dict[str, Any]:
        """Return queue and history from local JSON files."""
        return {
            "queue": read_queue(self.queue_file, verify=verify),
            "history": read_history(self.history_file),
        }

    def save(
        self, queue: list[dict[str, Any]], wrapper: dict[str, Any] | None = None
    ) -> None:
        """Persist the queue to the configured JSON file."""
        write_queue(self.queue_file, queue, wrapper=wrapper)

    def close(self) -> None:
        """No-op for the JSON backend — files are closed after each operation."""
        return

    def sync_task(self, task: dict[str, Any], is_new: bool) -> None:
        """No-op: JSON backend has no external task mirror to maintain."""
        return
