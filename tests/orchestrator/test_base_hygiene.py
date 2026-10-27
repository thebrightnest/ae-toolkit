"""Run-start hygiene for a project with no `origin` remote (R-4)."""

from __future__ import annotations

import contextlib
import importlib
import io
import subprocess
import tempfile
import unittest
from pathlib import Path

import pytest

_ORCHESTRATOR_BIN = Path(__file__).parents[2] / "src" / "aet" / "cli" / "orchestrator.py"
_orchestrator_loader = importlib.machinery.SourceFileLoader("orchestrator", str(_ORCHESTRATOR_BIN))
_spec = importlib.util.spec_from_loader("orchestrator", _orchestrator_loader)
orchestrator = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(orchestrator)

pytestmark = pytest.mark.xdist_group("git-repo")


def _init_repo_without_remote(repo_root: str) -> None:
    """Initialize a repo on ``main`` with one commit and no remote."""
    subprocess.run(["git", "init", "-q", "-b", "main", repo_root], check=True)
    subprocess.run(
        ["git", "-C", repo_root, "config", "user.email", "test@example.com"], check=True
    )
    subprocess.run(["git", "-C", repo_root, "config", "user.name", "Test User"], check=True)
    Path(repo_root, "README.md").write_text("# test", encoding="utf-8")
    subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
    subprocess.run(["git", "-C", repo_root, "commit", "-q", "-m", "init"], check=True)


def _enforce(repo_root: str, branch: str = "main") -> tuple[bool, str]:
    """Run the run-start hygiene check and capture what it prints."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        ok = orchestrator.enforce_base_hygiene(repo_root, branch, branch)
    return ok, out.getvalue()


class TestNoRemoteHygiene(unittest.TestCase):
    def test_no_remote_root_on_integration_branch_halts(self):
        """A flush could not move the checked-out branch without writing the root."""
        with tempfile.TemporaryDirectory() as repo_root:
            _init_repo_without_remote(repo_root)

            ok, output = _enforce(repo_root)

            self.assertFalse(ok)
            self.assertIn("main", output)
            self.assertIn("check out another branch", output)
            self.assertIn("add a remote", output)

    def test_no_remote_root_on_other_branch_proceeds(self):
        """The flush moves an unchecked-out branch with `update-ref`."""
        with tempfile.TemporaryDirectory() as repo_root:
            _init_repo_without_remote(repo_root)
            subprocess.run(["git", "-C", repo_root, "checkout", "-q", "-b", "work"], check=True)

            ok, output = _enforce(repo_root)

            self.assertTrue(ok, output)

    def test_remote_root_on_integration_branch_proceeds(self):
        """With a remote, the flush pushes to origin and leaves the root alone."""
        with tempfile.TemporaryDirectory() as repo_root:
            _init_repo_without_remote(repo_root)
            subprocess.run(
                ["git", "-C", repo_root, "remote", "add", "origin", repo_root], check=True
            )

            ok, output = _enforce(repo_root)

            self.assertTrue(ok, output)


if __name__ == "__main__":
    unittest.main()
