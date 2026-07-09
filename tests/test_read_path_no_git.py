"""No-git guard tests for the aet-work read path.

Any git subprocess invocation on the status/next/orchestrator read path must
fail the test. Writes through aet-state transition are allowed.
"""

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
_ORCHESTRATOR_PY = _REPO_ROOT / "aet-work" / "bin" / "orchestrator"

_status_spec = importlib.util.spec_from_loader(
    "status", importlib.machinery.SourceFileLoader("status", str(_STATUS_PY))
)
status = importlib.util.module_from_spec(_status_spec)
_status_spec.loader.exec_module(status)

_next_spec = importlib.util.spec_from_loader(
    "next", importlib.machinery.SourceFileLoader("next", str(_NEXT_PY))
)
next_cmd = importlib.util.module_from_spec(_next_spec)
_next_spec.loader.exec_module(next_cmd)

_orchestrator_spec = importlib.util.spec_from_loader(
    "orchestrator", importlib.machinery.SourceFileLoader("orchestrator", str(_ORCHESTRATOR_PY))
)
orchestrator = importlib.util.module_from_spec(_orchestrator_spec)
_orchestrator_spec.loader.exec_module(orchestrator)


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


class _NoGitRun:
    """Record subprocess.run calls and raise if a git/derive command is used."""

    def __init__(self):
        self.calls: list[list[str]] = []

    def __call__(self, cmd, **kwargs):
        self.calls.append(list(cmd))
        if self._is_forbidden(cmd):
            raise AssertionError(f"Read path invoked forbidden subprocess: {cmd}")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    @staticmethod
    def _is_forbidden(cmd) -> bool:
        if not cmd:
            return False
        # Any git command is forbidden on the read path.
        if cmd[0] == "git":
            return True
        # aet-state derive is forbidden; aet-state transition is a write and allowed.
        if "aet-state" in str(cmd[0]) and "derive" in cmd:
            return True
        return False


class TestStatusReadPathNoGit(unittest.TestCase):
    def test_status_uses_stored_state_no_subprocess(self):
        """status renders a projection of stored state without calling git or derive."""
        plans_dir_tmp = _make_plans_dir(["t1.md", "t2.md"])
        plans_dir = plans_dir_tmp.name
        queue_file = _make_queue(_resolve_plan_files([
            {"id": "t1", "state": "ready", "title": "One", "plan_file": "docs/plans/t1.md"},
            {"id": "t2", "state": "blocked", "title": "Two", "plan_file": "docs/plans/t2.md"},
        ], plans_dir))
        history_file = _make_history([])

        no_git = _NoGitRun()
        stdout = io.StringIO()
        with patch.object(subprocess, "run", side_effect=no_git):
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
        self.assertIn("ready: 1", output)
        self.assertIn("blocked: 1", output)
        self.assertIn("t1", output)
        self.assertIn("t2", output)


class TestNextReadPathNoGit(unittest.TestCase):
    def test_next_uses_stored_ready_task_no_git(self):
        """next picks a stored ready task and transitions it without calling git or derive."""
        plans_dir_tmp = _make_plans_dir(["t1.md"])
        plans_dir = plans_dir_tmp.name
        queue_file = _make_queue(_resolve_plan_files([
            {"id": "t1", "state": "ready", "title": "One", "plan_file": "docs/plans/t1.md"},
        ], plans_dir))
        history_file = _make_history([])

        transition_calls = []

        def mock_run(cmd, **kwargs):
            transition_calls.append(list(cmd))
            if _NoGitRun._is_forbidden(cmd):
                raise AssertionError(f"next invoked forbidden subprocess: {cmd}")
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        stdout = io.StringIO()
        with patch.object(subprocess, "run", side_effect=mock_run):
            with patch.object(sys, "stdout", stdout):
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
            f"Expected transition call for t1, got {transition_calls}",
        )


class TestOrchestratorReadPathNoGit(unittest.TestCase):
    def test_get_next_ready_task_no_git(self):
        """Orchestrator read helper selects ready tasks without git."""
        queue = [
            {"id": "t1", "state": "blocked"},
            {"id": "t2", "state": "ready"},
        ]

        no_git = _NoGitRun()
        with patch.object(subprocess, "run", side_effect=no_git):
            task = orchestrator.get_next_ready_task(queue)

        self.assertIsNotNone(task)
        self.assertEqual(task["id"], "t2")

    def test_has_pending_tasks_no_git(self):
        """Orchestrator pending check uses stored non-terminal states without git."""
        queue = [
            {"id": "t1", "state": "merged"},
            {"id": "t2", "state": "ready"},
        ]

        no_git = _NoGitRun()
        with patch.object(subprocess, "run", side_effect=no_git):
            pending = orchestrator.has_pending_tasks(queue)

        self.assertTrue(pending)

    def test_has_pending_tasks_false_when_terminal(self):
        """Terminal stored states are not pending."""
        queue = [
            {"id": "t1", "state": "merged"},
            {"id": "t2", "state": "abandoned"},
        ]

        no_git = _NoGitRun()
        with patch.object(subprocess, "run", side_effect=no_git):
            pending = orchestrator.has_pending_tasks(queue)

        self.assertFalse(pending)


if __name__ == "__main__":
    unittest.main()
