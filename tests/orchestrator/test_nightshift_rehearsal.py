"""Phase 5 exit-gate rehearsal for the night-shift runtime (nsr-07).

Runs a small mixed queue unattended and asserts that the healthy task completes,
the deterministic failure is quarantined by the breaker, the stall is killed and
classified as timeout, the shift finishes without hanging, and both incident
tasks carry a per-task cost figure on the ledger.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import json
import os
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure the aet-work lib is on the path before importing telemetry.
from aet import breaker, failure

# Load the orchestrator script (no .py extension) as a module.
_ORCHESTRATOR_BIN = Path(__file__).parents[2] / "src" / "aet" / "cli" / "orchestrator.py"
_orchestrator_loader = importlib.machinery.SourceFileLoader(
    "orchestrator", str(_ORCHESTRATOR_BIN)
)
_spec = importlib.util.spec_from_loader("orchestrator", _orchestrator_loader)
orchestrator = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(orchestrator)

pytestmark = pytest.mark.xdist_group("process-group")


FIXTURES_DIR = Path(__file__).parents[1] / "fixtures" / "nightshift"


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


def _copy_fixtures(repo_root: str) -> Path:
    """Copy the nightshift fixture plans into the temp repo."""
    dest = Path(repo_root) / "tests" / "fixtures" / "nightshift"
    dest.mkdir(parents=True, exist_ok=True)
    for plan in FIXTURES_DIR.glob("*.md"):
        (dest / plan.name).write_text(plan.read_text(encoding="utf-8"), encoding="utf-8")
    return dest


def _write_rehearsal_workflow(repo_root: str) -> Path:
    """Write a single-skilled-stage workflow so the rehearsal stays focused."""
    workflow_path = Path(repo_root) / ".agents" / "workflows" / "rehearsal.json"
    workflow_path.parent.mkdir(parents=True, exist_ok=True)
    workflow_path.write_text(
        json.dumps(
            {
                "version": 1,
                "name": "rehearsal",
                "done_state": "done",
                "stages": [
                    {
                        "name": "plan-approved",
                        "skills": ["aet-tdd", "aet-implement"],
                        "evidence": None,
                        "gate_key": None,
                    },
                    {
                        "name": "implemented",
                        "skills": [],
                        "evidence": None,
                        "gate_key": None,
                    },
                ],
                "execution_policy": {"session_groups": [["plan-approved"]]},
                "routing": {
                    "default": {"harness": "claude", "model": None},
                    "by_stage": {},
                },
            }
        ),
        encoding="utf-8",
    )
    return workflow_path


def _write_fake_claude(repo_root: str) -> Path:
    """Create a fake claude CLI that drives the fixture behaviors."""
    bin_dir = Path(repo_root) / "bin"
    bin_dir.mkdir(exist_ok=True)
    fake_cli = bin_dir / "claude"
    fake_cli.write_text(
        '#!/usr/bin/env python3\n'
        'import os\n'
        'import signal\n'
        'import subprocess\n'
        'import sys\n'
        '\n'
        'prompt = sys.argv[-1]\n'
        '\n'
        'def result_envelope():\n'
        '    print(\'[{"type": "result", "usage": '
        '{"input_tokens": 10, "output_tokens": 5}, '
        '"total_cost_usd": 0.001}]\')\n'
        '    sys.stdout.flush()\n'
        '\n'
        '# Triage prompts always requeue so the breaker can eventually trip.\n'
        'if "failure-triage agent" in prompt:\n'
        '    print(\'{"action": "requeue"}\')\n'
        '    sys.exit(0)\n'
        '\n'
        '# Deterministic failure: stable tail and exit 1.\n'
        'if "deterministic-failure" in prompt:\n'
        '    print("FAILED: deterministic failure fixture")\n'
        '    result_envelope()\n'
        '    sys.exit(1)\n'
        '\n'
        '# Stall: emit usage, then self-SIGKILL to exercise the signal-exit\n'
        '# timeout path. The orchestrator classifies any signal-killed session\n'
        '# as timeout and records a TIMEOUT signature. The real stall watchdog\n'
        '# is covered by test_stall_watchdog.py.\n'
        'if "stall" in prompt:\n'
        '    result_envelope()\n'
        '    os.kill(os.getpid(), signal.SIGKILL)\n'
        '\n'
        '# Healthy fixture: ensure at least one commit exists and exit 0.\n'
        'print("fixture: checking commits", flush=True)\n'
        'ahead = subprocess.run(\n'
        '    ["git", "rev-list", "--count", "main..HEAD"],\n'
        '    capture_output=True, text=True, check=False\n'
        ')\n'
        'if ahead.returncode != 0 or int(ahead.stdout.strip() or 0) == 0:\n'
        '    print("fixture: writing marker", flush=True)\n'
        '    with open("fixture-done.txt", "w", encoding="utf-8") as f:\n'
        '        f.write("healthy\\n")\n'
        '    print("fixture: staging", flush=True)\n'
        '    subprocess.run(["git", "add", "."], check=True)\n'
        '    print("fixture: committing", flush=True)\n'
        '    subprocess.run(["git", "commit", "-m", "healthy fixture"], check=True)\n'
        'print("SUCCESS: healthy fixture completed")\n'
        'result_envelope()\n'
        'sys.exit(0)\n',
        encoding="utf-8",
    )
    fake_cli.chmod(0o755)
    return fake_cli


def _write_queue(repo_root: str, tasks: list[dict]) -> str:
    """Write a wrapper-format queue file and return its path."""
    queue_file = Path(repo_root) / ".agents" / "work-queue.json"
    queue_file.parent.mkdir(parents=True, exist_ok=True)
    queue_file.write_text(
        json.dumps(
            {
                "queue_updated_at": "2026-07-17T00:00:00Z",
                "source_prd": "docs/prds/roadmap-p5-night-shift-runtime-prd.md",
                "tasks": tasks,
            }
        ),
        encoding="utf-8",
    )
    return str(queue_file)


def _commit_repo_state(repo_root: str) -> None:
    """Commit fixtures, workflow, fake CLI, and queue so origin/main has the base state."""
    subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
    subprocess.run(
        ["git", "-C", repo_root, "commit", "-q", "-m", "add fixtures and queue"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", repo_root, "update-ref", "refs/remotes/origin/main", "HEAD"],
        check=True,
    )


class TestNightShiftExitGateRehearsal(unittest.TestCase):
    """End-to-end rehearsal over a mixed unattended queue.

    The stall fixture self-SIGKILLs to exercise the signal-exit timeout path:
    the child orchestrator sees a negative exit code, classifies the failure as
    timeout, records a TIMEOUT signature, and the batch parent leaves the task
    failed. The real stall watchdog is covered by
    tests/orchestrator/test_stall_watchdog.py. Every test below only reads the
    resulting queue state, so the batch runs once for the whole class.
    """

    queue_file: str
    run_out: str

    @classmethod
    def setUpClass(cls):
        """Run the one shift the whole class asserts against."""
        cls.repo_root, queue_file, args, adapter = cls._setup_repo()
        cls.queue_file = queue_file
        _rc, cls.run_out = cls._run_batch(args, adapter, timeout=300)

    @staticmethod
    def _run_batch(args, adapter, timeout: float = 300):
        """Run run_batch in a thread; return (rc, combined stdout/stderr)."""
        result = {"rc": None, "out": ""}
        orchestrator._shutdown_requested = False

        def target():
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                result["rc"] = orchestrator.run_batch(args, adapter)
            result["out"] = buf.getvalue()

        thread = threading.Thread(target=target)
        thread.start()
        thread.join(timeout=timeout)
        if thread.is_alive():
            orchestrator._shutdown_requested = True
            thread.join(timeout=5)
            raise AssertionError("run_batch did not finish within timeout")
        return result["rc"], result["out"]

    @classmethod
    def _setup_repo(cls):
        """Create a temp repo with fixtures, fake CLI, and a three-task queue."""
        repo_root = tempfile.mkdtemp(prefix="nsr-07-rehearsal-")
        cls.addClassCleanup(lambda: subprocess.run(["rm", "-rf", repo_root]))

        _init_git_repo(repo_root)
        _copy_fixtures(repo_root)
        _write_rehearsal_workflow(repo_root)
        fake_cli = _write_fake_claude(repo_root)

        queue_file = _write_queue(
            repo_root,
            [
                {
                    "id": "nightshift-healthy",
                    "title": "Healthy fixture",
                    "plan_file": "tests/fixtures/nightshift/healthy.md",
                    "blocked_by": [],
                    "state": "ready",
                },
                {
                    "id": "nightshift-deterministic-failure",
                    "title": "Deterministic failure fixture",
                    "plan_file": "tests/fixtures/nightshift/deterministic-failure.md",
                    "blocked_by": [],
                    "state": "ready",
                },
                {
                    "id": "nightshift-stall",
                    "title": "Stall fixture",
                    "plan_file": "tests/fixtures/nightshift/stall.md",
                    "blocked_by": [],
                    "state": "ready",
                },
            ],
        )
        _commit_repo_state(repo_root)

        # Ensure the fake claude is first on PATH for spawned children.
        new_path = f"{fake_cli.parent}{os.pathsep}{os.environ.get('PATH', '')}"
        cls.enterClassContext(patch.dict(os.environ, {"PATH": new_path}))

        # Lower the breaker threshold for the rehearsal so the deterministic
        # failure quarantines after one retry instead of the default three,
        # shrinking the serial setup time without changing the covered behavior.
        _orig_should_quarantine = breaker.should_quarantine_task
        cls.enterClassContext(
            patch.object(
                breaker,
                "should_quarantine_task",
                side_effect=lambda record: _orig_should_quarantine(record, threshold=1),
            )
        )

        adapter = orchestrator.resolve_cli_adapter(str(fake_cli))
        args = argparse.Namespace(
            queue_file=queue_file,
            plan_file=None,
            repo_root=repo_root,
            cli_bin="claude",
            isolation="minimal",
            max_jobs=3,
            task_timeout=999,
            heartbeat_interval=999,
            on_failure="triage",
        )
        return repo_root, queue_file, args, adapter

    def _load_queue(self) -> dict[str, dict]:
        """Return the shift's final tasks indexed by id."""
        queue = json.loads(Path(self.queue_file).read_text(encoding="utf-8"))["tasks"]
        return {t["id"]: t for t in queue}

    def test_mixed_queue_finishes_unattended(self):
        """The healthy task reaches awaiting_merge and the shift does not hang."""
        by_id = self._load_queue()

        self.assertEqual(by_id["nightshift-healthy"]["state"], "awaiting_merge")
        self.assertIn("awaiting merge", self.run_out)

    def test_deterministic_failure_quarantined_by_breaker(self):
        """The deterministic failure ends quarantined after the breaker trips."""
        by_id = self._load_queue()

        self.assertEqual(
            by_id["nightshift-deterministic-failure"]["state"], "quarantined"
        )

    def test_stall_killed_and_classified_timeout(self):
        """The stall fixture is killed and its failure class is timeout."""
        task = self._load_queue()["nightshift-stall"]
        # The stall task is either quarantined by the breaker or still failed;
        # either way the recorded failure class is timeout.
        self.assertIn(task["state"], {"quarantined", "failed"})
        last_entry = (task.get("failure_signatures") or [])[-1:]
        self.assertTrue(last_entry, "expected at least one failure signature")
        self.assertEqual(
            last_entry[0].get("class"),
            failure.FailureClass.TIMEOUT.value,
        )

    def test_both_incidents_costed_on_ledger(self):
        """Both incident tasks carry a per-task cost figure on the ledger."""
        by_id = self._load_queue()

        for task_id in (
            "nightshift-deterministic-failure",
            "nightshift-stall",
        ):
            cost = by_id[task_id].get("cost")
            self.assertIsNotNone(cost, f"{task_id} missing cost on ledger")
            self.assertIn("tokens", cost)
            self.assertIn("usd", cost)

    def test_no_fatal_teardown_output(self):
        """A failing worktree teardown is captured, not emitted as a git fatal line."""
        self.assertNotIn(
            "fatal:",
            self.run_out.lower(),
            f"git fatal teardown line leaked to output:\n{self.run_out}",
        )

    def test_incident_worktrees_are_removed(self):
        """Incident task worktrees are torn down instead of left on disk."""
        for task_id in (
            "nightshift-deterministic-failure",
            "nightshift-stall",
        ):
            worktree_dir = Path(self.repo_root, ".worktrees", task_id)
            self.assertFalse(
                worktree_dir.exists(),
                f"worktree for {task_id} was not removed: {worktree_dir}",
            )


if __name__ == "__main__":
    unittest.main()
