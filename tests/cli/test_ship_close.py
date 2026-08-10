"""Tests for `aet ship close` post-merge closure transaction (slc-04)."""

from __future__ import annotations

import argparse
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

import pytest

from aet.backends.git_refs_backend import GitRefsBackend

_SHIP_PY = Path(__file__).parents[2] / "src" / "aet" / "cli" / "ship.py"
_spec = importlib.util.spec_from_loader(
    "aet_ship_close", importlib.machinery.SourceFileLoader("aet_ship_close", str(_SHIP_PY))
)
ship = importlib.util.module_from_spec(_spec)
sys.modules["aet_ship_close"] = ship
_spec.loader.exec_module(ship)

pytestmark = pytest.mark.xdist_group("cwd")


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
    (path / "README.md").write_text("# test\n", encoding="utf-8")
    _git(path, "add", ".")
    _git(path, "commit", "-q", "-m", "initial")
    _git(path, "remote", "add", "origin", str(path))
    _git(path, "push", "-u", "origin", "main", check=False)
    return path


def _write_plan(repo: Path, task_id: str, *, r_ids: list[str] | None = None) -> Path:
    plan_dir = repo / "docs" / "plans"
    plan_dir.mkdir(parents=True, exist_ok=True)
    prd_mentions = " ".join(r_ids) if r_ids else ""
    content = (
        f"---\n"
        f"id: {task_id}\n"
        f"size: M\n"
        f"---\n\n"
        f"# Plan {task_id}\n\n"
        f"PRD: `docs/prds/demo-prd.md` ({prd_mentions})\n\n"
        f"## Task List\n\n"
        f"- [x] one\n\n"
        f"---\n\n"
        f"*Stage: awaiting_merge*\n"
    )
    plan_path = plan_dir / f"{task_id}.md"
    plan_path.write_text(content, encoding="utf-8")
    return plan_path


def _write_queue(repo: Path, tasks: list[dict]) -> str:
    queue_path = repo / ".agents" / "work-queue.json"
    queue_path.write_text(json.dumps({"tasks": tasks}), encoding="utf-8")
    return str(queue_path)


def _task(task_id: str, plan_path: Path, branch: str) -> dict:
    return {
        "id": task_id,
        "state": "awaiting_merge",
        "stage": "qa-complete",
        "title": f"task {task_id}",
        "plan_file": str(plan_path.relative_to(plan_path.parents[2])),
        "branch": branch,
    }


class MockResult:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _subprocess_mock(responses: dict):
    def mock_run(cmd, **kwargs):
        args = tuple(cmd)
        rc, out, err = responses.get(args, (1, "", ""))
        return MockResult(rc, out, err)

    return mock_run


class TestShipCloseTransaction(unittest.TestCase):
    """Integration tests for the terminal closure transaction."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.repo = _init_repo(Path(self.tmpdir.name) / "repo")
        self.cwd = os.getcwd()
        self.addCleanup(os.chdir, self.cwd)
        os.chdir(self.repo)

    def test_close_success_leaves_footer_queue_ledger_consistent(self):
        """aet ship close writes footer, queue, and ledger in one transaction."""
        plan_path = _write_plan(self.repo, "t1", r_ids=["R-5", "R-8"])
        queue_file = _write_queue(self.repo, [_task("t1", plan_path, "t1")])
        history_file = str(self.repo / ".agents" / "work-history.jsonl")

        # Create and merge a feature branch.
        _git(self.repo, "checkout", "-q", "-b", "t1")
        (self.repo / "feat.txt").write_text("feat\n", encoding="utf-8")
        _git(self.repo, "add", ".")
        _git(self.repo, "commit", "-q", "-m", "feat(t1): implement")
        _git(self.repo, "checkout", "-q", "main")
        _git(self.repo, "merge", "-q", "--no-ff", "t1", "-m", "Merge t1")
        args = argparse.Namespace(
            command="close",
            task_id=str(plan_path),
            plan=None,
            queue=queue_file,
            branch=None,
            merge_commit=None,
            target_branch=None,
            dry_run=False,
        )
        with patch.dict(os.environ, {"AET_BACKEND": "git-refs"}):
            rc = ship.cmd_ship(args)
        self.assertEqual(rc, 0)

        # Footer matches terminal state.
        content = plan_path.read_text(encoding="utf-8")
        self.assertIn("*Stage: merged*", content)
        self.assertNotIn("status:", content)

        # Live queue no longer contains the task.
        backend = GitRefsBackend(queue_file=queue_file, history_file=history_file)
        data = backend.load()
        self.assertEqual(data["queue"], [])

        # Ledger contains a land event with the R-8 digest.
        ledger_path = self.repo / ".agents" / "ledger.jsonl"
        events = [
            json.loads(line)
            for line in ledger_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        land_events = [e for e in events if e.get("kind") == "land"]
        self.assertEqual(len(land_events), 1)
        land = land_events[0]
        self.assertEqual(land["task"], "t1")
        self.assertEqual(land["ref_kind"], "git-sha")
        self.assertTrue(land["ref"])
        self.assertIn("R-5", land["payload"]["prd_r_ids"])
        self.assertIn("R-8", land["payload"]["prd_r_ids"])
        self.assertTrue(land["payload"]["merge_ref"])
        self.assertTrue(land["payload"]["plan_hash"])

    def test_close_refuses_missing_plan_fail_closed(self):
        """A plan file missing from checkout and merged branch refuses closure."""
        plan_path = self.repo / "docs" / "plans" / "t1.md"
        queue_file = _write_queue(self.repo, [_task("t1", plan_path, "t1")])

        _git(self.repo, "checkout", "-q", "-b", "t1")
        (self.repo / "feat.txt").write_text("feat\n", encoding="utf-8")
        _git(self.repo, "add", ".")
        _git(self.repo, "commit", "-q", "-m", "feat(t1): implement")
        _git(self.repo, "checkout", "-q", "main")
        _git(self.repo, "merge", "-q", "--no-ff", "t1", "-m", "Merge t1")

        args = argparse.Namespace(
            command="close",
            task_id="t1",
            plan=None,
            queue=queue_file,
            branch=None,
            merge_commit=None,
            target_branch=None,
            dry_run=False,
        )
        rc = ship.cmd_ship(args)
        self.assertNotEqual(rc, 0)

    def test_close_leaves_no_partial_refs_on_save_failure(self):
        """A failure during the atomic ref transaction writes no partial refs."""
        plan_path = _write_plan(self.repo, "t1")
        queue_file = _write_queue(self.repo, [_task("t1", plan_path, "t1")])
        history_file = str(self.repo / ".agents" / "work-history.jsonl")

        _git(self.repo, "checkout", "-q", "-b", "t1")
        (self.repo / "feat.txt").write_text("feat\n", encoding="utf-8")
        _git(self.repo, "add", ".")
        _git(self.repo, "commit", "-q", "-m", "feat(t1): implement")
        _git(self.repo, "checkout", "-q", "main")
        _git(self.repo, "merge", "-q", "--no-ff", "t1", "-m", "Merge t1")

        backend = GitRefsBackend(queue_file=queue_file, history_file=history_file)

        def _failing_save(queue):
            raise RuntimeError("simulated interrupt")

        backend.save = _failing_save  # type: ignore[method-assign]

        args = argparse.Namespace(
            command="close",
            task_id="t1",
            plan=None,
            queue=queue_file,
            branch=None,
            merge_commit=None,
            target_branch=None,
            dry_run=False,
        )

        with patch.object(ship.aet_state, "make_backend", return_value=backend):
            rc = ship.cmd_ship(args)
        self.assertNotEqual(rc, 0)

        # No refs should have been written.
        refs = _git(
            self.repo, "for-each-ref", "--format=%(refname)", "refs/aet/"
        ).stdout.strip()
        self.assertEqual(refs, "")


class TestShipCloseParser(unittest.TestCase):
    """Argument parsing for the close subcommand."""

    def test_close_subcommand_parses_plan_path(self):
        """aet ship close accepts a plan file as the first positional."""
        parser = ship.build_parser()
        args = parser.parse_args(["close", "docs/plans/t1.md"])
        self.assertEqual(args.command, "close")
        self.assertEqual(args.task_id, "docs/plans/t1.md")
