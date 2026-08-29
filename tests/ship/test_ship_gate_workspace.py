"""Tests for aet-ship gate workspace resolution and checkout independence.

Validates that `aet ship gate`, `aet ship open`, and `aet ship merge` always gate
the feature branch's workspace rather than the ambient checkout (HEAD/cwd), and
that a red feature branch is refused even when invoked from a green trunk checkout.
"""

from __future__ import annotations

import argparse
import importlib.machinery
import importlib.util
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from aet.backends.git_refs_backend import GitRefsBackend

_SHIP_PY = Path(__file__).parents[2] / "src" / "aet" / "cli" / "ship.py"
_spec = importlib.util.spec_from_loader(
    "aet_ship", importlib.machinery.SourceFileLoader("aet_ship", str(_SHIP_PY))
)
ship = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ship)


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
    _git(path, "symbolic-ref", "HEAD", "refs/heads/main")
    _git(path, "config", "user.email", "test@example.com")
    _git(path, "config", "user.name", "Test User")
    (path / ".agents").mkdir(parents=True, exist_ok=True)
    (path / "README.md").write_text("hello\n", encoding="utf-8")
    _git(path, "add", ".")
    _git(path, "commit", "-q", "-m", "initial commit on main")
    _git(path, "remote", "add", "origin", str(path))
    _git(path, "push", "-u", "origin", "main", check=False)
    return path


def _save_task_record(repo: Path, task_id: str, branch: str | None = None) -> None:
    queue_file = repo / ".agents" / "aet-queue"
    history_file = repo / ".agents" / "work-history.jsonl"
    backend = GitRefsBackend(
        queue_file=str(queue_file),
        history_file=str(history_file),
    )
    spec = {
        "frontmatter": {"id": task_id},
        "title": f"Plan {task_id}",
        "body": "",
        "tasks": ["- [x] task one"],
    }
    backend.save(
        [
            {
                "id": task_id,
                "state": "awaiting_merge",
                "stage": "qa-complete",
                "branch": branch or task_id,
                "plan_file": f"docs/plans/{task_id}.md",
                "spec": spec,
            }
        ]
    )


class TestShipGateWorkspace(unittest.TestCase):
    """Tests that gate operations inspect and validate the feature branch workspace."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.repo = _init_repo(Path(self.tmpdir.name) / "repo")
        self.cwd = os.getcwd()
        self.addCleanup(os.chdir, self.cwd)
        os.chdir(self.repo)

    def test_gate_runs_against_feature_worktree_from_main(self):
        """When invoked from main, gate runs in the feature branch's worktree."""
        task_id = "feat-red"
        # Create a linked worktree for feat-red
        worktree_dir = self.repo / ".worktrees" / task_id
        worktree_dir.parent.mkdir(parents=True, exist_ok=True)
        _git(self.repo, "worktree", "add", "-b", task_id, str(worktree_dir), "main")
        _save_task_record(self.repo, task_id)

        # Make main have a passing test script, but feat-red have a failing one
        (self.repo / "test.sh").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        os.chmod(self.repo / "test.sh", 0o755)

        (worktree_dir / "test.sh").write_text("#!/bin/sh\necho 'FAIL IN FEATURE' >&2\nexit 1\n", encoding="utf-8")
        os.chmod(worktree_dir / "test.sh", 0o755)

        _git(self.repo, "add", "test.sh")
        _git(self.repo, "commit", "-q", "-m", "add test script on main")
        _git(worktree_dir, "add", "test.sh")
        _git(worktree_dir, "commit", "-q", "-m", "add failing test on feature")

        env = {
            "AET_SHIP_TEST_CMD": "./test.sh",
            "AET_BACKEND": "git-refs",
        }
        with patch.dict(os.environ, env):
            rc = ship.cmd_gate(argparse.Namespace(plan=task_id, base=None, dry_run=False))

        # Must fail because the feature branch is red, even though cwd (main) is green
        self.assertNotEqual(rc, 0)

    def test_gate_names_validated_branch_on_success(self):
        """When gate passes, output and result message name the validated branch."""
        task_id = "feat-green"
        worktree_dir = self.repo / ".worktrees" / task_id
        worktree_dir.parent.mkdir(parents=True, exist_ok=True)
        _git(self.repo, "worktree", "add", "-b", task_id, str(worktree_dir), "main")
        _save_task_record(self.repo, task_id)

        (worktree_dir / "test.sh").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        os.chmod(worktree_dir / "test.sh", 0o755)
        _git(worktree_dir, "add", "test.sh")
        _git(worktree_dir, "commit", "-q", "-m", "add test on feature")

        env = {
            "AET_SHIP_TEST_CMD": "./test.sh",
            "AET_BACKEND": "git-refs",
        }
        with patch.dict(os.environ, env):
            args = argparse.Namespace(plan=task_id, base=None, dry_run=False)
            rc = ship._resolve_ship_task(args)
            self.assertIsNone(rc)
            result = ship._run_gate(args)

        self.assertTrue(result.ok)
        self.assertIn(task_id, result.message)

    def test_gate_creates_temp_worktree_when_no_worktree_exists(self):
        """When the branch exists without a worktree, a temporary worktree is created and cleaned up."""
        task_id = "feat-temp"
        _git(self.repo, "branch", task_id, "main")
        _save_task_record(self.repo, task_id)

        env = {
            "AET_SHIP_TEST_CMD": "true",
            "AET_BACKEND": "git-refs",
        }
        with patch.dict(os.environ, env):
            args = argparse.Namespace(plan=task_id, base=None, dry_run=False)
            ship._resolve_ship_task(args)
            result = ship._run_gate(args)

        self.assertTrue(result.ok)
        # Check that no temp worktree was left behind
        worktrees_out = _git(self.repo, "worktree", "list", "--porcelain").stdout
        self.assertNotIn(".gate-", worktrees_out)

    def test_gate_fails_closed_when_branch_cannot_be_resolved(self):
        """Refuse with diagnostic when no feature branch/workspace exists."""
        task_id = "feat-unresolvable"
        _save_task_record(self.repo, task_id)

        args = argparse.Namespace(plan=task_id, base=None, dry_run=False)
        ship._resolve_ship_task(args)
        result = ship._run_gate(args)

        self.assertFalse(result.ok)
        self.assertIn("Cannot resolve", result.message)

    def test_merge_refuses_red_feature_from_green_main(self):
        """`aet ship merge` from main refuses a red feature branch at the gate."""
        task_id = "feat-merge-red"
        worktree_dir = self.repo / ".worktrees" / task_id
        worktree_dir.parent.mkdir(parents=True, exist_ok=True)
        _git(self.repo, "worktree", "add", "-b", task_id, str(worktree_dir), "main")
        _save_task_record(self.repo, task_id)

        (worktree_dir / "test.sh").write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        os.chmod(worktree_dir / "test.sh", 0o755)
        _git(worktree_dir, "add", "test.sh")
        _git(worktree_dir, "commit", "-q", "-m", "failing commit")

        env = {
            "AET_SHIP_TEST_CMD": "./test.sh",
            "AET_BACKEND": "git-refs",
        }
        with patch.dict(os.environ, env):
            rc = ship.cmd_merge(argparse.Namespace(plan=task_id, branch="main", dry_run=False))

        self.assertNotEqual(rc, 0)
        # Main should not have the commit
        log = _git(self.repo, "log", "--oneline", "main").stdout
        self.assertNotIn("failing commit", log)


if __name__ == "__main__":
    unittest.main()
