"""Tests for aet-work read-side commands (status, next)."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_REPO_ROOT = Path(__file__).parent.parent
_STATUS_PY = _REPO_ROOT / "aet-work" / "bin" / "status"
_NEXT_PY = _REPO_ROOT / "aet-work" / "bin" / "next"

_status_spec = importlib.util.spec_from_loader(
    "status", importlib.machinery.SourceFileLoader("status", str(_STATUS_PY))
)
status = importlib.util.module_from_spec(_status_spec)
_status_spec.loader.exec_module(status)

if _NEXT_PY.exists():
    _next_spec = importlib.util.spec_from_loader(
        "next", importlib.machinery.SourceFileLoader("next", str(_NEXT_PY))
    )
    next_cmd = importlib.util.module_from_spec(_next_spec)
    _next_spec.loader.exec_module(next_cmd)
else:
    next_cmd = None


def _write_json_file(data) -> str:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data, f)
        return f.name


def _make_queue(tasks: list[dict]) -> str:
    return _write_json_file(tasks)


def _make_history(tasks: list[dict]) -> str:
    path = Path(tempfile.mkstemp(suffix=".jsonl")[1])
    with open(path, "w", encoding="utf-8") as f:
        for task in tasks:
            json.dump(task, f)
            f.write("\n")
    return str(path)


def _make_plans_dir(plan_names: list[str]) -> tempfile.TemporaryDirectory:
    tmp = tempfile.TemporaryDirectory()
    for name in plan_names:
        Path(tmp.name, name).write_text("# Plan\n", encoding="utf-8")
    return tmp


def _resolve_plan_files(tasks: list[dict], plans_dir: str) -> list[dict]:
    """Replace bare plan filenames with absolute paths inside plans_dir."""
    resolved = []
    for task in tasks:
        copy = dict(task)
        plan_file = copy.get("plan_file", "")
        if plan_file and not Path(plan_file).is_absolute():
            copy["plan_file"] = str(Path(plans_dir) / Path(plan_file).name)
        resolved.append(copy)
    return resolved


class TestStatusStoredState(unittest.TestCase):
    def test_counts_use_stored_state(self):
        """status uses stored state for the summary counts."""
        plans_dir_tmp = _make_plans_dir(["t1.md", "t2.md"])
        plans_dir = plans_dir_tmp.name
        queue_file = _make_queue(_resolve_plan_files([
            {"id": "t1", "state": "ready", "title": "One", "plan_file": "docs/plans/t1.md"},
            {"id": "t2", "state": "blocked", "title": "Two", "plan_file": "docs/plans/t2.md"},
        ], plans_dir))
        history_file = _make_history([])

        stdout = io.StringIO()
        with patch.object(sys, "stdout", stdout):
            with patch.object(sys, "argv", [
                "status",
                "--queue-file", queue_file,
                "--history-file", history_file,
                "--plans-dir", plans_dir,
            ]):
                rc = status.main()

        self.assertEqual(rc, 0)
        output = stdout.getvalue()
        self.assertIn("unblocked: 1", output)
        self.assertIn("blocked: 1", output)

    def test_counts_include_awaiting_merge(self):
        """status summary includes awaiting_merge tasks."""
        plans_dir_tmp = _make_plans_dir(["t1.md"])
        plans_dir = plans_dir_tmp.name
        queue_file = _make_queue(_resolve_plan_files([
            {"id": "t1", "state": "awaiting_merge", "title": "Done-ish", "plan_file": "docs/plans/t1.md"},
        ], plans_dir))
        history_file = _make_history([])

        stdout = io.StringIO()
        with patch.object(sys, "stdout", stdout):
            with patch.object(sys, "argv", [
                "status",
                "--queue-file", queue_file,
                "--history-file", history_file,
                "--plans-dir", plans_dir,
            ]):
                rc = status.main()

        self.assertEqual(rc, 0)
        output = stdout.getvalue()
        self.assertIn("awaiting_merge: 1", output)

    def test_failed_tasks_reported_from_stored_status(self):
        """Failed tasks are reported from stored state."""
        plans_dir_tmp = _make_plans_dir(["t1.md"])
        plans_dir = plans_dir_tmp.name
        queue_file = _make_queue(_resolve_plan_files([
            {"id": "t1", "state": "failed", "title": "Broke", "plan_file": "docs/plans/t1.md"},
        ], plans_dir))
        history_file = _make_history([])

        stdout = io.StringIO()
        with patch.object(sys, "stdout", stdout):
            with patch.object(sys, "argv", [
                "status",
                "--queue-file", queue_file,
                "--history-file", history_file,
                "--plans-dir", plans_dir,
            ]):
                status.main()

        output = stdout.getvalue()
        self.assertIn("Failed tasks:", output)
        self.assertIn("Broke", output)

    def test_next_ready_tasks_use_stored_state(self):
        """The 'Next ready tasks' list uses stored state."""
        plans_dir_tmp = _make_plans_dir(["t1.md", "t2.md"])
        plans_dir = plans_dir_tmp.name
        queue_file = _make_queue(_resolve_plan_files([
            {"id": "t1", "state": "ready", "title": "One", "plan_file": "docs/plans/t1.md"},
            {"id": "t2", "state": "blocked", "title": "Two", "plan_file": "docs/plans/t2.md"},
        ], plans_dir))
        history_file = _make_history([])

        stdout = io.StringIO()
        with patch.object(sys, "stdout", stdout):
            with patch.object(sys, "argv", [
                "status",
                "--queue-file", queue_file,
                "--history-file", history_file,
                "--plans-dir", plans_dir,
            ]):
                status.main()

        output = stdout.getvalue()
        self.assertIn("Next ready tasks:", output)
        self.assertIn("One", output)
        ready_section = output.split("Next ready tasks:")[1].split("\n\n")[0]
        self.assertNotIn("Two", ready_section)

    def test_works_when_queue_file_is_missing(self):
        """status exits cleanly and reports an empty queue when files are missing."""
        plans_dir_tmp = _make_plans_dir([])
        plans_dir = plans_dir_tmp.name
        queue_file = str(Path(tempfile.mkdtemp()) / "missing-queue.json")
        history_file = str(Path(tempfile.mkdtemp()) / "missing-history.jsonl")

        stdout = io.StringIO()
        with patch.object(sys, "stdout", stdout):
            with patch.object(sys, "argv", [
                "status",
                "--queue-file", queue_file,
                "--history-file", history_file,
                "--plans-dir", plans_dir,
            ]):
                rc = status.main()

        self.assertEqual(rc, 0)
        output = stdout.getvalue()
        self.assertIn("No plan drift detected", output)
        self.assertIn("planned: 0", output)
        self.assertIn("Next ready tasks:", output)
        self.assertIn("None.", output)


@unittest.skipIf(next_cmd is None, "next command not yet implemented")
class TestNextStoredState(unittest.TestCase):
    def test_refuses_on_plan_drift(self):
        """next exits non-zero when a plan file exists on disk but not in the queue."""
        queue_file = _make_queue([])
        history_file = _make_history([])
        plans_dir_tmp = _make_plans_dir(["orphan.md"])
        plans_dir = plans_dir_tmp.name

        with patch.object(sys, "argv", [
            "next",
            "--queue-file", queue_file,
            "--history-file", history_file,
            "--plans-dir", plans_dir,
        ]):
            rc = next_cmd.main()

        self.assertEqual(rc, 1)

    def test_picks_first_stored_ready_and_transitions(self):
        """next picks the first stored-ready task and transitions it to in_progress."""
        plans_dir_tmp = _make_plans_dir(["t1.md", "t2.md"])
        plans_dir = plans_dir_tmp.name
        queue_file = _make_queue(_resolve_plan_files([
            {"id": "t1", "state": "blocked", "title": "One", "plan_file": "docs/plans/t1.md"},
            {"id": "t2", "state": "ready", "title": "Two", "plan_file": "docs/plans/t2.md"},
        ], plans_dir))
        history_file = _make_history([])

        transition_calls = []

        def mock_run(cmd, **_kwargs):
            transition_calls.append(list(cmd))
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        with patch.object(subprocess, "run", side_effect=mock_run):
            with patch.object(sys, "argv", [
                "next",
                "--queue-file", queue_file,
                "--history-file", history_file,
                "--plans-dir", plans_dir,
            ]):
                rc = next_cmd.main()

        self.assertEqual(rc, 0)
        self.assertTrue(
            any("t2" in c and "transition" in c and "in_progress" in c for c in transition_calls),
            f"Expected transition to in_progress for t2, got {transition_calls}",
        )

    def test_topological_order_respected(self):
        """next picks the earliest stored-ready task in topological order."""
        plans_dir_tmp = _make_plans_dir(["t1.md", "t2.md"])
        plans_dir = plans_dir_tmp.name
        queue_file = _make_queue(_resolve_plan_files([
            {"id": "t1", "state": "ready", "title": "One", "plan_file": "docs/plans/t1.md", "blocked_by": []},
            {"id": "t2", "state": "ready", "title": "Two", "plan_file": "docs/plans/t2.md", "blocked_by": ["t1"]},
        ], plans_dir))
        history_file = _make_history([])

        transition_calls = []

        def mock_run(cmd, **_kwargs):
            transition_calls.append(list(cmd))
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        with patch.object(subprocess, "run", side_effect=mock_run):
            with patch.object(sys, "argv", [
                "next",
                "--queue-file", queue_file,
                "--history-file", history_file,
                "--plans-dir", plans_dir,
            ]):
                rc = next_cmd.main()

        self.assertEqual(rc, 0)
        self.assertTrue(
            any("t1" in c and "transition" in c and "in_progress" in c for c in transition_calls),
            f"Expected transition to in_progress for t1, got {transition_calls}",
        )


if __name__ == "__main__":
    unittest.main()
