"""Regression tests for osd-01: why a SIGKILLed session does not always fail.

The rehearsal showed a stall task ending ``failed`` in ~5/6 runs and ``ready``
in ~1/6.  The root cause is a race between the child orchestrator's stall
watchdog (which records a ``TIMEOUT`` signature) and the batch parent's wall-
clock backstop (which kills the child orchestrator before it can record one).

These tests exercise both extremes deterministically.
"""

from __future__ import annotations

import argparse
import importlib.util
import io
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import pytest

from aet import telemetry
from aet.cli_adapter import CLIAdapter
from tests.orchestrator._helpers import load_queue, write_queue

pytestmark = pytest.mark.xdist_group("process-group")

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


def _write_queue(
    repo_root: str,
    task_id: str,
    state: str = "ready",
    failure_signatures: list[dict] | None = None,
) -> str:
    """Seed a single-task git-refs queue and return its path."""
    return write_queue(
        repo_root,
        [
            {
                "id": task_id,
                "title": task_id,
                "plan_file": f"docs/plans/{task_id}.md",
                "blocked_by": [],
                "state": state,
                "failure_signatures": failure_signatures or [],
            }
        ],
    )


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
    return _write_queue(repo_root, task_id)


def _write_triage_aware_cli(repo_root: str) -> str:
    """Create a fake agent CLI that returns a requeue verdict for triage prompts."""
    bin_dir = Path(repo_root) / "bin"
    bin_dir.mkdir(exist_ok=True)
    fake_cli = bin_dir / "kimi"
    fake_cli.write_text(
        "#!/usr/bin/env python3\n"
        "import os\n"
        "import signal\n"
        "import sys\n"
        "import time\n"
        "\n"
        "prompt = sys.argv[-1] if sys.argv else ''\n"
        'if "Failure class" in prompt:\n'
        '    print(\'{"class":"timeout","action":"requeue"}\')\n'
        "    sys.exit(0)\n"
        "\n"
        "shutdown = False\n"
        "\n"
        "def _handler(_signum, _frame):\n"
        "    global shutdown\n"
        "    shutdown = True\n"
        "\n"
        "signal.signal(signal.SIGTERM, _handler)\n"
        "signal.signal(signal.SIGINT, _handler)\n"
        "deadline = time.monotonic() + 600\n"
        "while not shutdown and time.monotonic() < deadline:\n"
        "    time.sleep(0.05)\n",
        encoding="utf-8",
    )
    fake_cli.chmod(0o755)
    return str(fake_cli)


def _custom_adapter(fake_cli: str, stall_timeout: float) -> CLIAdapter:
    """Return a CLIAdapter that kills silently after ``stall_timeout``."""
    return CLIAdapter(
        name="test",
        bin=fake_cli,
        prompt_flag="-p",
        workdir_flag=None,
        headless_flag=None,
        stall_timeout=stall_timeout,
        wall_backstop=10.0,
    )


class TestInternalStallRecordsTimeout(unittest.TestCase):
    """When the child's own stall watchdog fires, it records TIMEOUT."""

    def test_internal_stall_records_timeout_signature(self):
        """A session killed by its own watchdog records a TIMEOUT signature."""
        with tempfile.TemporaryDirectory() as repo_root:
            fake_cli = _write_triage_aware_cli(repo_root)
            queue_file = _write_queue(repo_root, "osd-internal")
            backend = orchestrator.create_backend(queue_file=queue_file)
            task = {
                "id": "osd-internal",
                "plan_file": "docs/plans/osd-internal.md",
                "state": "in_progress",
            }
            adapter = _custom_adapter(fake_cli, stall_timeout=0.2)

            exit_code, _usage, _session_dir, _output = orchestrator.run_stage(
                adapter,
                repo_root=repo_root,
                plan_file="docs/plans/osd-internal.md",
                worktree_dir=repo_root,
                skills=["aet-tdd", "aet-implement"],
                current_stage="plan-approved",
                next_stage="implemented",
                task_id="osd-internal",
                task=task,
                backend=backend,
                stall_timeout=0.2,
            )

            self.assertEqual(exit_code, -9)
            self.assertTrue(task.get("failure_signatures"))
            last = task["failure_signatures"][-1]
            self.assertEqual(last.get("class"), "timeout")


class TestExternalKillBeforeStall(unittest.TestCase):
    """An external SIGKILL before the watchdog fires still returns -9."""

    def test_external_sigkill_before_stall_returns_same_exit_code(self):
        """Same raw exit code, but the child has no chance to record TIMEOUT."""
        with tempfile.TemporaryDirectory() as cwd:
            pid_file = Path(cwd) / "pid.txt"
            script = (
                "from pathlib import Path\n"
                "import os, sys, time\n"
                f"Path('{pid_file}').write_text(str(os.getpid()))\n"
                "time.sleep(600)\n"
            )
            cmd = [sys.executable, "-c", script]
            result: dict[str, object] = {"exit_code": None}

            def target():
                result["exit_code"], _ = orchestrator._run_with_live_tee(
                    cmd, cwd, os.environ.copy(), stall_timeout=10.0
                )

            thread = threading.Thread(target=target)
            thread.start()
            # Wait for the child to start, then kill its process group.
            for _ in range(50):
                if pid_file.exists():
                    break
                time.sleep(0.01)
            self.assertTrue(pid_file.exists(), "child process never started")
            pid = int(pid_file.read_text(encoding="utf-8"))
            time.sleep(0.1)
            try:
                os.killpg(os.getpgid(pid), signal.SIGKILL)
            except ProcessLookupError:
                pass
            thread.join(timeout=5)
            self.assertFalse(thread.is_alive())
            self.assertEqual(result["exit_code"], -9)


class TestFinalizeSignalExitAuthoritative(unittest.TestCase):
    """A signal-killed child is classified as timeout by the parent."""

    def test_finalize_records_timeout_signature_when_child_could_not(self):
        """The batch parent sees ret=-9 with no TIMEOUT entry and appends one."""
        with tempfile.TemporaryDirectory() as repo_root:
            task_id = "osd-parent-wins"
            queue_file = _write_queue(
                repo_root,
                task_id,
                state="in_progress",
                failure_signatures=[],
            )
            backend = orchestrator.create_backend(queue_file=queue_file)

            deltas = orchestrator._finalize_task(
                backend,
                queue_file,
                task_id,
                ret=-9,
                repo_root=repo_root,
                adapter=None,
                on_failure="triage",
            )

            self.assertEqual(deltas, {"successes": 0, "failures": 1, "stop_spawn": False})
            queue = load_queue(queue_file)
            self.assertEqual(queue[0]["state"], "failed")
            timeout_sigs = [
                entry
                for entry in queue[0].get("failure_signatures", [])
                if entry.get("class") == "timeout"
            ]
            self.assertEqual(len(timeout_sigs), 1)

    def test_finalize_appends_only_one_timeout_signature(self):
        """A signal-killed session ends with exactly one TIMEOUT signature."""
        with tempfile.TemporaryDirectory() as repo_root:
            task_id = "osd-parent-wins"
            queue_file = _write_queue(
                repo_root,
                task_id,
                state="in_progress",
                failure_signatures=[{"class": "timeout", "signature": "abc"}],
            )
            backend = orchestrator.create_backend(queue_file=queue_file)

            orchestrator._finalize_task(
                backend,
                queue_file,
                task_id,
                ret=-9,
                repo_root=repo_root,
                adapter=None,
                on_failure="triage",
            )

            queue = load_queue(queue_file)
            timeout_sigs = [
                entry
                for entry in queue[0].get("failure_signatures", [])
                if entry.get("class") == "timeout"
            ]
            self.assertEqual(len(timeout_sigs), 1)

    def test_finalize_treats_any_signal_death_as_timeout(self):
        """Any negative return code (e.g. SIGTERM) is authoritative for timeout."""
        with tempfile.TemporaryDirectory() as repo_root:
            task_id = "osd-parent-wins"
            queue_file = _write_queue(
                repo_root,
                task_id,
                state="in_progress",
                failure_signatures=[],
            )
            backend = orchestrator.create_backend(queue_file=queue_file)

            deltas = orchestrator._finalize_task(
                backend,
                queue_file,
                task_id,
                ret=-15,
                repo_root=repo_root,
                adapter=None,
                on_failure="triage",
            )

            self.assertEqual(deltas, {"successes": 0, "failures": 1, "stop_spawn": False})
            queue = load_queue(queue_file)
            self.assertEqual(queue[0]["state"], "failed")
            timeout_sigs = [
                entry
                for entry in queue[0].get("failure_signatures", [])
                if entry.get("class") == "timeout"
            ]
            self.assertEqual(len(timeout_sigs), 1)


def _write_sleeping_cli(repo_root: str, started_file: str) -> str:
    """Create a fake agent CLI that records its startup and sleeps."""
    bin_dir = Path(repo_root) / "bin"
    bin_dir.mkdir(exist_ok=True)
    fake_cli = bin_dir / "claude"
    fake_cli.write_text(
        "#!/usr/bin/env python3\n"
        "import os\n"
        "import signal\n"
        "import sys\n"
        "import time\n"
        "from pathlib import Path\n"
        f"Path('{started_file}').write_text(str(os.getpid()))\n"
        "shutdown = False\n"
        "def _handler(_signum, _frame):\n"
        "    global shutdown\n"
        "    shutdown = True\n"
        "signal.signal(signal.SIGTERM, _handler)\n"
        "signal.signal(signal.SIGINT, _handler)\n"
        "while not shutdown:\n"
        "    time.sleep(0.05)\n"
        "sys.exit(0)\n",
        encoding="utf-8",
    )
    fake_cli.chmod(0o755)
    return str(fake_cli)


class TestFinalizeOperatorStopCanceled(unittest.TestCase):
    """When canceled=True is passed, _finalize_task returns task to ready without signatures."""

    def test_finalize_canceled_leaves_task_ready_no_signature(self):
        with tempfile.TemporaryDirectory() as repo_root:
            task_id = "osd-canceled"
            queue_file = _write_queue(
                repo_root,
                task_id,
                state="in_progress",
                failure_signatures=[],
            )
            backend = orchestrator.create_backend(queue_file=queue_file)

            buf = io.StringIO()
            with redirect_stdout(buf):
                deltas = orchestrator._finalize_task(
                    backend,
                    queue_file,
                    task_id,
                    ret=-1,
                    repo_root=repo_root,
                    adapter=None,
                    on_failure="triage",
                    canceled=True,
                )

            self.assertEqual(deltas, {"successes": 0, "failures": 0, "stop_spawn": False})
            self.assertIn("canceled by operator stop; returned to ready", buf.getvalue())
            queue = load_queue(queue_file)
            self.assertEqual(queue[0]["state"], "ready")
            self.assertEqual(queue[0].get("failure_signatures", []), [])


class TestOperatorStopIntegration(unittest.TestCase):
    """rl-01 / R-4, R-7: an operator stop cancels tasks, leaving them ready with no signature."""

    def test_batch_run_sigterm_leaves_task_ready_and_prints_canceled(self):
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            task_id = "rl01-sigterm"
            started_file = os.path.join(repo_root, "started.txt")
            fake_cli = _write_sleeping_cli(repo_root, started_file)
            queue_file = _setup_plan_and_queue(repo_root, task_id)
            adapter = orchestrator.resolve_cli_adapter(fake_cli)

            args = argparse.Namespace(
                queue_file=queue_file,
                plan_file=None,
                repo_root=repo_root,
                cli_bin=fake_cli,
                isolation="minimal",
                max_jobs=1,
                task_timeout=30.0,
                heartbeat_interval=999,
                on_failure="continue",
                force=False,
            )

            result = {"rc": None, "out": ""}

            def target():
                buf = io.StringIO()
                with redirect_stdout(buf):
                    with patch.dict(os.environ, {"PATH": f"{Path(fake_cli).parent}:{os.environ.get('PATH', '')}"}):
                        result["rc"] = orchestrator.run_batch(args, adapter)
                result["out"] = buf.getvalue()

            thread = threading.Thread(target=target)
            thread.start()

            # Wait for the child session to start
            for _ in range(100):
                if os.path.exists(started_file):
                    break
                time.sleep(0.05)
            self.assertTrue(os.path.exists(started_file), "child never started")

            try:
                # Trigger SIGTERM to orchestrator
                orchestrator._handle_signal(signal.SIGTERM, None)

                thread.join(timeout=15)
                self.assertFalse(thread.is_alive(), "run_batch did not finish")

                self.assertIn("canceled by operator stop", result["out"])

                queue = load_queue(queue_file)
                task = next(t for t in queue if t["id"] == task_id)
                self.assertEqual(task["state"], "ready")
                self.assertEqual(task.get("failure_signatures", []), [])
            finally:
                orchestrator._shutdown_requested = False

    def test_stage_record_and_run_summary_canceled(self):
        """Unit test: stage record of canceled task has failure_class: canceled, summary has canceled: true."""
        with tempfile.TemporaryDirectory() as repo_root:
            logger = telemetry.RunLogger(repo_root, run_id="test-canceled-run")
            cls = orchestrator._classify_failure(
                exit_code=-1,
                tail="shutdown",
                stage="implement",
                verdict_recorded=False,
                shutdown=True,
                killed_by_timeout=True,
            )
            self.assertEqual(cls.value, "canceled")

            rec = telemetry.stage_record(
                run_id=logger.run_id,
                task_id="t1",
                plan_file="docs/plans/t1.md",
                stage="implement",
                agent_cli="test",
                isolation_level="minimal",
                start_time=telemetry.iso_now(),
                end_time=telemetry.iso_now(),
                exit_code=-1,
                failure_class=cls.value,
            )
            self.assertEqual(rec["failure_class"], "canceled")

            summary = telemetry.run_summary_record(
                run_id=logger.run_id,
                start_time=telemetry.iso_now(),
                end_time=telemetry.iso_now(),
                tasks_spawned=1,
                tasks_succeeded=0,
                tasks_failed=0,
                canceled=True,
            )
            self.assertTrue(summary["canceled"])


if __name__ == "__main__":
    unittest.main()
