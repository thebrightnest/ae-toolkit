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
    queue_path = repo / ".agents" / "aet-queue"
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    backend = GitRefsBackend(
        queue_file=str(queue_path),
        history_file=str(repo / ".agents" / "work-history.jsonl"),
    )
    backend.save(tasks)
    return str(queue_path)


def _head(repo: Path) -> str:
    """Return the current HEAD sha — the commit a branch made now starts at."""
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def _task(
    task_id: str, plan_path: Path, branch: str, base_commit: str | None = None
) -> dict:
    return {
        "id": task_id,
        "state": "awaiting_merge",
        "stage": "qa-complete",
        "title": f"task {task_id}",
        "plan_file": str(plan_path.relative_to(plan_path.parents[2])),
        "branch": branch,
        # ADR-064: the commit the branch was created at. Recorded by the
        # orchestrator at branch creation; without it, closure cannot tell an
        # undiverged branch from a merged one.
        "base_commit": base_commit,
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

    def test_close_success_seals_queue_and_ledger_without_touching_plan(self):
        """aet ship close seals queue and ledger; the plan file is left alone (R-4)."""
        plan_path = _write_plan(self.repo, "t1", r_ids=["R-5", "R-8"])
        original_content = plan_path.read_text(encoding="utf-8")
        queue_file = _write_queue(self.repo, [_task("t1", plan_path, "t1", _head(self.repo))])
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
            task_id="t1",
            plan=None,
            queue=queue_file,
            branch=None,
            merge_commit=None,
            target_branch=None,
            dry_run=False,
        )
        # This test asserts on the ledger write itself, so it pins the ledger to
        # its own fixture repo rather than inheriting conftest's _isolate_ledger
        # tmp dir — the override path that fixture documents.
        env = {
            "AET_BACKEND": "git-refs",
            "AET_LEDGER_PATH": str(self.repo / ".agents" / "ledger.jsonl"),
        }
        with patch.dict(os.environ, env):
            rc = ship.cmd_ship(args)
        self.assertEqual(rc, 0)

        # The plan file is untouched: no footer rewrite, no archive move (R-4).
        self.assertTrue(plan_path.exists())
        self.assertEqual(plan_path.read_text(encoding="utf-8"), original_content)
        self.assertFalse((plan_path.parent / "archive" / plan_path.name).exists())

        # Live queue no longer contains the task.
        backend = GitRefsBackend(queue_file=queue_file, history_file=history_file)
        data = backend.load()
        self.assertEqual(data["queue"], [])

        # Ledger contains a land event with the R-8 digest and no archive path.
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
        self.assertNotIn("archived_to", land["payload"])

        # No plan-state commit is created anywhere in the lifecycle (R-4).
        log = _git(self.repo, "log", "--format=%s", "--all").stdout
        self.assertNotIn("mark plan stage", log)

    def test_close_succeeds_when_plan_file_missing(self):
        """Closure resolves from the record; a missing plan file is not fatal (R-19)."""
        plan_path = self.repo / "docs" / "plans" / "t1.md"
        queue_file = _write_queue(self.repo, [_task("t1", plan_path, "t1", _head(self.repo))])

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
        self.assertEqual(rc, 0)

        # The merge is recorded and the queue sealed even without the plan file.
        backend = GitRefsBackend(
            queue_file=queue_file,
            history_file=str(self.repo / ".agents" / "work-history.jsonl"),
        )
        self.assertEqual(backend.load()["queue"], [])
        log = _git(self.repo, "log", "--format=%s", "--all").stdout
        self.assertNotIn("mark plan stage", log)

    def test_close_leaves_no_partial_refs_on_save_failure(self):
        """A failure during the atomic ref transaction writes no partial refs."""
        plan_path = _write_plan(self.repo, "t1")
        queue_file = _write_queue(self.repo, [_task("t1", plan_path, "t1", _head(self.repo))])
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

        # The save never completed, so no sealed ref was written and the live
        # task ref (written by the test setup) is still intact.
        refs = _git(
            self.repo, "for-each-ref", "--format=%(refname)", "refs/aet/"
        ).stdout.strip()
        self.assertNotIn("refs/aet/sealed/", refs)
        self.assertIn("refs/aet/tasks/t1", refs)

    def _branch_exists(self, branch: str) -> bool:
        return (
            _git(self.repo, "show-ref", "--verify", "--quiet", f"refs/heads/{branch}", check=False).returncode
            == 0
        )

    def _remote_branch_exists(self, branch: str) -> bool:
        return (
            _git(self.repo, "show-ref", "--verify", "--quiet", f"refs/remotes/origin/{branch}", check=False).returncode
            == 0
        )

    def test_close_delete_branch_removes_remote_and_local_after_record(self):
        """`--delete-branch` deletes remote and local branches after closure."""
        plan_path = _write_plan(self.repo, "t1")
        queue_file = _write_queue(self.repo, [_task("t1", plan_path, "t1", _head(self.repo))])

        _git(self.repo, "checkout", "-q", "-b", "t1")
        (self.repo / "feat.txt").write_text("feat\n", encoding="utf-8")
        _git(self.repo, "add", ".")
        _git(self.repo, "commit", "-q", "-m", "feat(t1): implement")
        _git(self.repo, "push", "-u", "origin", "t1", check=False)
        _git(self.repo, "checkout", "-q", "main")
        _git(self.repo, "merge", "-q", "--no-ff", "t1", "-m", "Merge t1")
        _git(self.repo, "push", "origin", "main", check=False)

        args = argparse.Namespace(
            command="close",
            task_id="t1",
            plan=None,
            queue=queue_file,
            branch=None,
            merge_commit=None,
            target_branch=None,
            dry_run=False,
            delete_branch=True,
        )
        with patch.dict(os.environ, {"AET_BACKEND": "git-refs"}):
            rc = ship.cmd_ship(args)
        self.assertEqual(rc, 0)
        self.assertFalse(self._branch_exists("t1"))
        self.assertFalse(self._remote_branch_exists("t1"))

    def test_close_delete_branch_leaves_branches_intact_when_record_fails(self):
        """A failing record-merge exits EXIT_DELETE_BEFORE_RECORD without deleting branches."""
        plan_path = _write_plan(self.repo, "t1")
        queue_file = _write_queue(self.repo, [_task("t1", plan_path, "t1", _head(self.repo))])

        _git(self.repo, "checkout", "-q", "-b", "t1")
        (self.repo / "feat.txt").write_text("feat\n", encoding="utf-8")
        _git(self.repo, "add", ".")
        _git(self.repo, "commit", "-q", "-m", "feat(t1): implement")
        _git(self.repo, "push", "-u", "origin", "t1", check=False)
        # Do NOT merge to main, so record-merge fails.

        args = argparse.Namespace(
            command="close",
            task_id="t1",
            plan=None,
            queue=queue_file,
            branch=None,
            merge_commit=None,
            target_branch=None,
            dry_run=False,
            delete_branch=True,
        )
        with patch.dict(os.environ, {"AET_BACKEND": "git-refs"}):
            rc = ship.cmd_ship(args)
        self.assertEqual(rc, ship.EXIT_DELETE_BEFORE_RECORD)
        self.assertTrue(self._branch_exists("t1"))
        self.assertTrue(self._remote_branch_exists("t1"))

    def test_close_delete_branch_dry_run_does_not_delete(self):
        """`--delete-branch --dry-run` reports deletions without executing them."""
        plan_path = _write_plan(self.repo, "t1")
        queue_file = _write_queue(self.repo, [_task("t1", plan_path, "t1", _head(self.repo))])

        _git(self.repo, "checkout", "-q", "-b", "t1")
        (self.repo / "feat.txt").write_text("feat\n", encoding="utf-8")
        _git(self.repo, "add", ".")
        _git(self.repo, "commit", "-q", "-m", "feat(t1): implement")
        _git(self.repo, "push", "-u", "origin", "t1", check=False)
        _git(self.repo, "checkout", "-q", "main")
        _git(self.repo, "merge", "-q", "--no-ff", "t1", "-m", "Merge t1")
        _git(self.repo, "push", "origin", "main", check=False)

        args = argparse.Namespace(
            command="close",
            task_id="t1",
            plan=None,
            queue=queue_file,
            branch=None,
            merge_commit=None,
            target_branch=None,
            dry_run=True,
            delete_branch=True,
        )
        with patch.dict(os.environ, {"AET_BACKEND": "git-refs"}):
            rc = ship.cmd_ship(args)
        self.assertEqual(rc, 0)
        self.assertTrue(self._branch_exists("t1"))
        self.assertTrue(self._remote_branch_exists("t1"))


class TestShipCloseParser(unittest.TestCase):
    """Argument parsing for the close subcommand."""

    def test_close_subcommand_parses_task_id(self):
        """aet ship close accepts a task id as the first positional."""
        parser = ship.build_parser()
        args = parser.parse_args(["close", "t1"])
        self.assertEqual(args.command, "close")
        self.assertEqual(args.task_id, "t1")
