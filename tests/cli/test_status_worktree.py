"""`aet status` resolves recorded worktree paths against the repo root.

Regression test: worktree paths are stored relative to the repo root
(``.worktrees/<task-id>``), so testing them against the process working
directory reported every worktree as stale whenever status was run from
anywhere but the root — including from inside a worktree.
"""

import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from aet.cli import status
from tests.state._helpers import init_git_repo, seed_git_queue


class TestStatusWorktreeResolution(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo_root = Path(self._tmp.name) / "repo"
        init_git_repo(self.repo_root)

        self.worktree_rel = ".worktrees/t1"
        (self.repo_root / self.worktree_rel).mkdir(parents=True)

        self.queue_path, self.history_path = seed_git_queue(
            self.repo_root,
            [
                {
                    "id": "t1",
                    "state": "in_progress",
                    "title": "task one",
                    "branch": "t1",
                    "worktree": self.worktree_rel,
                }
            ],
        )
        self._cwd = os.getcwd()
        self.addCleanup(os.chdir, self._cwd)

    def _status_output(self) -> str:
        buf = io.StringIO()
        with redirect_stdout(buf):
            status._run(
                str(self.queue_path),
                str(self.history_path),
                self.repo_root / "docs" / "plans",
                False,
            )
        return buf.getvalue()

    def test_no_stale_warning_from_repo_root(self):
        os.chdir(self.repo_root)
        self.assertIn("All registered worktrees are present.", self._status_output())

    def test_no_stale_warning_from_inside_a_worktree(self):
        """The reported defect: an existing worktree read as stale."""
        os.chdir(self.repo_root / self.worktree_rel)
        output = self._status_output()
        self.assertNotIn("Stale worktree", output)
        self.assertIn("All registered worktrees are present.", output)

    def test_genuinely_missing_worktree_is_still_reported(self):
        """The signal must survive the fix."""
        import shutil

        shutil.rmtree(self.repo_root / self.worktree_rel)
        os.chdir(self.repo_root)
        output = self._status_output()
        self.assertIn("Stale worktree", output)
        self.assertIn("t1", output)


if __name__ == "__main__":
    unittest.main()
