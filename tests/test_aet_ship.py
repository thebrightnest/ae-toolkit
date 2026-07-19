"""Tests for the aet-ship closure executable."""

import importlib.machinery
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_SHIP_PY = Path(__file__).parent.parent / "aet-ship" / "bin" / "ship"
_spec = importlib.util.spec_from_loader(
    "aet_ship", importlib.machinery.SourceFileLoader("aet_ship", str(_SHIP_PY))
)
ship = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ship)

import aet_queue as aet_queue_module  # noqa: E402


class MockResult:
    def __init__(self, returncode, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _subprocess_mock(responses):
    """Return a mock subprocess.run that answers git and gh commands.

    responses maps tuple(program, *args) -> (returncode, stdout, stderr).
    """

    def mock_run(cmd, **kwargs):
        args = tuple(cmd)
        rc, out, err = responses.get(args, (1, "", ""))
        return MockResult(rc, out, err)

    return mock_run


class TestShipClosure(unittest.TestCase):
    """Behavior-driven tests for aet-ship/bin/ship."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)

        base = Path(self.tmpdir.name)
        self.queue_path = base / ".agents" / "work-queue.json"
        self.queue_path.parent.mkdir(parents=True)
        self.history_file = self.queue_path.with_name("work-history.jsonl")

        self.plan_path = base / "docs" / "plans" / "t1.md"
        self.plan_path.parent.mkdir(parents=True)
        self.plan_path.write_text(
            "---\n"
            "id: t1\n"
            "status: awaiting_merge\n"
            "---\n\n"
            "# Plan T1\n\n"
            "---\n\n"
            "*Stage: awaiting_merge*\n",
            encoding="utf-8",
        )

        queue = {
            "tasks": [
                {
                    "id": "t1",
                    "status": "awaiting_merge",
                    "branch": "feat-001",
                    "plan_file": str(self.plan_path),
                }
            ]
        }
        self.queue_path.write_text(json.dumps(queue), encoding="utf-8")

        self.cwd = os.getcwd()
        self.addCleanup(os.chdir, self.cwd)

    def _success_responses(self):
        plan_abs = os.path.realpath(str(self.plan_path))
        plan_rel = os.path.relpath(plan_abs, os.path.realpath(str(self.queue_path.parent)))
        return {
            ("git", "fetch", "origin"): (0, "", ""),
            ("git", "rev-parse", "feat-001"): (0, "abc1234\n", ""),
            ("git", "merge-base", "--is-ancestor", "abc1234", "origin/main"): (
                0,
                "",
                "",
            ),
            ("git", "add", plan_rel): (0, "", ""),
            ("git", "diff", "--cached", "--quiet"): (1, "", ""),
            ("git", "commit", "-m", "chore(t1): mark plan as merged"): (
                0,
                "",
                "",
            ),
            ("git", "push"): (0, "", ""),
        }

    def test_ship_records_merge_updates_plan_and_removes_task(self):
        """ship closes a task by updating the plan and sealing the queue entry."""
        with patch.object(
            sys,
            "argv",
            [
                "ship",
                "t1",
                str(self.plan_path),
                str(self.queue_path),
            ],
        ):
            mock = _subprocess_mock(self._success_responses())
            with patch.object(
                ship.aet_state.subprocess,
                "run",
                side_effect=mock,
            ):
                with patch.object(
                    aet_queue_module.subprocess,
                    "run",
                    side_effect=mock,
                ):
                    rc = ship.main()

        self.assertEqual(rc, 0)

        content = self.plan_path.read_text(encoding="utf-8")
        self.assertIn("status: merged", content)
        self.assertIn("*Stage: merged*", content)

        live = json.loads(self.queue_path.read_text(encoding="utf-8"))
        self.assertEqual(live["tasks"], [])

        lines = self.history_file.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 1)
        settled = json.loads(lines[0])
        self.assertEqual(settled["id"], "t1")
        self.assertEqual(settled["state"], "merged")
        self.assertEqual(settled["merge_commit"], "abc1234")
        self.assertIn("settled_at", settled)

    def test_ship_dry_run_does_not_mutate(self):
        """ship --dry-run reports success without changing plan or queue."""
        original_content = self.plan_path.read_text(encoding="utf-8")

        with patch.object(
            sys,
            "argv",
            [
                "ship",
                "--dry-run",
                "t1",
                str(self.plan_path),
                str(self.queue_path),
            ],
        ):
            mock = _subprocess_mock(self._success_responses())
            with patch.object(
                ship.aet_state.subprocess,
                "run",
                side_effect=mock,
            ):
                with patch.object(
                    aet_queue_module.subprocess,
                    "run",
                    side_effect=mock,
                ):
                    rc = ship.main()

        self.assertEqual(rc, 0)
        self.assertEqual(self.plan_path.read_text(encoding="utf-8"), original_content)

        live = json.loads(self.queue_path.read_text(encoding="utf-8"))
        self.assertEqual(len(live["tasks"]), 1)
        self.assertFalse(self.history_file.exists())

    def test_ship_defaults_queue_path(self):
        """ship defaults the queue path to .agents/work-queue.json in cwd."""
        os.chdir(self.tmpdir.name)

        with patch.object(
            sys,
            "argv",
            [
                "ship",
                "t1",
                str(self.plan_path),
            ],
        ):
            mock = _subprocess_mock(self._success_responses())
            with patch.object(
                ship.aet_state.subprocess,
                "run",
                side_effect=mock,
            ):
                with patch.object(
                    aet_queue_module.subprocess,
                    "run",
                    side_effect=mock,
                ):
                    rc = ship.main()

        self.assertEqual(rc, 0)
        live = json.loads(self.queue_path.read_text(encoding="utf-8"))
        self.assertEqual(live["tasks"], [])


if __name__ == "__main__":
    unittest.main()
