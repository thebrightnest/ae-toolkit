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

from aet.cli_adapter import CLIAdapter

pytestmark = pytest.mark.xdist_group("process-group")

# Ensure the aet-work lib is on the path before importing telemetry.
# Load the orchestrator script (no .py extension) as a module.
_ORCHESTRATOR_BIN = Path(__file__).parents[2] / "src" / "aet" / "cli" / "orchestrator.py"
_orchestrator_loader = importlib.machinery.SourceFileLoader(
    "orchestrator", str(_ORCHESTRATOR_BIN)
)
_spec = importlib.util.spec_from_loader("orchestrator", _orchestrator_loader)
orchestrator = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(orchestrator)


# Trimmed from real `claude -p --output-format json` output captured 2026-07-12:
# a single-line JSON array whose final element (type "result") carries `usage`
# and `total_cost_usd`.
_CLAUDE_ENVELOPE = (
    '[{"type":"system","subtype":"init","session_id":"s1"},'
    '{"type":"assistant","message":{"content":[{"type":"text","text":"OK"}],'
    '"usage":{"input_tokens":2,"cache_creation_input_tokens":13845,'
    '"cache_read_input_tokens":0,"output_tokens":1}}},'
    '{"type":"result","subtype":"success","is_error":false,"num_turns":1,'
    '"result":"OK","total_cost_usd":0.139146,'
    '"usage":{"input_tokens":2,"cache_creation_input_tokens":13845,'
    '"cache_read_input_tokens":0,"output_tokens":4,'
    '"server_tool_use":{"web_search_requests":0}}}]'
)


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
    """Create a fake agent CLI that sleeps silently until killed."""
    bin_dir = Path(repo_root) / "bin"
    bin_dir.mkdir()
    fake_cli = bin_dir / "kimi"
    helper = Path(__file__).parents[1] / "fixtures" / "sleep_until_signaled.py"
    fake_cli.write_text(
        "#!/usr/bin/env bash\n"
        "# ignore prompt flag and prompt\n"
        f"exec python3 '{helper}' 600\n",
        encoding="utf-8",
    )
    fake_cli.chmod(0o755)
    return str(fake_cli)


def _write_kimi_session(home: Path, session_id: str) -> Path:
    """Materialize a minimal fake ~/.kimi-code session with usage in wire files."""
    session_dir = home / "sessions" / "wd_proj_abc123" / session_id
    wire = session_dir / "agents" / "main" / "wire.jsonl"
    wire.parent.mkdir(parents=True, exist_ok=True)
    wire.write_text(
        json.dumps(
            {
                "type": "context.append_loop_event",
                "event": {
                    "type": "step.end",
                    "uuid": "u1",
                    "turnId": "0",
                    "step": 1,
                    "usage": {
                        "inputOther": 10,
                        "output": 1,
                        "inputCacheRead": 0,
                        "inputCacheCreation": 0,
                    },
                    "finishReason": "stop",
                },
                "time": 1781943979640,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    with (home / "session_index.jsonl").open("a") as f:
        f.write(
            json.dumps(
                {
                    "sessionId": session_id,
                    "sessionDir": str(session_dir),
                    "workDir": "/tmp/proj",
                }
            )
            + "\n"
        )
    return session_dir


class TestStallWatchdog(unittest.TestCase):
    """Unit tests for the stdout-silence watchdog in _run_with_live_tee."""

    def test_silent_session_killed_after_stall_timeout(self):
        """A silent session is killed and classified as timeout (-9)."""
        with tempfile.TemporaryDirectory() as cwd:
            helper = (
                Path(__file__).parents[1] / "fixtures" / "sleep_until_signaled.py"
            )
            cmd = [sys.executable, str(helper), "600"]
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


class TestAdapterStallResolution(unittest.TestCase):
    """The watchdog interval resolves from the active CLIAdapter (ADR-053)."""

    def _custom_adapter(self, stall_timeout: float) -> CLIAdapter:
        return CLIAdapter(
            name="test",
            bin="test",
            prompt_flag="-p",
            workdir_flag=None,
            headless_flag=None,
            stall_timeout=stall_timeout,
            wall_backstop=10.0,
        )

    def test_spawn_session_uses_adapter_stall_timeout(self):
        """A custom adapter with a short stall timeout triggers a fast kill."""
        with tempfile.TemporaryDirectory() as cwd:
            helper = (
                Path(__file__).parents[1] / "fixtures" / "sleep_until_signaled.py"
            )
            adapter = self._custom_adapter(stall_timeout=0.1)
            cmd = [sys.executable, str(helper), "600"]
            start = time.monotonic()
            exit_code, _usage, _session_dir, output = orchestrator._spawn_session_with_tail(
                adapter, cmd, cwd, os.environ.copy()
            )
            elapsed = time.monotonic() - start
            self.assertEqual(exit_code, -9)
            self.assertLess(elapsed, 5.0)
            self.assertEqual(output, "")

    def test_spawn_session_spares_emitting_session(self):
        """An emitting session survives an adapter's short stall timeout."""
        with tempfile.TemporaryDirectory() as cwd:
            script = (
                "import time, sys\n"
                "for i in range(10):\n"
                "    print(f'line {i}', flush=True)\n"
                "    time.sleep(0.05)\n"
            )
            adapter = self._custom_adapter(stall_timeout=0.15)
            cmd = [sys.executable, "-c", script]
            start = time.monotonic()
            exit_code, _usage, _session_dir, output = orchestrator._spawn_session_with_tail(
                adapter, cmd, cwd, os.environ.copy()
            )
            elapsed = time.monotonic() - start
            self.assertEqual(exit_code, 0)
            self.assertGreaterEqual(elapsed, 0.4)
            self.assertIn("line 9", output)


class TestDetachedOutputAndUsage(unittest.TestCase):
    """Regression tests for R-6: the live tee must stay on and usage must parse."""

    def test_claude_json_envelope_output_is_complete_and_usage_non_null(self):
        """A detached claude run writes the full envelope to output.log and parses usage."""
        with tempfile.TemporaryDirectory() as cwd:
            script = f"import sys; print({_CLAUDE_ENVELOPE!r}, flush=True)"
            adapter = orchestrator.resolve_cli_adapter("claude")
            cmd = [sys.executable, "-c", script]
            exit_code, usage, _session_dir, output = orchestrator._spawn_session_with_tail(
                adapter, cmd, cwd, os.environ.copy()
            )
            self.assertEqual(exit_code, 0)
            self.assertIn("total_cost_usd", output)
            self.assertIsNotNone(usage)
            self.assertEqual(usage["output_tokens"], 4)
            self.assertAlmostEqual(usage["cost_usd"], 0.139146)

    def test_kimi_wire_file_output_is_complete_and_usage_non_null(self):
        """A detached kimi run writes the resume hint to output.log and parses wire usage."""
        with tempfile.TemporaryDirectory() as cwd:
            with tempfile.TemporaryDirectory() as home_dir:
                kimi_home = Path(home_dir) / ".kimi-code"
                session_id = "session_rid_05_kimi"
                _write_kimi_session(kimi_home, session_id)
                env = os.environ.copy()
                script = (
                    "import sys; "
                    f"print('To resume this session: kimi -r {session_id}', flush=True)"
                )
                adapter = orchestrator.resolve_cli_adapter("kimi")
                cmd = [sys.executable, "-c", script]
                with patch.object(Path, "home", return_value=Path(home_dir)):
                    exit_code, usage, session_dir, output = orchestrator._spawn_session_with_tail(
                        adapter, cmd, cwd, env
                    )
                self.assertEqual(exit_code, 0)
                self.assertIn(session_id, output)
                self.assertIsNotNone(usage)
                self.assertEqual(usage["input_tokens"], 10)
                self.assertEqual(usage["output_tokens"], 1)
                self.assertIsNotNone(session_dir)


class TestSignalExitClassification(unittest.TestCase):
    """Regression tests for osd-02: signal-killed sessions classify as timeout."""

    def _write_self_sigkill_cli(self, repo_root: str) -> str:
        """Create a fake agent CLI that emits usage then self-SIGKILLs."""
        bin_dir = Path(repo_root) / "bin"
        bin_dir.mkdir(exist_ok=True)
        fake_cli = bin_dir / "kimi"
        fake_cli.write_text(
            "#!/usr/bin/env python3\n"
            "import os\n"
            "import signal\n"
            "import sys\n"
            'print(\'[{"type": "result", "usage": '
            '{"input_tokens": 10, "output_tokens": 5}, '
            '"total_cost_usd": 0.001}]\')\n'
            "sys.stdout.flush()\n"
            "os.kill(os.getpid(), signal.SIGKILL)\n",
            encoding="utf-8",
        )
        fake_cli.chmod(0o755)
        return str(fake_cli)

    def _custom_adapter(self, fake_cli: str, stall_timeout: float) -> CLIAdapter:
        """Return a CLIAdapter pointing at the fake CLI with a short stall timeout."""
        return CLIAdapter(
            name="test",
            bin=fake_cli,
            prompt_flag="-p",
            workdir_flag=None,
            headless_flag=None,
            stall_timeout=stall_timeout,
            wall_backstop=10.0,
        )

    def test_run_stage_records_timeout_signature_for_signal_death(self):
        """A session killed by SIGKILL is classified and recorded as timeout."""
        with tempfile.TemporaryDirectory() as repo_root:
            fake_cli = self._write_self_sigkill_cli(repo_root)
            queue_file = _write_queue(
                repo_root,
                [
                    {
                        "id": "osd-signal",
                        "title": "osd-signal",
                        "plan_file": "docs/plans/osd-signal.md",
                        "blocked_by": [],
                        "state": "ready",
                    }
                ],
            )
            backend = orchestrator.create_backend(queue_file=queue_file)
            task = {
                "id": "osd-signal",
                "plan_file": "docs/plans/osd-signal.md",
                "state": "in_progress",
            }
            Path(repo_root, "docs", "plans", "osd-signal.md").parent.mkdir(
                parents=True, exist_ok=True
            )
            Path(repo_root, "docs", "plans", "osd-signal.md").write_text(
                "---\nid: osd-signal\n---\n\n# Demo\n\n_Stage: plan-approved_\n",
                encoding="utf-8",
            )
            adapter = self._custom_adapter(fake_cli, stall_timeout=2.0)

            exit_code, _usage, _session_dir, _output = orchestrator.run_stage(
                adapter,
                repo_root=repo_root,
                plan_file="docs/plans/osd-signal.md",
                worktree_dir=repo_root,
                skills=["aet-tdd", "aet-implement"],
                current_stage="plan-approved",
                next_stage="implemented",
                task_id="osd-signal",
                task=task,
                backend=backend,
            )

            self.assertLess(exit_code, 0)
            self.assertTrue(task.get("failure_signatures"))
            last = task["failure_signatures"][-1]
            self.assertEqual(last.get("class"), "timeout")


class TestBatchTimeoutBackstop(unittest.TestCase):
    """Integration tests for stall and wall-clock kills through run_batch."""

    def _run_batch(self, args, adapter, timeout: float = 90):
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
                task_timeout=0.5,
                heartbeat_interval=999,
                on_failure="continue",
            )

            with patch.object(
                orchestrator, "verify_branch_has_commits", return_value=(True, "")
            ):
                rc, out = self._run_batch(args, adapter, timeout=15)

            self.assertEqual(rc, 1)
            self.assertIn("timed out after 0.5s", out)

            queue = json.loads(Path(queue_file).read_text(encoding="utf-8"))["tasks"]
            self.assertEqual(queue[0]["state"], "failed")


if __name__ == "__main__":
    unittest.main()
