"""JSON file backend for the aet-work queue."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from backends.base import TaskBackend
from queue import (
    LEGAL_TRANSITIONS,
    append_history,
    current_state,
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

    def load(self) -> dict[str, Any]:
        """Return queue and history from local JSON files."""
        return {
            "queue": read_queue(self.queue_file),
            "history": read_history(self.history_file),
        }

    def save(self, queue: list[dict[str, Any]]) -> None:
        """Persist the queue to the configured JSON file."""
        write_queue(self.queue_file, queue)

    def transition(
        self,
        task_id: str,
        from_state: str | None,
        to_state: str,
        by: str = "system",
        evidence: dict[str, Any] | None = None,
    ) -> bool:
        """Apply a validated state transition to a task in the JSON queue."""
        queue = read_queue(self.queue_file)
        task = next((t for t in queue if t.get("id") == task_id), None)
        if task is None:
            return False

        recorded_state = current_state(task)
        if recorded_state != from_state:
            return False

        legal = LEGAL_TRANSITIONS.get(from_state, set())
        if to_state not in legal:
            return False

        task["state"] = to_state
        append_history(task, from_state, to_state, by, evidence)
        write_queue(self.queue_file, queue)
        return True

    def plan_drift(self, plans_dir: str | Path) -> list[str]:
        """Return plan files that are not present in queue or history."""
        data = self.load()
        queue = data["queue"]
        history = data["history"]

        queued_files = {t.get("plan_file") for t in queue if t.get("plan_file")}
        settled_files = {t.get("plan_file") for t in history if t.get("plan_file")}
        plan_files = sorted(Path(plans_dir).glob("*.md"))

        return [
            str(pf)
            for pf in plan_files
            if str(pf) not in queued_files and str(pf) not in settled_files
        ]

    def close(self) -> None:
        """No-op for the JSON backend — files are closed after each operation."""
        return
