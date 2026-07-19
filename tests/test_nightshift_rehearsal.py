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
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

# Ensure the aet-work lib is on the path before importing telemetry.
sys.path.insert(0, str(Path(__file__).parent.parent / "aet-work" / "lib"))

import failure

# Load the orchestrator script (no .py extension) as a module.
_ORCHESTRATOR_BIN = Path(__file__).parent.parent / "aet-work" / "bin" / "orchestrator"
sys.path.insert(0, str(_ORCHESTRATOR_BIN.parent))
_orchestrator_loader = importlib.machinery.SourceFileLoader(
    "orchestrator", str(_ORCHESTRATOR_BIN)
)
_spec = importlib.util.spec_from_loader("orchestrator", _orchestrator_loader)
orchestrator = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(orchestrator)


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "nightshift"


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
        'import subprocess\n'
        'import sys\n'
        'import time\n'
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
        '# Stall: emit usage, then go silent until the watchdog kills us.\n'
        'if "stall" in prompt:\n'
        '    result_envelope()\n'
        '    time.sleep(600)\n'
        '    sys.exit(0)\n'
        '\n'
        '# Healthy fixture: ensure at least one commit exists and exit 0.\n'
        'ahead = subprocess.run(\n'
        '    ["git", "rev-list", "--count", "main..HEAD"],\n'
        '    capture_output=True, text=True, check=False\n'
        ')\n'
        'if ahead.returncode != 0 or int(ahead.stdout.strip() or 0) == 0:\n'
        '    with open("fixture-done.txt", "w", encoding="utf-8") as f:\n'
        '        f.write("healthy\\n")\n'
        '    subprocess.run(["git", "add", "."], check=True)\n'
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
    """End-to-end rehearsal over a mixed unattended queue."""

    def _run_batch(self, args, adapter, timeout: float = 60):
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

    def _setup_repo(self):
        """Create a temp repo with fixtures, fake CLI, and a three-task queue."""
        repo_root = tempfile.mkdtemp(prefix="nsr-07-rehearsal-")
        self.addCleanup(lambda: subprocess.run(["rm", "-rf", repo_root]))

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
        self.enterContext(patch.dict(os.environ, {"PATH": new_path}))

        adapter = orchestrator.resolve_cli_adapter(str(fake_cli))
        args = argparse.Namespace(
            queue_file=queue_file,
            plan_file=None,
            repo_root=repo_root,
            cli_bin="claude",
            isolation="minimal",
            max_jobs=3,
            task_timeout=999,
            stall_timeout=5,
            heartbeat_interval=999,
            on_failure="triage",
        )
        return repo_root, queue_file, args, adapter

    def _load_queue(self, queue_file: str) -> dict[str, dict]:
        """Return tasks indexed by id."""
        queue = json.loads(Path(queue_file).read_text(encoding="utf-8"))["tasks"]
        return {t["id"]: t for t in queue}

    def test_mixed_queue_finishes_unattended(self):
        """The healthy task reaches awaiting_merge and the shift does not hang."""
        _repo_root, queue_file, args, adapter = self._setup_repo()

        rc, out = self._run_batch(args, adapter, timeout=60)

        by_id = self._load_queue(queue_file)

        self.assertEqual(by_id["nightshift-healthy"]["state"], "awaiting_merge")
        self.assertIn("awaiting merge", out)

    def test_deterministic_failure_quarantined_by_breaker(self):
        """The deterministic failure ends quarantined after the breaker trips."""
        _repo_root, queue_file, args, adapter = self._setup_repo()

        self._run_batch(args, adapter, timeout=60)

        by_id = self._load_queue(queue_file)

        self.assertEqual(
            by_id["nightshift-deterministic-failure"]["state"], "quarantined"
        )

    def test_stall_killed_and_classified_timeout(self):
        """The stall fixture is killed and its failure class is timeout."""
        _repo_root, queue_file, args, adapter = self._setup_repo()

        self._run_batch(args, adapter, timeout=60)

        task = self._load_queue(queue_file)["nightshift-stall"]
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
        _repo_root, queue_file, args, adapter = self._setup_repo()

        self._run_batch(args, adapter, timeout=60)

        by_id = self._load_queue(queue_file)

        for task_id in (
            "nightshift-deterministic-failure",
            "nightshift-stall",
        ):
            cost = by_id[task_id].get("cost")
            self.assertIsNotNone(cost, f"{task_id} missing cost on ledger")
            self.assertIn("tokens", cost)
            self.assertIn("usd", cost)


if __name__ == "__main__":
    unittest.main()
