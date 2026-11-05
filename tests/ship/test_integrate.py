"""Integration tests for autonomous monolithic commit remediation in aet.integrate (R-5)."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pytest

from aet import validation
from aet.backends import create_backend
from aet.integrate import (
    integrate,
    parse_task_file_mappings,
)
from aet.worktree import create_worktree

pytestmark = pytest.mark.xdist_group("git-repo")


def _init_git_repo(repo_root: str, origin_root: str) -> None:
    """Initialize a git repo with main and a bare origin remote."""
    subprocess.run(["git", "init", "--bare", "-q", origin_root], check=True)
    subprocess.run(["git", "init", "-q", repo_root], check=True)
    subprocess.run(["git", "-C", repo_root, "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", repo_root, "config", "user.name", "Test User"], check=True)
    Path(repo_root, "README.md").write_text("# test", encoding="utf-8")
    subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
    subprocess.run(["git", "-C", repo_root, "commit", "-q", "-m", "initial"], check=True)
    subprocess.run(["git", "-C", repo_root, "branch", "-M", "main"], check=True)
    subprocess.run(["git", "-C", repo_root, "remote", "add", "origin", origin_root], check=True)
    subprocess.run(["git", "-C", repo_root, "push", "-q", "-u", "origin", "main"], check=True)
    subprocess.run(
        ["git", "-C", repo_root, "update-ref", "refs/remotes/origin/main", "HEAD"],
        check=True,
    )


def _create_integration_branch(repo_root: str, name: str = "epic-01") -> None:
    subprocess.run(["git", "-C", repo_root, "checkout", "-q", "-b", name], check=True)
    subprocess.run(["git", "-C", repo_root, "push", "-q", "-u", "origin", name], check=True)
    subprocess.run(
        ["git", "-C", repo_root, "update-ref", f"refs/remotes/origin/{name}", "HEAD"],
        check=True,
    )
    subprocess.run(["git", "-C", repo_root, "checkout", "-q", "main"], check=True)


def _setup_repo_and_backend(repo_root: str, origin_root: str):
    _init_git_repo(repo_root, origin_root)
    agents_dir = Path(repo_root, ".agents")
    agents_dir.mkdir(parents=True, exist_ok=True)
    (agents_dir / "aet-config.json").write_text(
        json.dumps(
            {
                "trunk_branch": "main",
                "integration_branch": "epic-01",
                "integration_mode": "single-pr",
            }
        ),
        encoding="utf-8",
    )
    queue_file = str(agents_dir / "aet-queue")
    history_file = str(agents_dir / "work-history.jsonl")
    backend = create_backend(
        config_path=str(agents_dir / "aet-config.json"),
        queue_file=queue_file,
        history_file=history_file,
    )
    _create_integration_branch(repo_root, "epic-01")
    return backend, queue_file


def _add_files_commit(worktree_dir: str, files: dict[str, str], msg: str = "work") -> None:
    for filename, content in files.items():
        p = Path(worktree_dir, filename)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        subprocess.run(["git", "-C", worktree_dir, "add", filename], check=True)
    subprocess.run(["git", "-C", worktree_dir, "commit", "-q", "-m", msg], check=True)


class TestAutonomousMonolithicCommitRemediation(unittest.TestCase):
    """Test suite for autonomous remediation of monolithic commits (R-5)."""

    def test_parse_task_file_mappings_unambiguous_dict(self):
        spec = {
            "tasks": [
                {"title": "Task 1", "files": ["src/a.py"]},
                {"title": "Task 2", "files": ["src/b.py"]},
            ]
        }
        changed = ["src/a.py", "src/b.py"]
        groups = parse_task_file_mappings(spec, changed)
        self.assertIsNotNone(groups)
        self.assertEqual(len(groups), 2)
        self.assertEqual(groups[0], ("Task 1", ["src/a.py"]))
        self.assertEqual(groups[1], ("Task 2", ["src/b.py"]))

    def test_parse_task_file_mappings_unambiguous_markdown(self):
        spec = {
            "tasks": [
                "- [ ] 1. Implement feature in `src/a.py`",
                "- [ ] 2. Add test in `tests/test_b.py`",
            ]
        }
        changed = ["src/a.py", "tests/test_b.py"]
        groups = parse_task_file_mappings(spec, changed)
        self.assertIsNotNone(groups)
        self.assertEqual(len(groups), 2)
        self.assertEqual(groups[0][1], ["src/a.py"])
        self.assertEqual(groups[1][1], ["tests/test_b.py"])

    def test_parse_task_file_mappings_ambiguous_overlapping(self):
        spec = {
            "tasks": [
                {"title": "Task 1", "files": ["src/a.py", "src/common.py"]},
                {"title": "Task 2", "files": ["src/b.py", "src/common.py"]},
            ]
        }
        changed = ["src/a.py", "src/b.py", "src/common.py"]
        groups = parse_task_file_mappings(spec, changed)
        self.assertIsNone(groups)

    def test_parse_task_file_mappings_ambiguous_unmapped_file(self):
        spec = {
            "tasks": [
                {"title": "Task 1", "files": ["src/a.py"]},
                {"title": "Task 2", "files": ["src/b.py"]},
            ]
        }
        changed = ["src/a.py", "src/b.py", "src/extra.py"]
        groups = parse_task_file_mappings(spec, changed)
        self.assertIsNone(groups)

    def test_unambiguous_monolithic_commit_is_auto_split_and_integrated(self):
        """Assert unambiguous monolithic commit is auto-split and integrated."""
        with tempfile.TemporaryDirectory() as repo_root, tempfile.TemporaryDirectory() as origin_root:
            backend, queue_file = _setup_repo_and_backend(repo_root, origin_root)
            task_id = "task-auto-split"
            task_spec = {
                "tasks": [
                    {"title": "Add component alpha", "files": ["alpha.py"]},
                    {"title": "Add component beta", "files": ["beta.py"]},
                ],
            }
            backend.save([{"id": task_id, "state": "in_progress", "branch": task_id, "spec": task_spec}])

            wt = create_worktree(repo_root, task_id, base_branch="origin/epic-01")
            _add_files_commit(
                wt,
                {"alpha.py": "alpha content\n", "beta.py": "beta content\n"},
                "monolithic commit doing both tasks",
            )

            skip_check = validation.CheckResult("SKIP", None, True, "")
            with patch("aet.validation.pre_integration_check", return_value=skip_check):
                with patch("aet.gate.check_task_evidence", return_value=(True, [])):
                    res = integrate(
                        repo_root=repo_root,
                        task=task_id,
                        worktree_dir=wt,
                        backend=backend,
                        integration_branch="epic-01",
                    )

            self.assertEqual(res.status, "staged")
            self.assertTrue(res.ok)

            data = backend.load()
            task_rec = next(t for t in data["queue"] if t["id"] == task_id)
            self.assertEqual(task_rec["state"], "awaiting_merge")
            self.assertIn("train", task_rec)
            self.assertEqual(task_rec["train"]["branch"], "epic-01")

    def test_ambiguous_monolithic_commit_still_refuses(self):
        """Ambiguous monolithic commit cannot auto-split and remains guard_refused."""
        with tempfile.TemporaryDirectory() as repo_root, tempfile.TemporaryDirectory() as origin_root:
            backend, queue_file = _setup_repo_and_backend(repo_root, origin_root)
            task_id = "task-ambiguous"
            task_spec = {
                "tasks": ["- [ ] Task 1 without files", "- [ ] Task 2 without files"],
            }
            backend.save([{"id": task_id, "state": "in_progress", "branch": task_id, "spec": task_spec}])

            wt = create_worktree(repo_root, task_id, base_branch="origin/epic-01")
            _add_files_commit(
                wt,
                {"alpha.py": "alpha\n", "beta.py": "beta\n"},
                "monolithic commit",
            )

            skip_check = validation.CheckResult("SKIP", None, True, "")
            with patch("aet.validation.pre_integration_check", return_value=skip_check):
                with patch("aet.gate.check_task_evidence", return_value=(True, [])):
                    res = integrate(
                        repo_root=repo_root,
                        task=task_id,
                        worktree_dir=wt,
                        backend=backend,
                        integration_branch="epic-01",
                    )

            self.assertEqual(res.status, "guard_refused")
            self.assertFalse(res.ok)
