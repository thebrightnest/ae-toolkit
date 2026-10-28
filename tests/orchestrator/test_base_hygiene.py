"""Run-start hygiene for a project with no `origin` remote (R-4)."""

from __future__ import annotations

import argparse
import contextlib
import importlib
import io
import os
import subprocess
import tempfile
import unittest
import unittest.mock
from pathlib import Path

import pytest

from tests.orchestrator._helpers import init_epic_repo, install_fake_agent, load_queue, write_queue

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


class TestPerBranchHygiene(unittest.TestCase):
    def test_dirty_epic_branch_skips_only_its_tasks(self):
        """R-5: a dirty feat/a skips task A; task B on feat/b completes."""
        with (
            tempfile.TemporaryDirectory() as repo_root,
            tempfile.TemporaryDirectory() as origin_root,
            tempfile.TemporaryDirectory() as bin_root,
        ):
            plans = init_epic_repo(
                repo_root, origin_root, {"task-a": "a-prd", "task-b": "b-prd"}
            )
            subprocess.run(["git", "-C", repo_root, "push", "-q", "origin", "main:feat/a"], check=True)
            subprocess.run(["git", "-C", repo_root, "fetch", "-q", "origin"], check=True)
            subprocess.run(["git", "-C", repo_root, "branch", "feat/a", "origin/feat/a"], check=True)
            subprocess.run(["git", "-C", repo_root, "checkout", "-q", "feat/a"], check=True)
            Path(repo_root, "unpushed.py").write_text("x = 1\n", encoding="utf-8")
            subprocess.run(["git", "-C", repo_root, "add", "unpushed.py"], check=True)
            subprocess.run(["git", "-C", repo_root, "commit", "-q", "-m", "unpushed"], check=True)
            subprocess.run(["git", "-C", repo_root, "checkout", "-q", "main"], check=True)

            queue_file = write_queue(
                repo_root,
                [
                    {"id": "task-a", "state": "ready", "plan_file": plans["task-a"]},
                    {"id": "task-b", "state": "ready", "plan_file": plans["task-b"]},
                ],
            )
            bin_dir, adapter = install_fake_agent(bin_root)
            args = argparse.Namespace(
                queue_file=queue_file,
                repo_root=repo_root,
                base=None,
                isolation="standard",
                max_jobs=2,
                task_timeout=600,
                heartbeat_interval=60,
                on_failure="continue",
                run_id="run-hygiene-skip",
            )

            out = io.StringIO()
            env = {"PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}
            with unittest.mock.patch.dict(os.environ, env), contextlib.redirect_stdout(out):
                exit_code = orchestrator.run_batch(args, adapter)

            output = out.getvalue()
            states = {t["id"]: t["state"] for t in load_queue(queue_file)}
            self.assertNotEqual(exit_code, 0, output)
            self.assertEqual(states.get("task-a"), "ready", output)
            self.assertNotIn("task-b", states, output)
            self.assertIn("Skipping task-a", output)
            self.assertIn("Local feat/a is ahead of origin/feat/a", output)
            summary = output.split("🏁 Orchestrator finished.")[1]
            self.assertIn("Remedy: push feat/a or reset it to origin/feat/a", summary)
            log = subprocess.run(
                ["git", "-C", repo_root, "log", "origin/feat/b", "--format=%s"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout
            self.assertIn("Integrate task-b", log)


if __name__ == "__main__":
    unittest.main()
