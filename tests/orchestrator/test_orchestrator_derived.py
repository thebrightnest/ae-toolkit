"""Tests for orchestrator stored-state helpers."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from aet import telemetry

pytestmark = pytest.mark.xdist_group("telemetry-dir")

_ORCHESTRATOR_PY = Path(__file__).parents[2] / "src" / "aet" / "cli" / "orchestrator.py"
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

        stage = orchestrator.get_current_stage(task, plan_path, "plan-approved")

        self.assertEqual(stage, "implemented")

    def test_footer_divergence_does_not_change_scheduling(self):
        """A stale footer does not override the recorded stage."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Plan\n\n_Stage: implemented_\n")
            plan_path = f.name

        task = {"id": "t1", "stage": "qa-complete"}

        stage = orchestrator.get_current_stage(task, plan_path, "plan-approved")

        self.assertEqual(stage, "qa-complete")

    def test_falls_back_to_footer_when_no_recorded_stage(self):
        """When task has no stage, the footer is used for compatibility."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Plan\n\n_Stage: implemented_\n")
            plan_path = f.name

        task = {"id": "t1"}

        stage = orchestrator.get_current_stage(task, plan_path, "plan-approved")

        self.assertEqual(stage, "implemented")

    def test_defaults_to_entry_stage_when_nothing_recorded(self):
        """With no record and no footer, fall back to the workflow entry stage."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Plan\n")
            plan_path = f.name

        task = {"id": "t1"}

        stage = orchestrator.get_current_stage(task, plan_path, "plan-approved")

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


class TestRecordStage(unittest.TestCase):
    def test_record_stage_persists_to_queue(self):
        """_record_stage calls aet-state set-stage and updates the task."""
        with tempfile.TemporaryDirectory() as repo_root:
            agents_dir = Path(repo_root) / ".agents"
            agents_dir.mkdir()
            queue_file = agents_dir / "aet-queue"
            queue = [{"id": "t1", "state": "in_progress", "title": "One"}]
            queue_file.write_text(json.dumps(queue), encoding="utf-8")

            task = {"id": "t1"}
            result = orchestrator._record_stage(task, "implemented", repo_root)

            self.assertTrue(result)
            self.assertEqual(task["stage"], "implemented")
            data = json.loads(queue_file.read_text(encoding="utf-8"))
            self.assertEqual(data[0]["stage"], "implemented")
            self.assertEqual(data[0]["history"][0]["to"], "implemented")

    def test_record_stage_without_queue_updates_in_memory(self):
        """_record_stage updates the task dict directly when no queue exists."""
        with tempfile.TemporaryDirectory() as repo_root:
            task = {"id": "t1"}
            result = orchestrator._record_stage(task, "implemented", repo_root)

            self.assertTrue(result)
            self.assertEqual(task["stage"], "implemented")

    def test_record_stage_returns_false_when_set_stage_fails(self):
        """_record_stage returns False if aet-state set-stage rejects."""
        with tempfile.TemporaryDirectory() as repo_root:
            agents_dir = Path(repo_root) / ".agents"
            agents_dir.mkdir()
            queue_file = agents_dir / "aet-queue"
            queue = [{"id": "t1", "state": "ready", "title": "One"}]
            queue_file.write_text(json.dumps(queue), encoding="utf-8")

            task = {"id": "t1"}
            result = orchestrator._record_stage(task, "implemented", repo_root)

            self.assertFalse(result)
            self.assertNotIn("stage", task)


class TestMarkFailed(unittest.TestCase):
    def _fake_backend(self, queue):
        backend = MagicMock()
        backend.load.return_value = {"queue": list(queue), "history": []}
        return backend

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
            orchestrator._mark_failed(
                self._fake_backend(queue), queue_file, "t1", "in_progress"
            )

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
            orchestrator._mark_failed(
                self._fake_backend(queue), queue_file, "t1", "ready"
            )

        with open(queue_file, "r", encoding="utf-8") as f:
            result = json.load(f)
        self.assertEqual(result[0]["state"], "failed")


if __name__ == "__main__":
    unittest.main()


class TestSessionTestRunScope(unittest.TestCase):
    """tap-06 end to end: a `make validate` is labelled by what it actually ran.

    Exercises the whole chain at the emission site — session reader, the
    resolved-targets marker in the command's output, and the classifier — so a
    break anywhere between them shows up as a wrong `scope` on the record.
    """

    def _emit(self, invocations):
        logger = MagicMock()
        logger.run_id = "run-1"
        with patch.object(
            orchestrator.session_log, "extract_test_invocations", return_value=invocations
        ):
            orchestrator._emit_session_test_runs(
                logger,
                "demo",
                "docs/plans/demo.md",
                "qa",
                "claude",
                Path("/session"),
                "/worktree",
            )
        return [call.args[0] for call in logger.append_record.call_args_list]

    def _invocation(self, command, output):
        return {
            "command": command,
            "output": output,
            "start_time": "2026-07-26T10:00:00Z",
            "end_time": "2026-07-26T10:01:00Z",
            "exit_code": 0,
        }

    def test_narrowed_make_validate_records_impact_scope(self):
        output = (
            "→ targeted tests: tests/queue (changed paths: 2)\n"
            f"{telemetry.TEST_SCOPE_MARKER_PREFIX} tests/queue\n"
            "✓ All validation checks passed\n"
        )
        records = self._emit([self._invocation("make validate", output)])
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["scope"], "impact")
        self.assertEqual(records[0]["test_command"], "make validate")

    def test_unnarrowed_make_validate_still_records_full_suite(self):
        output = (
            "→ full suite (changed paths: 31)\n"
            f"{telemetry.TEST_SCOPE_MARKER_PREFIX} tests/\n"
        )
        records = self._emit([self._invocation("make validate", output)])
        self.assertEqual(records[0]["scope"], "full-suite")

    def test_make_run_without_marker_stays_full_suite(self):
        """The conservative pre-tap-06 answer survives for unmarked output."""
        records = self._emit([self._invocation("make test", "✓ Tests passed\n")])
        self.assertEqual(records[0]["scope"], "full-suite")

    def test_captured_output_is_read_but_never_archived(self):
        """Output is a classification input only — it must not reach the record.

        A command's captured output can hold anything the shell printed, up to
        and including credentials. It is read for the marker and dropped; the
        archive keeps the scope label, never the text it came from.
        """
        secret = "AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG"
        output = f"{telemetry.TEST_SCOPE_MARKER_PREFIX} tests/queue\n{secret}\n"
        records = self._emit([self._invocation("make validate", output)])
        self.assertEqual(records[0]["scope"], "impact")
        self.assertNotIn("output", records[0])
        self.assertNotIn(secret, json.dumps(records[0]))

    def test_reader_without_output_key_does_not_break_emission(self):
        """Defensive: an adapter that omits `output` still yields a record."""
        invocation = self._invocation("make validate", None)
        del invocation["output"]
        records = self._emit([invocation])
        self.assertEqual(records[0]["scope"], "full-suite")
