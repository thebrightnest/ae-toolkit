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

_SHIP_PY = Path(__file__).parents[2] / "src" / "aet" / "cli" / "ship.py"
_spec = importlib.util.spec_from_loader(
    "aet_ship", importlib.machinery.SourceFileLoader("aet_ship", str(_SHIP_PY))
)
ship = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ship)

from aet import queue as aet_queue_module  # noqa: E402


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
    """Behavior-driven tests for src/aet/cli/ship.py."""

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
        """aet ship close closes a task by updating the plan and sealing the queue entry."""
        with patch.object(
            sys,
            "argv",
            [
                "ship",
                "close",
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
        """aet ship close --dry-run reports success without changing plan or queue."""
        original_content = self.plan_path.read_text(encoding="utf-8")

        with patch.object(
            sys,
            "argv",
            [
                "ship",
                "close",
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
        """aet ship close defaults the queue path to .agents/work-queue.json in cwd."""
        os.chdir(self.tmpdir.name)

        with patch.object(
            sys,
            "argv",
            [
                "ship",
                "close",
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

    def test_ship_close_plan_path_derives_task_id(self):
        """aet ship close <plan> derives the task id from plan frontmatter."""
        with patch.object(
            sys,
            "argv",
            [
                "ship",
                "close",
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
        live = json.loads(self.queue_path.read_text(encoding="utf-8"))
        self.assertEqual(live["tasks"], [])

    def test_ship_close_task_id_only_uses_queue_plan_file(self):
        """aet ship close <task-id> reads the plan path from the queue task."""
        with patch.object(
            sys,
            "argv",
            [
                "ship",
                "close",
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
        live = json.loads(self.queue_path.read_text(encoding="utf-8"))
        self.assertEqual(live["tasks"], [])

    def test_ship_close_task_id_with_default_queue(self):
        """aet ship close <task-id> uses the default queue path in cwd."""
        os.chdir(self.tmpdir.name)

        with patch.object(
            sys,
            "argv",
            [
                "ship",
                "close",
                "t1",
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
        live = json.loads(self.queue_path.read_text(encoding="utf-8"))
        self.assertEqual(live["tasks"], [])

    def test_ship_close_missing_plan_path_fails_cleanly(self):
        """aet ship close <plan> fails with a clear message when the plan file is missing."""
        with patch.object(
            sys,
            "argv",
            [
                "ship",
                "close",
                str(self.plan_path.parent / "missing.md"),
            ],
        ):
            rc = ship.main()

        self.assertNotEqual(rc, 0)

    def test_ship_close_two_plan_paths_is_rejected(self):
        """aet ship close <plan-a> <plan-b> is rejected as ambiguous."""
        plan_b = self.plan_path.parent / "t2.md"
        plan_b.write_text(
            "---\n"
            "id: t2\n"
            "status: awaiting_merge\n"
            "---\n\n"
            "# Plan T2\n",
            encoding="utf-8",
        )

        with patch.object(
            sys,
            "argv",
            [
                "ship",
                "close",
                str(self.plan_path),
                str(plan_b),
            ],
        ):
            rc = ship.main()

        self.assertNotEqual(rc, 0)

    def test_ship_close_task_id_with_queue_as_second_arg_is_rejected(self):
        """aet ship close <task-id> <queue> is rejected; queue belongs in the third position."""
        with patch.object(
            sys,
            "argv",
            [
                "ship",
                "close",
                "t1",
                str(self.queue_path),
            ],
        ):
            rc = ship.main()

        self.assertNotEqual(rc, 0)

    def test_ship_close_plan_without_id_frontmatter_uses_filename_stem(self):
        """A plan without an `id` frontmatter key falls back to the filename stem."""
        stem_plan = self.plan_path.parent / "fallback-stem.md"
        stem_plan.write_text(
            "---\n"
            "status: awaiting_merge\n"
            "---\n\n"
            "# Fallback Stem Plan\n\n"
            "---\n\n"
            "*Stage: awaiting_merge*\n",
            encoding="utf-8",
        )

        queue = {
            "tasks": [
                {
                    "id": "fallback-stem",
                    "status": "awaiting_merge",
                    "branch": "feat-001",
                    "plan_file": str(stem_plan),
                }
            ]
        }
        self.queue_path.write_text(json.dumps(queue), encoding="utf-8")

        responses = self._success_responses()
        stem_abs = os.path.realpath(str(stem_plan))
        stem_rel = os.path.relpath(stem_abs, os.path.realpath(str(self.queue_path.parent)))
        responses[("git", "add", stem_rel)] = (0, "", "")
        responses[("git", "commit", "-m", "chore(fallback-stem): mark plan as merged")] = (
            0,
            "",
            "",
        )
        t1_abs = os.path.realpath(str(self.plan_path))
        t1_rel = os.path.relpath(t1_abs, os.path.realpath(str(self.queue_path.parent)))
        responses.pop(("git", "add", t1_rel), None)
        responses.pop(("git", "commit", "-m", "chore(t1): mark plan as merged"), None)

        with patch.object(
            sys,
            "argv",
            [
                "ship",
                "close",
                str(stem_plan),
                str(self.queue_path),
            ],
        ):
            mock = _subprocess_mock(responses)
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
        content = stem_plan.read_text(encoding="utf-8")
        self.assertIn("status: merged", content)
        live = json.loads(self.queue_path.read_text(encoding="utf-8"))
        self.assertEqual(live["tasks"], [])


if __name__ == "__main__":
    unittest.main()
