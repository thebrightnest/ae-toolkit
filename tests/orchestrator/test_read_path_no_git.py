"""No-git guard tests for the aet-work read path.

Any git subprocess invocation on the status/next/orchestrator read path must
fail the test. Writes through aet-state transition are allowed.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.xdist_group("telemetry-dir")

_REPO_ROOT = Path(__file__).parents[2]
_STATUS_PY = _REPO_ROOT / "src" / "aet" / "cli" / "status.py"
_NEXT_PY = _REPO_ROOT / "src" / "aet" / "cli" / "next.py"
_ORCHESTRATOR_PY = _REPO_ROOT / "src" / "aet" / "cli" / "orchestrator.py"

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
        stem = Path(name).stem
        Path(tmp.name, name).write_text(
            f"---\nid: {stem}\nstatus: queued\n---\n\n# Plan\n",
            encoding="utf-8",
        )
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
