"""Integration tests for Merge Train staging and flush (ADR-079, R-3, R-5, R-6, R-7).

Covers:
1. Three independent tasks → exactly one validate_command call at end of run, all three merged.
2. Task B blocked by staged Task A → flush triggers and Task B starts in the same run.
3. No validation subprocess starts while integration_lock is held (lock-holder instrumentation).
4. Red flush → all staged tasks remain awaiting_merge, integration branch unmoved.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pytest

from aet import telemetry
from aet.cli import orchestrator
from aet.cli.aet_state import resolve_task_record
from aet.cli_adapter import CLIAdapter

pytestmark = pytest.mark.xdist_group("git-repo")

_SRC_DIR = Path(__file__).parents[2] / "src"


def _init_git_repo(repo_root: str, origin_root: str) -> None:
    """Initialize a git repo with main and a bare origin remote."""
    subprocess.run(["git", "init", "--bare", "-q", origin_root], check=True)
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
    Path(repo_root, ".gitignore").write_text(
        ".agents/hooks/\n.agents/concurrency.log\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
    subprocess.run(
        ["git", "-C", repo_root, "commit", "-q", "-m", "initial"],
        check=True,
    )
    subprocess.run(["git", "-C", repo_root, "branch", "-M", "main"], check=True)
    subprocess.run(
        ["git", "-C", repo_root, "remote", "add", "origin", origin_root],
        check=True,
    )
    subprocess.run(
        ["git", "-C", repo_root, "push", "-q", "-u", "origin", "main"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", repo_root, "update-ref", "refs/remotes/origin/main", "HEAD"],
        check=True,
    )


def _create_integration_branch(repo_root: str, name: str = "epic-01") -> None:
    """Create and push an integration branch from the current HEAD."""
    subprocess.run(
        ["git", "-C", repo_root, "checkout", "-q", "-b", name],
        check=True,
    )
    subprocess.run(
        ["git", "-C", repo_root, "push", "-q", "-u", "origin", name],
        check=True,
    )
    subprocess.run(
        ["git", "-C", repo_root, "update-ref", f"refs/remotes/origin/{name}", "HEAD"],
        check=True,
    )
    subprocess.run(["git", "-C", repo_root, "checkout", "-q", "main"], check=True)


def _write_plan(
    repo_root: str,
    task_id: str,
    work_class: str = "normal",
    blocks: list[str] | None = None,
    blocked_by: list[str] | None = None,
) -> str:
    """Write a minimal plan markdown file."""
    plan_file = os.path.join(repo_root, "docs", "plans", f"{task_id}.md")
    Path(plan_file).parent.mkdir(parents=True, exist_ok=True)
    extra_yaml = ""
    if blocks:
        extra_yaml += "blocks:\n" + "\n".join(f"  - {b}" for b in blocks) + "\n"
    if blocked_by:
        extra_yaml += "blocked_by:\n" + "\n".join(f"  - {b}" for b in blocked_by) + "\n"
    Path(plan_file).write_text(
        f"---\nid: {task_id}\nworkflow: test\nwork_class: {work_class}\n{extra_yaml}---\n\n"
        f"# {task_id}\n\n_Stage: plan-approved_\n",
        encoding="utf-8",
    )
    return plan_file


def _write_test_workflow(repo_root: str) -> str:
    """Write a minimal workflow that ends at qa-complete."""
    workflows_dir = Path(repo_root, ".agents", "workflows")
    workflows_dir.mkdir(parents=True, exist_ok=True)
    workflow_file = workflows_dir / "test.json"
    workflow_file.write_text(
        json.dumps(
            {
                "version": 1,
                "name": "test",
                "done_state": "qa-complete",
                "stages": [
                    {
                        "name": "plan-approved",
                        "skills": ["aet-tdd", "aet-implement"],
                        "evidence": None,
                        "gate_key": None,
                    },
                    {
                        "name": "implemented",
                        "skills": ["aet-qa"],
                        "evidence": "qa",
                        "gate_key": None,
                    },
                ],
                "execution_policy": {"session_groups": [["plan-approved", "implemented"]]},
                "routing": {"default": {"harness": "claude", "model": None}, "by_stage": {}},
            }
        ),
        encoding="utf-8",
    )
    return str(workflow_file)


def _install_fake_cli(temp_dir: str) -> tuple[Path, CLIAdapter]:
    """Create a fake CLI script named 'claude' that implements stage commits and writes QA verdicts."""
    fake_bin_dir = Path(temp_dir) / "fake-bin"
    fake_bin_dir.mkdir(parents=True, exist_ok=True)
    fake_cli = fake_bin_dir / "claude"

    src_str = str(_SRC_DIR)
    script_content = f"""#!{sys.executable}
import json
import os
import pathlib
import subprocess
import sys
import time

if {src_str!r} not in sys.path:
    sys.path.insert(0, {src_str!r})

wt = os.environ.get('AET_WORKTREE', '.')
name = os.environ.get('AET_TASK_ID', 'task')
repo_root = os.environ.get('AET_REPO_ROOT', '.')

hook_file = pathlib.Path(repo_root) / '.agents' / 'hooks' / f'{{name}}.py'
if hook_file.exists():
    global_vars = {{
        'wt': wt,
        'name': name,
        'repo_root': repo_root,
        'os': os,
        'sys': sys,
        'time': time,
        'subprocess': subprocess,
        'pathlib': pathlib,
        'json': json,
    }}
    with open(hook_file, 'r', encoding='utf-8') as f:
        exec(f.read(), global_vars)
else:
    counter_file = pathlib.Path(wt, '.stage-counter')
    counter = int(counter_file.read_text().strip()) if counter_file.exists() else 0
    counter += 1
    counter_file.write_text(str(counter))
    pathlib.Path(wt, f'{{name}}-{{counter}}.txt').write_text(f'stage {{counter}}')
    subprocess.run(['git', '-C', wt, 'add', '.'], check=True)
    subprocess.run(['git', '-C', wt, 'commit', '-q', '-m', f'stage {{counter}}'], check=True)
    from aet import evidence, telemetry
    project_slug = telemetry.derive_project_slug(repo_root)
    record = {{
        'task_id': name,
        'stage': 'qa-complete',
        'skill': 'aet-qa',
        'verdict': 'pass',
        'summary': 'fake qa passed',
        'generated_at': telemetry.iso_now(),
        'test_command': 'make validate',
        'tests_total': 1,
        'tests_passed': 1,
        'tests_failed': 0,
    }}
    evidence.write_verdict(name, 'qa', record, project_slug=project_slug, worktree_dir=wt)
"""
    fake_cli.write_text(script_content, encoding="utf-8")
    fake_cli.chmod(0o755)

    adapter = CLIAdapter(
        name="claude",
        bin="claude",
        prompt_flag="-p",
        workdir_flag=None,
        headless_flag="--dangerously-skip-permissions",
    )
    return fake_bin_dir, adapter


def _get_task(backend, queue_file: str, task_id: str) -> dict:
    task, sealed = resolve_task_record(task_id, queue_file, backend=backend)
    rec = task or sealed
    assert rec is not None, f"Task {task_id} not found in live queue or sealed history"
    return rec


class TestMergeTrainFlush(unittest.TestCase):
    """Integration tests for merge train batch flush and staging."""

    def setUp(self):
        self._tmp_repo = tempfile.TemporaryDirectory()
        self._tmp_origin = tempfile.TemporaryDirectory()
        self._tmp_misc = tempfile.TemporaryDirectory()

        self.repo_root = self._tmp_repo.name
        self.origin_root = self._tmp_origin.name
        self.misc_dir = self._tmp_misc.name

        self.reports_dir = Path(self.misc_dir) / "reports"
        self.telemetry_dir = Path(self.misc_dir) / "telemetry"
        self.lock_log = Path(self.misc_dir) / "lock.log"

        self._orig_env = os.environ.copy()
        os.environ["AET_REPORTS_DIR"] = str(self.reports_dir)
        os.environ["AET_TELEMETRY_ARCHIVE_DIR"] = str(self.telemetry_dir)
        os.environ["AET_INTEGRATION_LOCK_LOG"] = str(self.lock_log)

        fake_bin_dir, self.adapter = _install_fake_cli(self.misc_dir)
        os.environ["PATH"] = str(fake_bin_dir) + os.pathsep + os.environ.get("PATH", "")

        _init_git_repo(self.repo_root, self.origin_root)
        Path(self.repo_root, ".agents").mkdir(parents=True, exist_ok=True)
        _write_test_workflow(self.repo_root)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._orig_env)
        self._tmp_repo.cleanup()
        self._tmp_origin.cleanup()
        self._tmp_misc.cleanup()

    def test_three_independent_tasks_flush_once_at_end_of_run(self):
        """Three independent tasks produce exactly one validate_command call at end of run and all merge."""
        counter_file = Path(self.misc_dir) / "val_counter.txt"
        val_script = Path(self.misc_dir) / "validate.py"
        val_script.write_text(
            f"import sys\n"
            f"with open({str(counter_file)!r}, 'a', encoding='utf-8') as f:\n"
            f"    f.write('validated\\n')\n"
            f"sys.exit(0)\n",
            encoding="utf-8",
        )

        Path(self.repo_root, ".agents", "aet-config.json").write_text(
            json.dumps(
                {
                    "trunk_branch": "main",
                    "integration_branch": "epic-01",
                    "integration_mode": "single-pr",
                    "validate_command": f"{sys.executable} {val_script}",
                }
            ),
            encoding="utf-8",
        )

        plan_1 = _write_plan(self.repo_root, "task-1")
        plan_2 = _write_plan(self.repo_root, "task-2")
        plan_3 = _write_plan(self.repo_root, "task-3")

        subprocess.run(["git", "-C", self.repo_root, "add", "."], check=True)
        subprocess.run(
            ["git", "-C", self.repo_root, "commit", "-q", "-m", "init plans"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", self.repo_root, "update-ref", "refs/remotes/origin/main", "HEAD"],
            check=True,
        )
        _create_integration_branch(self.repo_root, "epic-01")

        queue_file = os.path.join(self.repo_root, ".agents", "aet-queue")
        backend = orchestrator._make_backend(queue_file)
        backend.save(
            [
                {"id": "task-1", "state": "ready", "plan_file": plan_1},
                {"id": "task-2", "state": "ready", "plan_file": plan_2},
                {"id": "task-3", "state": "ready", "plan_file": plan_3},
            ]
        )

        args = argparse.Namespace(
            queue_file=queue_file,
            repo_root=self.repo_root,
            base="epic-01",
            isolation="standard",
            max_jobs=3,
            task_timeout=3600,
            heartbeat_interval=60,
            on_failure="triage",
            run_id="run-three-tasks",
        )

        exit_code = orchestrator.run_batch(args, self.adapter)
        self.assertEqual(exit_code, 0)

        # Exactly ONE validate_command call at end of run for the batch of 3 tasks
        self.assertTrue(counter_file.exists())
        val_lines = counter_file.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(val_lines), 1, f"Expected 1 validation call, got {len(val_lines)}: {val_lines}")

        # All 3 tasks must be merged
        for tid in ["task-1", "task-2", "task-3"]:
            rec = _get_task(backend, queue_file, tid)
            self.assertEqual(rec["state"], "merged", f"Task {tid} should be merged")
            self.assertIsNone(rec.get("train"), f"Task {tid} should have train marker cleared")

        # Verify commits are present on origin/epic-01
        log_res = subprocess.run(
            ["git", "-C", self.repo_root, "log", "origin/epic-01", "--oneline"],
            capture_output=True,
            text=True,
            check=True,
        )
        for tid in ["task-1", "task-2", "task-3"]:
            self.assertIn(f"Integrate {tid}", log_res.stdout)

        # Verify batch verdict recorded
        slug = telemetry.derive_project_slug(self.repo_root)
        batch_verdict_path = self.reports_dir / slug / "_train" / "epic-01" / "batch.json"
        self.assertTrue(batch_verdict_path.exists())
        verdicts = json.loads(batch_verdict_path.read_text(encoding="utf-8"))
        self.assertEqual(len(verdicts), 1)
        self.assertEqual(verdicts[0]["kind"], "batch")
        self.assertEqual(verdicts[0]["verdict"], "pass")
        self.assertEqual(verdicts[0]["task_ids"], ["task-1", "task-2", "task-3"])

    def test_task_b_blocked_by_staged_task_a_triggers_flush_and_starts(self):
        """Task B blocked by staged Task A triggers flush, unblocking Task B to start and complete in the same run."""
        Path(self.repo_root, ".agents", "aet-config.json").write_text(
            json.dumps(
                {
                    "trunk_branch": "main",
                    "integration_branch": "epic-01",
                    "integration_mode": "single-pr",
                    "validate_command": "true",
                }
            ),
            encoding="utf-8",
        )

        plan_a = _write_plan(self.repo_root, "task-a", blocks=["task-b"])
        plan_b = _write_plan(self.repo_root, "task-b", blocked_by=["task-a"])

        subprocess.run(["git", "-C", self.repo_root, "add", "."], check=True)
        subprocess.run(
            ["git", "-C", self.repo_root, "commit", "-q", "-m", "init plans"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", self.repo_root, "update-ref", "refs/remotes/origin/main", "HEAD"],
            check=True,
        )
        _create_integration_branch(self.repo_root, "epic-01")

        queue_file = os.path.join(self.repo_root, ".agents", "aet-queue")
        backend = orchestrator._make_backend(queue_file)
        backend.save(
            [
                {"id": "task-a", "state": "ready", "plan_file": plan_a, "blocks": ["task-b"]},
                {"id": "task-b", "state": "blocked", "plan_file": plan_b, "blocked_by": ["task-a"]},
            ]
        )

        args = argparse.Namespace(
            queue_file=queue_file,
            repo_root=self.repo_root,
            base="epic-01",
            isolation="standard",
            max_jobs=2,
            task_timeout=3600,
            heartbeat_interval=60,
            on_failure="triage",
            run_id="run-dep-chain",
        )

        exit_code = orchestrator.run_batch(args, self.adapter)
        self.assertEqual(exit_code, 0)

        # Both tasks should be merged at the end of the run
        rec_a = _get_task(backend, queue_file, "task-a")
        rec_b = _get_task(backend, queue_file, "task-b")
        self.assertEqual(rec_a["state"], "merged")
        self.assertEqual(rec_b["state"], "merged")

        # Verify both commits exist on origin/epic-01
        log_res = subprocess.run(
            ["git", "-C", self.repo_root, "log", "origin/epic-01", "--oneline"],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertIn("Integrate task-a", log_res.stdout)
        self.assertIn("Integrate task-b", log_res.stdout)

    def test_no_validation_subprocess_starts_while_integration_lock_held(self):
        """No validation subprocess runs while integration_lock is held."""
        val_log = Path(self.misc_dir) / "val_timing.log"
        lock_file_path = Path(self.repo_root) / ".agents" / "integration.lock"

        # The validation script asserts that it can acquire integration.lock in non-blocking mode.
        # If integration_lock was held by the parent process, fcntl.flock would fail with BlockingIOError!
        val_script = Path(self.misc_dir) / "instrumented_validate.py"
        val_script.write_text(
            f"import fcntl, os, sys, time, json\n"
            f"lock_path = {str(lock_file_path)!r}\n"
            f"val_log = {str(val_log)!r}\n"
            f"start = time.time()\n"
            f"lock_held_by_parent = False\n"
            f"if os.path.exists(lock_path):\n"
            f"    with open(lock_path, 'r') as f:\n"
            f"        try:\n"
            f"            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)\n"
            f"            fcntl.flock(f.fileno(), fcntl.LOCK_UN)\n"
            f"        except (BlockingIOError, OSError):\n"
            f"            lock_held_by_parent = True\n"
            f"time.sleep(0.05)\n"
            f"end = time.time()\n"
            f"with open(val_log, 'a', encoding='utf-8') as f:\n"
            f"    f.write(json.dumps({{'start': start, 'end': end, 'lock_held': lock_held_by_parent}}) + '\\n')\n"
            f"if lock_held_by_parent:\n"
            f"    sys.exit(1)\n"
            f"sys.exit(0)\n",
            encoding="utf-8",
        )

        Path(self.repo_root, ".agents", "aet-config.json").write_text(
            json.dumps(
                {
                    "trunk_branch": "main",
                    "integration_branch": "epic-01",
                    "integration_mode": "single-pr",
                    "validate_command": f"{sys.executable} {val_script}",
                }
            ),
            encoding="utf-8",
        )

        plan_1 = _write_plan(self.repo_root, "task-1")

        subprocess.run(["git", "-C", self.repo_root, "add", "."], check=True)
        subprocess.run(
            ["git", "-C", self.repo_root, "commit", "-q", "-m", "init plans"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", self.repo_root, "update-ref", "refs/remotes/origin/main", "HEAD"],
            check=True,
        )
        _create_integration_branch(self.repo_root, "epic-01")

        queue_file = os.path.join(self.repo_root, ".agents", "aet-queue")
        backend = orchestrator._make_backend(queue_file)
        backend.save([{"id": "task-1", "state": "ready", "plan_file": plan_1}])

        args = argparse.Namespace(
            queue_file=queue_file,
            repo_root=self.repo_root,
            base="epic-01",
            isolation="standard",
            max_jobs=1,
            task_timeout=3600,
            heartbeat_interval=60,
            on_failure="triage",
            run_id="run-lock-check",
        )

        exit_code = orchestrator.run_batch(args, self.adapter)
        self.assertEqual(exit_code, 0)

        # Validation ran and confirmed lock was NOT held
        self.assertTrue(val_log.exists())
        val_entry = json.loads(val_log.read_text(encoding="utf-8").strip())
        self.assertFalse(val_entry["lock_held"], "Validation should never run while integration_lock is held")

        # Double check with the lock log that timing intervals did not overlap
        events = []
        if self.lock_log.exists():
            for line in self.lock_log.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    events.append(json.loads(line))

        holds = []
        open_by_pid = {}
        for ev in events:
            pid = ev["pid"]
            if ev["event"] == "acquired":
                open_by_pid[pid] = ev["time"]
            elif ev["event"] == "releasing":
                start_t = open_by_pid.pop(pid, 0.0)
                holds.append((start_t, ev["time"]))

        val_start = val_entry["start"]
        val_end = val_entry["end"]
        for lock_start, lock_end in holds:
            overlap = max(lock_start, val_start) < min(lock_end, val_end)
            self.assertFalse(
                overlap,
                f"Overlap detected: validation [{val_start}, {val_end}] vs lock hold [{lock_start}, {lock_end}]",
            )

    def test_red_flush_leaves_staged_tasks_awaiting_merge_integration_branch_unmoved(self):
        """A red flush halts integration fail-closed: staged tasks stay awaiting_merge, branch unmoved."""
        Path(self.repo_root, ".agents", "aet-config.json").write_text(
            json.dumps(
                {
                    "trunk_branch": "main",
                    "integration_branch": "epic-01",
                    "integration_mode": "single-pr",
                    "validate_command": "false",
                }
            ),
            encoding="utf-8",
        )

        plan_1 = _write_plan(self.repo_root, "task-1")
        plan_2 = _write_plan(self.repo_root, "task-2")

        subprocess.run(["git", "-C", self.repo_root, "add", "."], check=True)
        subprocess.run(
            ["git", "-C", self.repo_root, "commit", "-q", "-m", "init plans"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", self.repo_root, "update-ref", "refs/remotes/origin/main", "HEAD"],
            check=True,
        )
        _create_integration_branch(self.repo_root, "epic-01")

        orig_tip = subprocess.run(
            ["git", "-C", self.repo_root, "rev-parse", "origin/epic-01"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        queue_file = os.path.join(self.repo_root, ".agents", "aet-queue")
        backend = orchestrator._make_backend(queue_file)
        backend.save(
            [
                {"id": "task-1", "state": "ready", "plan_file": plan_1},
                {"id": "task-2", "state": "ready", "plan_file": plan_2},
            ]
        )

        args = argparse.Namespace(
            queue_file=queue_file,
            repo_root=self.repo_root,
            base="epic-01",
            isolation="standard",
            max_jobs=2,
            task_timeout=3600,
            heartbeat_interval=60,
            on_failure="triage",
            run_id="run-red-flush",
        )

        # Batch run will fail due to red flush halt
        exit_code = orchestrator.run_batch(args, self.adapter)
        self.assertNotEqual(exit_code, 0)

        # Both tasks must remain awaiting_merge with their train markers intact
        rec_1 = _get_task(backend, queue_file, "task-1")
        rec_2 = _get_task(backend, queue_file, "task-2")
        self.assertEqual(rec_1["state"], "awaiting_merge")
        self.assertEqual(rec_2["state"], "awaiting_merge")
        self.assertIsNotNone(rec_1.get("train"))
        self.assertIsNotNone(rec_2.get("train"))

        # Integration branch on origin must be unmoved
        curr_tip = subprocess.run(
            ["git", "-C", self.repo_root, "rev-parse", "origin/epic-01"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        self.assertEqual(curr_tip, orig_tip, "Integration branch should not move on red flush")


if __name__ == "__main__":
    unittest.main()
