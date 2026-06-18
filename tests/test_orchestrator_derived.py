"""Tests for orchestrator stored-state helpers."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_ORCHESTRATOR_PY = Path(__file__).parent.parent / "aet-work" / "bin" / "orchestrator"
_spec = importlib.util.spec_from_loader(
    "orchestrator", importlib.machinery.SourceFileLoader("orchestrator", str(_ORCHESTRATOR_PY))
)
orchestrator = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(orchestrator)


class TestCurrentStageFromRecord(unittest.TestCase):
    def test_stage_read_from_record_not_footer(self):
        """Orchestrator prefers task['stage'] over the plan footer."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Plan\n\n_Stage: plan-approved_\n")
            plan_path = f.name

        task = {"id": "t1", "stage": "implemented"}

        stage = orchestrator.get_current_stage(task, plan_path)

        self.assertEqual(stage, "implemented")

    def test_footer_divergence_does_not_change_scheduling(self):
        """A stale footer does not override the recorded stage."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Plan\n\n_Stage: implemented_\n")
            plan_path = f.name

        task = {"id": "t1", "stage": "qa-complete"}

        stage = orchestrator.get_current_stage(task, plan_path)

        self.assertEqual(stage, "qa-complete")

    def test_falls_back_to_footer_when_no_recorded_stage(self):
        """When task has no stage, the footer is used for compatibility."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Plan\n\n_Stage: implemented_\n")
            plan_path = f.name

        task = {"id": "t1"}

        stage = orchestrator.get_current_stage(task, plan_path)

        self.assertEqual(stage, "implemented")

    def test_defaults_to_plan_approved_when_nothing_recorded(self):
        """When no stage exists anywhere, default to plan-approved."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Plan\n")
            plan_path = f.name

        task = {"id": "t1"}

        stage = orchestrator.get_current_stage(task, plan_path)

        self.assertEqual(stage, "plan-approved")


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


class TestMarkFailed(unittest.TestCase):
    def test_mark_failed_updates_canonical_state(self):
        """_mark_failed writes the failed state through the transition writer."""
        queue = [{"id": "t1", "state": "in_progress", "title": "One"}]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(queue, f)
            queue_file = f.name

        def mock_run(cmd, **_kwargs):
            # Simulate a successful aet-state transition that updates the file.
            if "transition" in cmd:
                with open(queue_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for task in data:
                    if task.get("id") == "t1":
                        task["state"] = "failed"
                with open(queue_file, "w", encoding="utf-8") as f:
                    json.dump(data, f)
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        with patch.object(subprocess, "run", side_effect=mock_run):
            orchestrator._mark_failed(queue_file, "t1", "in_progress")

        with open(queue_file, "r", encoding="utf-8") as f:
            result = json.load(f)
        self.assertEqual(result[0]["state"], "failed")

    def test_mark_failed_ready_to_failed_is_legal(self):
        """A ready task that fails during pickup can transition to failed."""
        queue = [{"id": "t1", "state": "ready", "title": "One"}]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(queue, f)
            queue_file = f.name

        def mock_run(cmd, **_kwargs):
            if "transition" in cmd:
                with open(queue_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for task in data:
                    if task.get("id") == "t1":
                        task["state"] = "failed"
                with open(queue_file, "w", encoding="utf-8") as f:
                    json.dump(data, f)
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        with patch.object(subprocess, "run", side_effect=mock_run):
            orchestrator._mark_failed(queue_file, "t1", "ready")

        with open(queue_file, "r", encoding="utf-8") as f:
            result = json.load(f)
        self.assertEqual(result[0]["state"], "failed")


if __name__ == "__main__":
    unittest.main()
