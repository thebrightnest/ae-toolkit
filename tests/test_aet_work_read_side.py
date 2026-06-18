"""Tests for aet-work read-side commands (status, next)."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import io
import json
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


class _MockResult:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _write_json_file(data) -> str:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data, f)
        return f.name


def _make_queue(tasks: list[dict]) -> str:
    return _write_json_file(tasks)


def _make_archive(tasks: list[dict]) -> str:
    return _write_json_file({"archived_at": "2026-01-01T00:00:00Z", "tasks": tasks})


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


class TestStatusDerivedState(unittest.TestCase):
    def test_counts_use_derived_status(self):
        """status uses derived status for the summary counts."""
        plans_dir_tmp = _make_plans_dir(["t1.md", "t2.md"])
        plans_dir = plans_dir_tmp.name
        queue_file = _make_queue(_resolve_plan_files([
            {"id": "t1", "status": "planned", "title": "One", "plan_file": "docs/plans/t1.md"},
            {"id": "t2", "status": "blocked", "title": "Two", "plan_file": "docs/plans/t2.md"},
        ], plans_dir))
        archive_file = _make_archive([])

        derived = {
            "t1": {"derived_status": "unblocked"},
            "t2": {"derived_status": "unblocked"},
        }

        stdout = io.StringIO()
        with patch.object(status, "derive_statuses", return_value=derived):
            with patch.object(sys, "stdout", stdout):
                with patch.object(sys, "argv", [
                    "status",
                    "--queue-file", queue_file,
                    "--archive-file", archive_file,
                    "--plans-dir", plans_dir,
                ]):
                    rc = status.main()

        self.assertEqual(rc, 0)
        output = stdout.getvalue()
        self.assertIn("unblocked: 2", output)
        self.assertIn("blocked: 0", output)

    def test_no_ordinary_mismatch_warning(self):
        """Ordinary stored-vs-derived mismatches do not show a warning marker."""
        plans_dir_tmp = _make_plans_dir(["t1.md", "t2.md"])
        plans_dir = plans_dir_tmp.name
        queue_file = _make_queue(_resolve_plan_files([
            {"id": "t1", "status": "planned", "title": "One", "plan_file": "docs/plans/t1.md"},
            {"id": "t2", "status": "unblocked", "title": "Two", "plan_file": "docs/plans/t2.md"},
        ], plans_dir))
        archive_file = _make_archive([])

        derived = {
            "t1": {"derived_status": "unblocked"},
            "t2": {"derived_status": "blocked"},
        }

        stdout = io.StringIO()
        with patch.object(status, "derive_statuses", return_value=derived):
            with patch.object(sys, "stdout", stdout):
                with patch.object(sys, "argv", [
                    "status",
                    "--queue-file", queue_file,
                    "--archive-file", archive_file,
                    "--plans-dir", plans_dir,
                ]):
                    status.main()

        output = stdout.getvalue()
        lines = [line for line in output.splitlines() if line.startswith("t")]
        self.assertEqual(len(lines), 2)
        for line in lines:
            self.assertNotIn("⚠️", line)

    def test_failed_tasks_reported_from_stored_status(self):
        """Failed tasks are reported from stored status regardless of derived status."""
        plans_dir_tmp = _make_plans_dir(["t1.md"])
        plans_dir = plans_dir_tmp.name
        queue_file = _make_queue(_resolve_plan_files([
            {"id": "t1", "status": "failed", "title": "Broke", "plan_file": "docs/plans/t1.md"},
        ], plans_dir))
        archive_file = _make_archive([])

        derived = {"t1": {"derived_status": "blocked"}}

        stdout = io.StringIO()
        with patch.object(status, "derive_statuses", return_value=derived):
            with patch.object(sys, "stdout", stdout):
                with patch.object(sys, "argv", [
                    "status",
                    "--queue-file", queue_file,
                    "--archive-file", archive_file,
                    "--plans-dir", plans_dir,
                ]):
                    status.main()

        output = stdout.getvalue()
        self.assertIn("Failed tasks:", output)
        self.assertIn("Broke", output)

    def test_next_unblocked_tasks_use_derived_status(self):
        """The 'Next unblocked tasks' list uses derived status."""
        plans_dir_tmp = _make_plans_dir(["t1.md", "t2.md"])
        plans_dir = plans_dir_tmp.name
        queue_file = _make_queue(_resolve_plan_files([
            {"id": "t1", "status": "planned", "title": "One", "plan_file": "docs/plans/t1.md"},
            {"id": "t2", "status": "planned", "title": "Two", "plan_file": "docs/plans/t2.md"},
        ], plans_dir))
        archive_file = _make_archive([])

        derived = {
            "t1": {"derived_status": "unblocked"},
            "t2": {"derived_status": "blocked"},
        }

        stdout = io.StringIO()
        with patch.object(status, "derive_statuses", return_value=derived):
            with patch.object(sys, "stdout", stdout):
                with patch.object(sys, "argv", [
                    "status",
                    "--queue-file", queue_file,
                    "--archive-file", archive_file,
                    "--plans-dir", plans_dir,
                ]):
                    status.main()

        output = stdout.getvalue()
        self.assertIn("Next unblocked tasks:", output)
        self.assertIn("One", output)
        self.assertNotIn("Two", output.split("Next unblocked tasks:")[1].split("\n\n")[0])


@unittest.skipIf(next_cmd is None, "next command not yet implemented")
class TestNextDerivedState(unittest.TestCase):
    def test_refuses_on_plan_drift(self):
        """next exits non-zero when a plan file exists on disk but not in the queue."""
        queue_file = _make_queue([])
        archive_file = _make_archive([])
        plans_dir_tmp = _make_plans_dir(["orphan.md"])
        plans_dir = plans_dir_tmp.name

        with patch.object(sys, "argv", [
            "next",
            "--queue-file", queue_file,
            "--archive-file", archive_file,
            "--plans-dir", plans_dir,
        ]):
            rc = next_cmd.main()

        self.assertEqual(rc, 1)

    def test_picks_first_derived_unblocked(self):
        """next picks the first derived-unblocked task and transitions it."""
        plans_dir_tmp = _make_plans_dir(["t1.md", "t2.md"])
        plans_dir = plans_dir_tmp.name
        queue_file = _make_queue(_resolve_plan_files([
            {"id": "t1", "status": "planned", "title": "One", "plan_file": "docs/plans/t1.md"},
            {"id": "t2", "status": "planned", "title": "Two", "plan_file": "docs/plans/t2.md"},
        ], plans_dir))
        archive_file = _make_archive([])

        derived = {
            "t1": {"derived_status": "blocked"},
            "t2": {"derived_status": "unblocked"},
        }

        transition_calls = []

        def mock_run(cmd, **_kwargs):
            transition_calls.append(cmd)
            return _MockResult(0, "", "")

        with patch.object(next_cmd, "derive_statuses", return_value=derived):
            with patch("subprocess.run", side_effect=mock_run):
                with patch.object(sys, "argv", [
                    "next",
                    "--queue-file", queue_file,
                    "--archive-file", archive_file,
                    "--plans-dir", plans_dir,
                ]):
                    rc = next_cmd.main()

        self.assertEqual(rc, 0)
        self.assertTrue(any("t2" in c and "in-progress" in c for c in transition_calls))

    def test_topological_order_respected(self):
        """next picks the earliest derived-unblocked task in topological order."""
        plans_dir_tmp = _make_plans_dir(["t1.md", "t2.md"])
        plans_dir = plans_dir_tmp.name
        queue_file = _make_queue(_resolve_plan_files([
            {"id": "t1", "status": "planned", "title": "One", "plan_file": "docs/plans/t1.md", "blocked_by": []},
            {"id": "t2", "status": "planned", "title": "Two", "plan_file": "docs/plans/t2.md", "blocked_by": ["t1"]},
        ], plans_dir))
        archive_file = _make_archive([])

        derived = {
            "t1": {"derived_status": "unblocked"},
            "t2": {"derived_status": "unblocked"},
        }

        transition_calls = []

        def mock_run(cmd, **_kwargs):
            transition_calls.append(cmd)
            return _MockResult(0, "", "")

        with patch.object(next_cmd, "derive_statuses", return_value=derived):
            with patch("subprocess.run", side_effect=mock_run):
                with patch.object(sys, "argv", [
                    "next",
                    "--queue-file", queue_file,
                    "--archive-file", archive_file,
                    "--plans-dir", plans_dir,
                ]):
                    rc = next_cmd.main()

        self.assertEqual(rc, 0)
        self.assertTrue(any("t1" in c and "in-progress" in c for c in transition_calls))


if __name__ == "__main__":
    unittest.main()
