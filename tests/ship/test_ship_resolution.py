"""Tests that aet ship resolves task records, not plan files (R-2, R-3, R-4, R-9)."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from aet import plan_parser
from aet.backends.git_refs_backend import GitRefsBackend

_SHIP_PY = Path(__file__).parents[2] / "src" / "aet" / "cli" / "ship.py"
_spec = importlib.util.spec_from_loader(
    "aet_ship", importlib.machinery.SourceFileLoader("aet_ship", str(_SHIP_PY))
)
ship = importlib.util.module_from_spec(_spec)
sys.modules["aet_ship"] = ship
_spec.loader.exec_module(ship)


class MockResult:
    def __init__(self, returncode, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _subprocess_mock(responses, record=None, branch="feat-001"):
    """Return a mock subprocess.run that answers named commands.

    Unknown commands are delegated to the real subprocess so the git-refs backend
    can operate on the temporary repository.
    """
    real_run = subprocess.run

    def _lookup(cmd):
        if isinstance(cmd, str):
            if cmd in responses:
                return responses[cmd]
            return None
        args = list(cmd)
        if len(args) >= 3 and args[0] == "git" and args[1] == "-C":
            args = ["git"] + args[3:]
        t_args = tuple(args)
        if t_args in responses:
            return responses[t_args]

        for key in responses:
            if not isinstance(key, tuple):
                continue
            if len(key) == len(args):
                match = True
                for a, k in zip(args, key):
                    if a == k:
                        continue
                    if ".." in a and ".." in k and a.split("..")[0] == k.split("..")[0]:
                        continue
                    branch_aliases = ("HEAD", branch, f"origin/{branch}", "t1", "origin/t1")
                    if a in branch_aliases and k in branch_aliases:
                        continue
                    match = False
                    break
                if match:
                    return responses[key]
            if len(args) == len(key) and len(args) >= 3 and args[1] == "diff" and ".." in args[2]:
                normalized = [args[0], args[1], args[2].split("..")[0]] + args[3:]
                if tuple(normalized) == key:
                    return responses[key]

        if len(args) >= 3 and args[1] == "-c":
            for key, value in responses.items():
                if isinstance(key, tuple) and len(key) >= 3 and key[1] == "-c" and key[2] == args[2]:
                    return value
        return None

    def mock_run(cmd, **kwargs):
        if record is not None:
            record.append(cmd if isinstance(cmd, str) else tuple(cmd))
        hit = _lookup(cmd)
        if hit is not None:
            rc, out, err = hit
            return MockResult(rc, out, err)
        return real_run(cmd, **kwargs)

    return mock_run


class TestShipResolution(unittest.TestCase):
    """Task-record resolution for ship gate/open/merge/default commands."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)

        base = Path(self.tmpdir.name)
        self.repo = base / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "-C", str(self.repo), "init", "-q"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "config", "user.email", "test@example.com"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "config", "user.name", "Test User"], check=True)
        (self.repo / ".agents").mkdir(parents=True, exist_ok=True)
        (self.repo / "README.md").write_text("hello\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.repo), "add", "."], check=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "-q", "-m", "initial"], check=True)

        self.cwd = os.getcwd()
        self.addCleanup(os.chdir, self.cwd)
        os.chdir(self.repo)

    def _spec(self, task_id: str = "t1") -> dict:
        content = (
            f"---\n"
            f"id: {task_id}\n"
            f"status: in_progress\n"
            f"---\n\n"
            f"# Plan {task_id}\n\n"
            f"## Task List\n\n"
            f"- [x] task one\n\n"
            f"---\n\n"
            f"*Stage: implemented*\n"
        )
        return plan_parser.extract_plan_spec_from_text(content, task_id)

    def _save_task(
        self,
        task_id: str = "t1",
        state: str = "awaiting_merge",
        spec: dict | None = None,
        sealed: bool = False,
    ) -> None:
        backend = GitRefsBackend(
            queue_file=str(self.repo / ".agents" / "aet-queue"),
            history_file=str(self.repo / ".agents" / "work-history.jsonl"),
        )
        task = {
            "id": task_id,
            "state": state,
            "stage": "qa-complete",
            "branch": "feat-001",
            "plan_file": f"docs/plans/{task_id}.md",
        }
        if spec is not None:
            task["spec"] = spec
        if sealed:
            # Move the task to the append-only history file.
            history_path = Path(backend._history_path())
            history_path.parent.mkdir(parents=True, exist_ok=True)
            with history_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(task) + "\n")
        else:
            backend.save([task])

    def _gate_success_responses(self, branch="feat-001"):
        origin_main = "origin-main-sha"
        return {
            ("git", "fetch", "origin"): (0, "", ""),
            ("git", "rev-parse", "--show-toplevel"): (0, f"{self.repo}\n", ""),
            ("git", "rev-parse", "--verify", "--quiet", branch): (0, "", ""),
            ("git", "rev-parse", "--verify", "--quiet", f"origin/{branch}"): (0, "", ""),
            ("git", "rev-parse", "--verify", "--quiet", "t1"): (0, "", ""),
            ("git", "rev-parse", "--verify", "--quiet", "origin/t1"): (0, "", ""),
            ("git", "worktree", "list", "--porcelain"): (0, f"worktree {self.repo}\nbranch refs/heads/{branch}\n", ""),
            ("git", "merge-base", "HEAD", "origin/main"): (0, f"{origin_main}\n", ""),
            ("git", "rev-parse", "origin/main"): (0, f"{origin_main}\n", ""),
            ("git", "branch", "--show-current"): (0, f"{branch}\n", ""),
            ("git", "status", "--short"): (0, "", ""),
            ("git", "diff", "origin/main", "--name-only"): (0, "src/thing.py\n", ""),
            ("true",): (0, "", ""),
        }

    def _run_gate(self, argv: list[str], env: dict | None = None) -> int:
        """Run a ship command with git subprocess mocked and the test gate disabled."""
        merged_env = {"AET_SHIP_TEST_CMD": "true"}
        if env:
            merged_env.update(env)
        with patch.dict(os.environ, merged_env, clear=False):
            with patch.object(sys, "argv", argv):
                mock = _subprocess_mock(self._gate_success_responses())
                with patch.object(ship.aet_state.subprocess, "run", side_effect=mock):
                    with patch.object(ship.subprocess, "run", side_effect=mock):
                        return ship.main()

    def test_gate_accepts_task_id(self):
        """``aet ship gate <id>`` resolves to the live task record."""
        self._save_task(spec=self._spec())
        rc = self._run_gate(["ship", "gate", "t1"])
        self.assertEqual(rc, 0)

    def test_gate_succeeds_when_plan_file_missing(self):
        """``aet ship gate <id>`` succeeds when the record carries a spec and the plan file is gone (R-2, R-4)."""
        self._save_task(spec=self._spec())
        # Ensure the conventional plan path does not exist.
        plan_path = self.repo / "docs" / "plans" / "t1.md"
        self.assertFalse(plan_path.exists())
        rc = self._run_gate(["ship", "gate", "t1"])
        self.assertEqual(rc, 0)

    def test_gate_rejects_md_path_form(self):
        """A ``.md`` argument is refused, naming ``aet sprint add`` as the entry point (R-3)."""
        rc = self._run_gate(["ship", "gate", "docs/plans/t1.md"])
        self.assertEqual(rc, 1)

    def test_gate_rejects_missing_task_id(self):
        """A missing task id errors naming the task id."""
        rc = self._run_gate(["ship", "gate", "no-such-id"])
        self.assertEqual(rc, 1)

    def test_gate_rejects_task_without_spec(self):
        """A live task without a spec fails closed naming the task id (R-9)."""
        self._save_task(spec=None)
        rc = self._run_gate(["ship", "gate", "t1"])
        self.assertEqual(rc, 1)

    def test_gate_reports_settled_task(self):
        """A settled merged task prints the merge commit and exits 0 (R-4)."""
        self._save_task(
            state="merged",
            spec=self._spec(),
            sealed=True,
        )
        # Patch the history so the sealed record carries a merge commit.
        history_path = self.repo / ".agents" / "work-history.jsonl"
        sealed = json.loads(history_path.read_text(encoding="utf-8").strip().splitlines()[-1])
        sealed["merge_commit"] = "deadbeef"
        sealed["merge_strategy"] = "regular"
        history_path.write_text(json.dumps(sealed) + "\n", encoding="utf-8")

        rc = self._run_gate(["ship", "gate", "t1"])
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
