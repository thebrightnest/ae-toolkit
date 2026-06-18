"""Tests for orchestrator stored-state helpers."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import unittest
from pathlib import Path

_ORCHESTRATOR_PY = Path(__file__).parent.parent / "aet-work" / "bin" / "orchestrator"
_spec = importlib.util.spec_from_loader(
    "orchestrator", importlib.machinery.SourceFileLoader("orchestrator", str(_ORCHESTRATOR_PY))
)
orchestrator = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(orchestrator)


class TestStoredStateHelpers(unittest.TestCase):
    def test_get_next_ready_returns_first_ready(self):
        """Return the first task whose stored state is ready."""
        queue = [
            {"id": "t1", "state": "blocked"},
            {"id": "t2", "state": "ready"},
        ]

        task = orchestrator.get_next_ready_task(queue)

        self.assertIsNotNone(task)
        self.assertEqual(task["id"], "t2")

    def test_get_next_ready_none_available(self):
        """Return None when no task is stored-ready."""
        queue = [{"id": "t1", "state": "blocked"}]

        task = orchestrator.get_next_ready_task(queue)

        self.assertIsNone(task)

    def test_has_pending_tasks_true_for_ready(self):
        """Pending check returns True when a stored-ready task exists."""
        queue = [{"id": "t1", "state": "ready"}]

        self.assertTrue(orchestrator.has_pending_tasks(queue))

    def test_has_pending_tasks_true_for_failed(self):
        """Failed stored state keeps a task actionable."""
        queue = [{"id": "t1", "state": "failed"}]

        self.assertTrue(orchestrator.has_pending_tasks(queue))

    def test_has_pending_tasks_true_for_in_progress(self):
        """In-progress stored state keeps a task actionable."""
        queue = [{"id": "t1", "state": "in_progress"}]

        self.assertTrue(orchestrator.has_pending_tasks(queue))

    def test_has_pending_tasks_false_when_all_terminal(self):
        """No pending tasks when all stored states are terminal."""
        queue = [
            {"id": "t1", "state": "merged"},
            {"id": "t2", "state": "abandoned"},
        ]

        self.assertFalse(orchestrator.has_pending_tasks(queue))


if __name__ == "__main__":
    unittest.main()
