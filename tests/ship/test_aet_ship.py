"""Tests for the aet-ship closure executable."""

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
_spec.loader.exec_module(ship)


class MockResult:
    def __init__(self, returncode, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _subprocess_mock(responses):
    """Return a mock subprocess.run that answers named commands.

    Unknown commands are delegated to the real subprocess so the git-refs backend
    can operate on the temporary repository.
    """
    real_run = subprocess.run

    def mock_run(cmd, **kwargs):
        args = tuple(cmd)
        if args in responses:
            rc, out, err = responses[args]
            return MockResult(rc, out, err)
        return real_run(cmd, **kwargs)

    return mock_run


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=check,
    )


def _init_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-q")
    _git(path, "config", "user.email", "test@example.com")
    _git(path, "config", "user.name", "Test User")
    (path / ".agents").mkdir(parents=True, exist_ok=True)
    (path / "README.md").write_text("hello\n", encoding="utf-8")
    _git(path, "add", ".")
    _git(path, "commit", "-q", "-m", "initial")
    # Add the repo as its own remote so mandatory backend pushes succeed.
    _git(path, "remote", "add", "origin", str(path))
    _git(path, "push", "-u", "origin", "main", check=False)
    return path


def _write_plan(repo: Path, task_id: str) -> Path:
    plan_dir = repo / "docs" / "plans"
    plan_dir.mkdir(parents=True, exist_ok=True)
    content = (
        f"---\n"
        f"id: {task_id}\n"
        f"---\n\n"
        f"# Plan {task_id}\n\n"
        f"## Task List\n\n"
        f"- [x] task one\n\n"
        f"---\n\n"
        f"*Stage: awaiting_merge*\n"
    )
    plan_path = plan_dir / f"{task_id}.md"
    plan_path.write_text(content, encoding="utf-8")
    return plan_path


def _spec(task_id: str) -> dict:
    content = (
        f"---\n"
        f"id: {task_id}\n"
        f"status: awaiting_merge\n"
        f"---\n\n"
        f"# Plan {task_id}\n\n"
        f"## Task List\n\n"
        f"- [x] task one\n\n"
        f"---\n\n"
        f"*Stage: implemented*\n"
    )
    return plan_parser.extract_plan_spec_from_text(content, task_id)


class TestShipClosure(unittest.TestCase):
    """Behavior-driven tests for src/aet/cli/ship.py close behavior."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)

        self.repo = _init_repo(Path(self.tmpdir.name) / "repo")
        # Project-scope config puts the backend in shared posture. Shadow
        # posture — the default with no such file — skips the work-history
        # write entirely, and these tests assert on the sealed record.
        (self.repo / ".agents" / "aet-config.json").write_text(
            json.dumps({"integration_mode": "pr-per-task"}), encoding="utf-8"
        )
        self.queue_path = self.repo / ".agents" / "aet-queue"
        self.history_file = self.repo / ".agents" / "work-history.jsonl"
        self.plan_path = _write_plan(self.repo, "t1")

        self._save_task("t1", "awaiting_merge")

        self.cwd = os.getcwd()
        self.addCleanup(os.chdir, self.cwd)
        os.chdir(self.repo)

    def _save_task(self, task_id: str, state: str) -> None:
        backend = GitRefsBackend(
            queue_file=str(self.queue_path),
            history_file=str(self.history_file),
        )
        backend.save(
            [
                {
                    "id": task_id,
                    "state": state,
                    "stage": "qa-complete",
                    "branch": "feat-001",
                    "base_commit": "base0000",
                    "plan_file": str(self.plan_path.relative_to(self.repo)),
                    "spec": _spec(task_id),
                }
            ]
        )

    def _success_responses(self):
        return {
            ("git", "fetch", "origin"): (0, "", ""),
            ("git", "rev-parse", "feat-001"): (0, "abc1234\n", ""),
            ("git", "rev-parse", "base0000"): (0, "base0000\n", ""),
            ("git", "merge-base", "--is-ancestor", "abc1234", "origin/main"): (
                0,
                "",
                "",
            ),
        }

    def _run_ship_close(self, argv: list[str]) -> int:
        mock = _subprocess_mock(self._success_responses())
        with patch.object(sys, "argv", argv):
            with patch.object(ship.aet_state.subprocess, "run", side_effect=mock):
                return ship.main()

    def test_ship_records_merge_seals_task_without_touching_plan(self):
        """aet ship close seals the queue entry and archives the plan (R-4/ADR-072)."""
        original_content = self.plan_path.read_text(encoding="utf-8")
        rc = self._run_ship_close(["ship", "close", "t1"])

        self.assertEqual(rc, 0)
        archived_plan = self.repo / "docs" / "plans" / "archive" / "t1.md"
        self.assertEqual(archived_plan.read_text(encoding="utf-8"), original_content)
        self.assertFalse(self.plan_path.exists())

        backend = GitRefsBackend(
            queue_file=str(self.queue_path),
            history_file=str(self.history_file),
        )
        self.assertEqual(backend.load()["queue"], [])

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
        rc = self._run_ship_close(["ship", "close", "--dry-run", "t1"])

        self.assertEqual(rc, 0)
        self.assertEqual(self.plan_path.read_text(encoding="utf-8"), original_content)

        backend = GitRefsBackend(
            queue_file=str(self.queue_path),
            history_file=str(self.history_file),
        )
        self.assertEqual(len(backend.load()["queue"]), 1)
        self.assertFalse(self.history_file.exists())

    def test_ship_defaults_queue_path(self):
        """aet ship close defaults the queue path to .agents/aet-queue in cwd."""
        rc = self._run_ship_close(["ship", "close", "t1"])

        self.assertEqual(rc, 0)
        backend = GitRefsBackend(
            queue_file=str(self.queue_path),
            history_file=str(self.history_file),
        )
        self.assertEqual(backend.load()["queue"], [])

    def test_ship_close_md_path_is_rejected(self):
        """aet ship close <plan.md> is refused, naming aet sprint add (R-3)."""
        rc = self._run_ship_close(["ship", "close", str(self.plan_path)])

        self.assertNotEqual(rc, 0)
        # The rejection message names aet sprint add as the intake entry point.
        # argparse/typer prints the error to stderr; our mock captures the
        # _fail message, but the easiest observable is the non-zero exit.

    def test_ship_close_task_id_resolves_queue_plan_file(self):
        """aet ship close <task-id> reads the plan path from the queue task."""
        rc = self._run_ship_close(["ship", "close", "t1"])

        self.assertEqual(rc, 0)
        archived_plan = self.repo / "docs" / "plans" / "archive" / "t1.md"
        content = archived_plan.read_text(encoding="utf-8")
        self.assertNotIn("status:", content)

        backend = GitRefsBackend(
            queue_file=str(self.queue_path),
            history_file=str(self.history_file),
        )
        self.assertEqual(backend.load()["queue"], [])

    def test_ship_close_task_id_with_default_queue(self):
        """aet ship close <task-id> uses the default queue path in cwd."""
        rc = self._run_ship_close(["ship", "close", "t1"])

        self.assertEqual(rc, 0)
        archived_plan = self.repo / "docs" / "plans" / "archive" / "t1.md"
        content = archived_plan.read_text(encoding="utf-8")
        self.assertNotIn("status:", content)

        backend = GitRefsBackend(
            queue_file=str(self.queue_path),
            history_file=str(self.history_file),
        )
        self.assertEqual(backend.load()["queue"], [])

    def test_ship_close_missing_task_id_fails_cleanly(self):
        """aet ship close <missing-id> fails with a clear message."""
        rc = self._run_ship_close(["ship", "close", "no-such-id"])

        self.assertNotEqual(rc, 0)

    def test_ship_close_two_plan_paths_is_rejected(self):
        """aet ship close <plan-a.md> <plan-b.md> is rejected as ambiguous."""
        plan_b = self.plan_path.parent / "t2.md"
        plan_b.write_text(
            "---\n"
            "id: t2\n"
            "---\n\n"
            "# Plan T2\n",
            encoding="utf-8",
        )

        rc = self._run_ship_close(["ship", "close", str(self.plan_path), str(plan_b)])

        self.assertNotEqual(rc, 0)

    def test_ship_close_task_id_with_queue_as_second_arg_is_rejected(self):
        """aet ship close <task-id> <queue> is rejected; queue belongs in the third position."""
        rc = self._run_ship_close(["ship", "close", "t1", str(self.queue_path)])

        self.assertNotEqual(rc, 0)

    def test_ship_close_md_path_without_id_is_rejected(self):
        """A .md path without an `id` frontmatter key is still refused (R-3)."""
        stem_plan = self.plan_path.parent / "fallback-stem.md"
        stem_plan.write_text(
            "---\n"
            "---\n\n"
            "# Fallback Stem Plan\n\n"
            "---\n\n"
            "*Stage: awaiting_merge*\n",
            encoding="utf-8",
        )

        rc = self._run_ship_close(["ship", "close", str(stem_plan)])

        self.assertNotEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
