"""Tests for derive_status in-progress session evidence requirement (ADR-072 / eop-02).

A branch sitting at its base commit has authored nothing and is not evidence of
active work. derive_status requires branch_has_own_commits before returning
in_progress; otherwise, the task derives as ready or blocked on its blockers.
"""

import importlib.machinery
import importlib.util
import io
import json
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from tests.state._helpers import add_bare_origin, init_git_repo, seed_git_queue

_AET_STATE_PY = Path(__file__).parents[2] / "src" / "aet" / "cli" / "aet_state.py"

_spec = importlib.util.spec_from_loader(
    "aet_state", importlib.machinery.SourceFileLoader("aet_state", str(_AET_STATE_PY))
)

aet_state = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(aet_state)


def _git(root, *args):
    return subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=False
    )


class DeriveStatusRepo:
    """A test repository with base, zero-commit, open (with commits), and merged branches."""

    def __init__(self, root: Path):
        self.root = root
        init_git_repo(root)
        add_bare_origin(root)
        (root / "base.txt").write_text("base\n", encoding="utf-8")
        _git(root, "add", "base.txt")
        _git(root, "commit", "-qm", "initial base commit")
        _git(root, "branch", "-M", "main")
        _git(root, "push", "-q", "-u", "origin", "main")

        self.base = _git(root, "rev-parse", "main").stdout.strip()

        # Zero-commit branch (sitting at base)
        _git(root, "branch", "zero-commit-task", "main")

        # Open branch with own work
        _git(root, "checkout", "-q", "-b", "in-progress-task", "main")
        (root / "work.txt").write_text("work in progress\n", encoding="utf-8")
        _git(root, "add", "work.txt")
        _git(root, "commit", "-qm", "authored work")
        _git(root, "checkout", "-q", "main")

        # Merged branch
        _git(root, "checkout", "-q", "-b", "merged-task", "main")
        (root / "merged.txt").write_text("merged work\n", encoding="utf-8")
        _git(root, "add", "merged.txt")
        _git(root, "commit", "-qm", "merged work commit")
        self.merged_tip = _git(root, "rev-parse", "merged-task").stdout.strip()
        _git(root, "checkout", "-q", "main")
        _git(root, "merge", "-q", "--no-ff", "-m", "merge task", "merged-task")
        _git(root, "push", "-q", "origin", "main")


class TestDeriveStatusSessionEvidence(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = DeriveStatusRepo(Path(self._tmp.name) / "repo")
        self.cwd = str(self.repo.root)

    def _derive(self, task, blocker_fn=None):
        task.setdefault("spec", {})
        return aet_state.derive_status(
            task, blocker_status_fn=blocker_fn, cwd=self.cwd, trunk_branch="main"
        )

    def test_zero_commit_branch_without_blockers_derives_ready(self):
        """A branch sitting at its base commit with no blockers derives ready, not in_progress."""
        task = {
            "id": "t-zero",
            "branch": "zero-commit-task",
            "base_commit": self.repo.base,
        }
        derived = self._derive(task)
        self.assertTrue(derived["branch_exists"])
        self.assertFalse(derived["on_trunk"])
        self.assertEqual(derived["derived_status"], "ready")

    def test_zero_commit_branch_with_active_blocker_derives_blocked(self):
        """A branch sitting at its base commit with an unfinished blocker derives blocked."""
        task = {
            "id": "t-zero-blocked",
            "branch": "zero-commit-task",
            "base_commit": self.repo.base,
            "blocked_by": ["t-other"],
        }

        def blocker_fn(b):
            return "in_progress" if b == "t-other" else "unknown"

        derived = self._derive(task, blocker_fn=blocker_fn)
        self.assertEqual(derived["derived_status"], "blocked")

    def test_zero_commit_branch_with_terminal_blocker_derives_ready(self):
        """A branch sitting at base with all blockers terminal derives ready."""
        task = {
            "id": "t-zero-unblocked",
            "branch": "zero-commit-task",
            "base_commit": self.repo.base,
            "blocked_by": ["t-other"],
        }

        def blocker_fn(b):
            return "merged" if b == "t-other" else "unknown"

        derived = self._derive(task, blocker_fn=blocker_fn)
        self.assertEqual(derived["derived_status"], "ready")

    def test_branch_with_own_commits_derives_in_progress(self):
        """A branch that has moved past its base commit derives in_progress."""
        task = {
            "id": "t-progress",
            "branch": "in-progress-task",
            "base_commit": self.repo.base,
        }
        derived = self._derive(task)
        self.assertTrue(derived["branch_exists"])
        self.assertEqual(derived["derived_status"], "in_progress")

    def test_task_with_no_branch_derives_ready_or_blocked(self):
        """A task without a branch derives ready (no blockers) or blocked (with blockers)."""
        task_ready = {"id": "t-nobranch"}
        derived_ready = self._derive(task_ready)
        self.assertFalse(derived_ready["branch_exists"])
        self.assertEqual(derived_ready["derived_status"], "ready")

        task_blocked = {"id": "t-nobranch-blk", "blocked_by": ["b1"]}

        def blocker_fn(b):
            return "in_progress"

        derived_blocked = self._derive(task_blocked, blocker_fn=blocker_fn)
        self.assertEqual(derived_blocked["derived_status"], "blocked")

    def test_merged_task_derives_merged(self):
        """A branch merged into origin/main still derives merged."""
        task = {
            "id": "t-merged",
            "branch": "merged-task",
            "base_commit": self.repo.base,
        }
        derived = self._derive(task)
        self.assertTrue(derived["on_trunk"])
        self.assertEqual(derived["derived_status"], "merged")

    def test_audit_reports_no_discrepancy_for_zero_commit_branch(self):
        """aet state audit reports no discrepancy for a task whose branch carries no commits."""
        queue_path, _ = seed_git_queue(
            self.repo.root,
            [
                {
                    "id": "t-zero",
                    "state": "ready",
                    "branch": "zero-commit-task",
                    "base_commit": self.repo.base,
                    "spec": {"frontmatter": {"id": "t-zero", "size": "S"}, "tasks": []},
                }
            ],
        )

        class Args:
            queue = str(queue_path)
            json = True
            all = False

        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = aet_state.cmd_audit(Args())

        self.assertEqual(rc, 0)
        report = json.loads(buf.getvalue())
        self.assertEqual(report.get("discrepancies", []), [])


if __name__ == "__main__":
    unittest.main()
