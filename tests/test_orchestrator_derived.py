"""Tests for orchestrator derived-state helpers."""

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


class TestDerivedHelpers(unittest.TestCase):
    def test_get_next_derived_unblocked_returns_first_unblocked(self):
        """Return the first task whose derived status is unblocked."""
        queue = [
            {"id": "t1"},
            {"id": "t2"},
        ]
        derived = {
            "t1": {"derived_status": "blocked"},
            "t2": {"derived_status": "unblocked"},
        }

        task = orchestrator.get_next_derived_unblocked(queue, derived)

        self.assertIsNotNone(task)
        self.assertEqual(task["id"], "t2")

    def test_get_next_derived_unblocked_ignores_warning_suffix(self):
        """A warning suffix on the derived status does not prevent selection."""
        queue = [{"id": "t1"}]
        derived = {"t1": {"derived_status": "unblocked (warning: done without merge verification)"}}

        task = orchestrator.get_next_derived_unblocked(queue, derived)

        self.assertIsNotNone(task)
        self.assertEqual(task["id"], "t1")

    def test_get_next_derived_unblocked_none_available(self):
        """Return None when no task is derived-unblocked."""
        queue = [{"id": "t1"}]
        derived = {"t1": {"derived_status": "blocked"}}

        task = orchestrator.get_next_derived_unblocked(queue, derived)

        self.assertIsNone(task)

    def test_has_derived_pending_tasks_true_for_unblocked(self):
        """Pending check returns True when a derived-unblocked task exists."""
        queue = [{"id": "t1"}]
        derived = {"t1": {"derived_status": "unblocked"}}

        self.assertTrue(orchestrator.has_derived_pending_tasks(queue, derived))

    def test_has_derived_pending_tasks_true_for_failed(self):
        """Failed stored status keeps a task actionable regardless of derived status."""
        queue = [{"id": "t1", "status": "failed"}]
        derived = {"t1": {"derived_status": "merged"}}

        self.assertTrue(orchestrator.has_derived_pending_tasks(queue, derived))

    def test_has_derived_pending_tasks_false_when_all_terminal(self):
        """No pending tasks when all derived statuses are terminal."""
        queue = [{"id": "t1"}]
        derived = {"t1": {"derived_status": "merged"}}

        self.assertFalse(orchestrator.has_derived_pending_tasks(queue, derived))


if __name__ == "__main__":
    unittest.main()
