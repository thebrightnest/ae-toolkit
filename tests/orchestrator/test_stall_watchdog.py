"""Tests for the stall watchdog on event silence (nsr-05)."""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.xdist_group("orchestrator")

# Ensure the aet-work lib is on the path before importing telemetry.
# Load the orchestrator script (no .py extension) as a module.
_ORCHESTRATOR_BIN = Path(__file__).parents[2] / "src" / "aet" / "cli" / "orchestrator.py"
_orchestrator_loader = importlib.machinery.SourceFileLoader(
    "orchestrator", str(_ORCHESTRATOR_BIN)
)
_spec = importlib.util.spec_from_loader("orchestrator", _orchestrator_loader)
orchestrator = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(orchestrator)


def _init_git_repo(repo_root: str) -> None:
    """Initialize a git repo with a clean main branch tracking origin."""
    subprocess.run(["git", "init", "-q", repo_root], check=True)
    subprocess.run(
        ["git", "-C", repo_root, "config", "user.email", "test@example.com"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", repo_root, "config", "user.name", "Test User"],
        check=True,
    )
    Path(repo_root, "README.md").write_text("# test", encoding="utf-8")
    subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
    subprocess.run(
        ["git", "-C", repo_root, "commit", "-q", "-m", "initial"],
        check=True,
    )
    subprocess.run(["git", "-C", repo_root, "branch", "-M", "main"], check=True)
    subprocess.run(
        ["git", "-C", repo_root, "remote", "add", "origin", repo_root],
        check=True,
    )
    subprocess.run(
        ["git", "-C", repo_root, "update-ref", "refs/remotes/origin/main", "HEAD"],
        check=True,
    )


def _write_queue(repo_root: str, tasks: list[dict]) -> str:
    """Write a wrapper-format queue file and return its path."""
    queue_file = Path(repo_root, ".agents", "work-queue.json")
    queue_file.parent.mkdir(parents=True, exist_ok=True)
    queue_file.write_text(
        json.dumps(
            {
                "queue_updated_at": "2026-06-18T00:00:00Z",
                "source_prd": "docs/prds/demo-prd.md",
                "tasks": tasks,
            }
        ),
        encoding="utf-8",
    )
    return str(queue_file)


def _setup_plan_and_queue(repo_root: str, task_id: str) -> str:
    """Commit a plan file, update origin/main, and return the queue file path."""
    plan_file = os.path.join(repo_root, "docs", "plans", f"{task_id}.md")
    Path(plan_file).parent.mkdir(parents=True, exist_ok=True)
    Path(plan_file).write_text(
        f"---\nid: {task_id}\n---\n\n# Demo\n\n_Stage: plan-approved_\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
    subprocess.run(
        ["git", "-C", repo_root, "commit", "-q", "-m", "add plan"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", repo_root, "update-ref", "refs/remotes/origin/main", "HEAD"],
        check=True,
    )
    return _write_queue(
        repo_root,
        [
            {
                "id": task_id,
                "title": task_id,
                "plan_file": f"docs/plans/{task_id}.md",
                "blocked_by": [],
                "state": "ready",
            }
        ],
    )


def _write_silent_cli(repo_root: str) -> str:
    """Create a fake agent CLI that sleeps silently."""
    bin_dir = Path(repo_root) / "bin"
    bin_dir.mkdir()
    fake_cli = bin_dir / "kimi"
    fake_cli.write_text(
        "#!/usr/bin/env bash\n"
        "# ignore prompt flag and prompt\n"
        "exec python3 -c \"import time; time.sleep(600)\"\n",
        encoding="utf-8",
    )
    fake_cli.chmod(0o755)
    return str(fake_cli)


class TestStallWatchdog(unittest.TestCase):
    """Unit tests for the stdout-silence watchdog in _run_with_live_tee."""

    def test_silent_session_killed_after_stall_timeout(self):
        """A silent session is killed and classified as timeout (-9)."""
        with tempfile.TemporaryDirectory() as cwd:
            cmd = [sys.executable, "-c", "import time; time.sleep(600)"]
            start = time.monotonic()
            exit_code, _tail = orchestrator._run_with_live_tee(
                cmd, cwd, os.environ.copy(), stall_timeout=0.2
            )
            elapsed = time.monotonic() - start
            self.assertEqual(exit_code, -9)
            self.assertLess(elapsed, 5.0)

    def test_emitting_session_spared_past_stall_timeout(self):
        """A session that keeps emitting is not killed by the watchdog."""
        with tempfile.TemporaryDirectory() as cwd:
            script = (
                "import time, sys\n"
                "for i in range(10):\n"
                "    print(f'line {i}', flush=True)\n"
                "    time.sleep(0.05)\n"
            )
            cmd = [sys.executable, "-c", script]
            start = time.monotonic()
            exit_code, tail = orchestrator._run_with_live_tee(
                cmd, cwd, os.environ.copy(), stall_timeout=0.15
            )
            elapsed = time.monotonic() - start
            self.assertEqual(exit_code, 0)
            self.assertGreaterEqual(elapsed, 0.4)
            self.assertIn("line 9", tail)


class TestBatchTimeoutBackstop(unittest.TestCase):
    """Integration tests for stall and wall-clock kills through run_batch."""

    def _run_batch(self, args, adapter, timeout: float = 30):
        """Run run_batch in a thread; return (rc, stdout)."""
        result = {"rc": None, "out": ""}
        orchestrator._shutdown_requested = False

        def target():
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                result["rc"] = orchestrator.run_batch(args, adapter)
            result["out"] = buf.getvalue()

        thread = threading.Thread(target=target)
        thread.start()
        thread.join(timeout=timeout)
        if thread.is_alive():
            orchestrator._shutdown_requested = True
            thread.join(timeout=5)
            self.fail("run_batch did not finish within timeout")
        return result["rc"], result["out"]

    def test_silent_session_killed_by_wallclock_backstop(self):
        """Batch parent's wall-clock backstop kills a wedged silent child."""
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            task_id = "nsr-05-wallclock"
            fake_cli = _write_silent_cli(repo_root)
            queue_file = _setup_plan_and_queue(repo_root, task_id)
            adapter = orchestrator.resolve_cli_adapter(fake_cli)

            args = argparse.Namespace(
                queue_file=queue_file,
                plan_file=None,
                repo_root=repo_root,
                cli_bin=fake_cli,
                isolation="minimal",
                max_jobs=1,
                task_timeout=1,
                stall_timeout=999,
                heartbeat_interval=999,
                on_failure="continue",
            )

            with patch.object(
                orchestrator, "verify_branch_has_commits", return_value=(True, "")
            ):
                rc, out = self._run_batch(args, adapter, timeout=15)

            self.assertEqual(rc, 1)
            self.assertIn("timed out after 1s", out)

            queue = json.loads(Path(queue_file).read_text(encoding="utf-8"))["tasks"]
            self.assertEqual(queue[0]["state"], "failed")

    def test_stall_kill_routes_through_finalize(self):
        """A stall kill inside the child orchestrator finalizes as failed."""
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            task_id = "nsr-05-stall"
            fake_cli = _write_silent_cli(repo_root)
            queue_file = _setup_plan_and_queue(repo_root, task_id)
            adapter = orchestrator.resolve_cli_adapter(fake_cli)

            args = argparse.Namespace(
                queue_file=queue_file,
                plan_file=None,
                repo_root=repo_root,
                cli_bin=fake_cli,
                isolation="minimal",
                max_jobs=1,
                task_timeout=999,
                stall_timeout=1,
                heartbeat_interval=999,
                on_failure="continue",
            )

            with patch.object(
                orchestrator, "verify_branch_has_commits", return_value=(True, "")
            ):
                rc, out = self._run_batch(args, adapter, timeout=30)

            self.assertEqual(rc, 1)
            self.assertIn("failed", out)

            queue = json.loads(Path(queue_file).read_text(encoding="utf-8"))["tasks"]
            self.assertEqual(queue[0]["state"], "failed")


if __name__ == "__main__":
    unittest.main()
