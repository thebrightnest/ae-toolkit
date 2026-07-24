"""Tests for single-pr integration serialization and failure handling.

Covers the local advisory integration lock (ADR-045, R-18) and the
Integration Failure engine-level outcome (R-19).
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import pytest

from aet import evidence as ev_module
from aet import integration_lock, telemetry
from aet.cli_adapter import CLIAdapter

_ORCHESTRATOR_BIN = Path(__file__).parents[2] / "src" / "aet" / "cli" / "orchestrator.py"
_orchestrator_loader = importlib.machinery.SourceFileLoader(
    "orchestrator", str(_ORCHESTRATOR_BIN)
)
_spec = importlib.util.spec_from_loader("orchestrator", _orchestrator_loader)
orchestrator = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(orchestrator)

pytestmark = pytest.mark.xdist_group("orchestrator")

_FAKE_ADAPTER = CLIAdapter(
    name="test",
    bin="echo",
    prompt_flag="-p",
    workdir_flag=None,
    headless_flag=None,
)


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


def _write_plan(repo_root: str, task_id: str) -> str:
    plan_file = os.path.join(repo_root, "docs", "plans", f"{task_id}-plan.md")
    Path(plan_file).parent.mkdir(parents=True, exist_ok=True)
    Path(plan_file).write_text(
        f"---\nid: {task_id}\nworkflow: test\n---\n\n# {task_id}\n\n_Stage: plan-approved_\n",
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


def _add_commit_to_worktree(worktree_dir: str, filename: str, content: str) -> None:
    Path(worktree_dir, filename).write_text(content, encoding="utf-8")
    subprocess.run(["git", "-C", worktree_dir, "add", "."], check=True)
    subprocess.run(
        ["git", "-C", worktree_dir, "commit", "-q", "-m", f"add {filename}"],
        check=True,
    )


def _write_qa_verdict(repo_root: str, task_id: str) -> None:
    """Write a passing qa verdict for task_id to the canonical evidence path."""
    project_slug = telemetry.derive_project_slug(repo_root)
    record = {
        "task_id": task_id,
        "stage": "qa-complete",
        "skill": "aet-qa",
        "verdict": "pass",
        "summary": "fake qa passed",
        "generated_at": telemetry.iso_now(),
        "tree_hash": "",
        "test_command": "make validate",
        "tests_total": 1,
        "tests_passed": 1,
        "tests_failed": 0,
    }
    ev_module.write_verdict(task_id, "qa", record, project_slug=project_slug)


def _read_lock_log(log_path: str) -> list[dict]:
    events = []
    if not os.path.exists(log_path):
        return events
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            events.append(json.loads(line))
    return events


def _assert_no_overlapping_hold(events: list[dict]) -> None:
    """Fail if any two lock holds overlap.

    Events alternate acquired/releasing per pid; a releasing without a matching
    acquired is treated as the end of a hold started before logging began.
    """
    holds: list[tuple[float, float, int]] = []
    open_by_pid: dict[int, float] = {}
    for ev in events:
        pid = ev["pid"]
        if ev["event"] == "acquired":
            open_by_pid[pid] = ev["time"]
        elif ev["event"] == "releasing":
            start = open_by_pid.pop(pid, 0.0)
            holds.append((start, ev["time"], pid))
    for i, (s1, e1, p1) in enumerate(holds):
        for s2, e2, p2 in holds[i + 1 :]:
            if max(s1, s2) < min(e1, e2):
                raise AssertionError(
                    f"Overlapping lock holds: pid {p1} [{s1}, {e1}] and pid {p2} [{s2}, {e2}]"
                )


class TestIntegrationLock(unittest.TestCase):
    def test_contended_acquisition_is_ordered(self):
        """Many threads acquire the lock in strict serial order."""
        with tempfile.TemporaryDirectory() as repo_root:
            order: list[int] = []
            barrier = threading.Barrier(4)

            def worker(idx: int) -> None:
                barrier.wait()
                with integration_lock.integration_lock(repo_root):
                    order.append(idx)

            threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            self.assertEqual(len(order), 4)
            self.assertEqual(sorted(order), list(range(4)))

    def test_lock_released_on_exception(self):
        """The lock is released when the protected body raises."""
        with tempfile.TemporaryDirectory() as repo_root:

            def _body() -> None:
                with integration_lock.integration_lock(repo_root):
                    raise RuntimeError("boom")

            self.assertRaises(RuntimeError, _body)
            # A second acquisition should succeed immediately, proving release.
            with integration_lock.integration_lock(repo_root):
                pass

    def test_lock_log_records_no_overlap(self):
        """Logged lock holds never overlap."""
        with tempfile.TemporaryDirectory() as repo_root, tempfile.NamedTemporaryFile(
            mode="w", delete=False
        ) as log:
            log_path = log.name
        os.environ["AET_INTEGRATION_LOCK_LOG"] = log_path
        try:
            barrier = threading.Barrier(3)

            def worker() -> None:
                barrier.wait()
                with integration_lock.integration_lock(repo_root):
                    time.sleep(0.01)

            threads = [threading.Thread(target=worker) for _ in range(3)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            events = _read_lock_log(log_path)
            self.assertEqual(len(events), 6)  # 3 acquired + 3 releasing
            _assert_no_overlapping_hold(events)
        finally:
            os.environ.pop("AET_INTEGRATION_LOCK_LOG", None)
            try:
                os.unlink(log_path)
            except FileNotFoundError:
                pass


class TestIntegrationSinglePrTask(unittest.TestCase):
    def test_successful_integration_rebases_validates_merges_pushes(self):
        """Happy path: rebase, validate, squash-merge, push."""
        self.maxDiff = None
        with tempfile.TemporaryDirectory() as repo_root, tempfile.TemporaryDirectory() as origin_root:
            _init_git_repo(repo_root, origin_root)
            Path(repo_root, ".agents").mkdir(parents=True, exist_ok=True)
            Path(repo_root, ".agents", "aet-work.json").write_text(
                json.dumps(
                    {
                        "trunk_branch": "main",
                        "integration_branch": "epic-01",
                        "integration_mode": "single-pr",
                    }
                ),
                encoding="utf-8",
            )
            plan_a = _write_plan(repo_root, "task-a")
            subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
            subprocess.run(
                ["git", "-C", repo_root, "commit", "-q", "-m", "add plans"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", repo_root, "update-ref", "refs/remotes/origin/main", "HEAD"],
                check=True,
            )
            _create_integration_branch(repo_root, "epic-01")

            worktree_a = orchestrator.create_worktree(
                repo_root, "task-a", base_branch="origin/epic-01"
            )
            _add_commit_to_worktree(worktree_a, "task-a.txt", "task-a work")
            _write_qa_verdict(repo_root, "task-a")

            with patch.object(orchestrator, "_validate_after_rebase", return_value=(True, "")):
                result = orchestrator._integrate_single_pr_task(
                    repo_root=repo_root,
                    task_id="task-a",
                    integration_branch="epic-01",
                    worktree_dir=worktree_a,
                    plan_file=plan_a,
                )

            self.assertTrue(result)
            remote_heads = subprocess.run(
                ["git", "-C", repo_root, "ls-remote", "--heads", "origin"],
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertIn("refs/heads/epic-01", remote_heads.stdout)
            self.assertNotIn("refs/heads/task-a", remote_heads.stdout)
            log = subprocess.run(
                ["git", "-C", repo_root, "log", "origin/epic-01", "--oneline"],
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertIn("Integrate task-a", log.stdout)

    def test_rebase_conflict_is_integration_failure_and_releases_lock(self):
        """A rebase conflict raises IntegrationFailureError and releases the lock."""
        with tempfile.TemporaryDirectory() as repo_root, tempfile.TemporaryDirectory() as origin_root:
            _init_git_repo(repo_root, origin_root)
            Path(repo_root, ".agents").mkdir(parents=True, exist_ok=True)
            Path(repo_root, ".agents", "aet-work.json").write_text(
                json.dumps(
                    {
                        "trunk_branch": "main",
                        "integration_branch": "epic-01",
                        "integration_mode": "single-pr",
                    }
                ),
                encoding="utf-8",
            )
            _write_plan(repo_root, "task-a")
            # Create a file on main that will conflict.
            Path(repo_root, "shared.txt").write_text("main content", encoding="utf-8")
            subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
            subprocess.run(
                ["git", "-C", repo_root, "commit", "-q", "-m", "add plans and shared"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", repo_root, "update-ref", "refs/remotes/origin/main", "HEAD"],
                check=True,
            )
            _create_integration_branch(repo_root, "epic-01")

            worktree_a = orchestrator.create_worktree(
                repo_root, "task-a", base_branch="origin/epic-01"
            )
            Path(worktree_a, "shared.txt").write_text("task-a content", encoding="utf-8")
            subprocess.run(["git", "-C", worktree_a, "add", "."], check=True)
            subprocess.run(
                ["git", "-C", worktree_a, "commit", "-q", "-m", "task-a change"],
                check=True,
            )

            # Change shared.txt on epic-01 to guarantee a conflict on rebase.
            subprocess.run(["git", "-C", repo_root, "checkout", "-q", "epic-01"], check=True)
            Path(repo_root, "shared.txt").write_text("epic content", encoding="utf-8")
            subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
            subprocess.run(
                ["git", "-C", repo_root, "commit", "-q", "-m", "epic change"],
                check=True,
            )
            subprocess.run(["git", "-C", repo_root, "push", "-q", "origin", "epic-01"], check=True)
            subprocess.run(
                ["git", "-C", repo_root, "update-ref", "refs/remotes/origin/epic-01", "HEAD"],
                check=True,
            )
            subprocess.run(["git", "-C", repo_root, "checkout", "-q", "main"], check=True)

            with self.assertRaises(orchestrator.IntegrationFailureError):
                orchestrator._integrate_single_pr_task(
                    repo_root=repo_root,
                    task_id="task-a",
                    integration_branch="epic-01",
                    worktree_dir=worktree_a,
                )

            # Lock must be released: a second integration should not block forever.
            with integration_lock.integration_lock(repo_root):
                pass

    def test_validation_failure_is_integration_failure_and_releases_lock(self):
        """A post-rebase validation failure raises IntegrationFailureError."""
        with tempfile.TemporaryDirectory() as repo_root, tempfile.TemporaryDirectory() as origin_root:
            _init_git_repo(repo_root, origin_root)
            Path(repo_root, ".agents").mkdir(parents=True, exist_ok=True)
            Path(repo_root, ".agents", "aet-work.json").write_text(
                json.dumps(
                    {
                        "trunk_branch": "main",
                        "integration_branch": "epic-01",
                        "integration_mode": "single-pr",
                    }
                ),
                encoding="utf-8",
            )
            _write_plan(repo_root, "task-a")
            subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
            subprocess.run(
                ["git", "-C", repo_root, "commit", "-q", "-m", "add plans"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", repo_root, "update-ref", "refs/remotes/origin/main", "HEAD"],
                check=True,
            )
            _create_integration_branch(repo_root, "epic-01")

            worktree_a = orchestrator.create_worktree(
                repo_root, "task-a", base_branch="origin/epic-01"
            )
            _add_commit_to_worktree(worktree_a, "task-a.txt", "task-a work")

            with patch.object(
                orchestrator, "_validate_after_rebase", return_value=(False, "tests failed")
            ):
                with self.assertRaises(orchestrator.IntegrationFailureError):
                    orchestrator._integrate_single_pr_task(
                        repo_root=repo_root,
                        task_id="task-a",
                        integration_branch="epic-01",
                        worktree_dir=worktree_a,
                    )

            with integration_lock.integration_lock(repo_root):
                pass

    def test_integration_failure_marked_on_task_record(self):
        """Integration failure marks the task failed with an integration signature."""
        with tempfile.TemporaryDirectory() as repo_root, tempfile.TemporaryDirectory() as origin_root:
            _init_git_repo(repo_root, origin_root)
            Path(repo_root, ".agents").mkdir(parents=True, exist_ok=True)
            Path(repo_root, ".agents", "aet-work.json").write_text(
                json.dumps(
                    {
                        "trunk_branch": "main",
                        "integration_branch": "epic-01",
                        "integration_mode": "single-pr",
                    }
                ),
                encoding="utf-8",
            )
            plan_a = _write_plan(repo_root, "task-a")
            subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
            subprocess.run(
                ["git", "-C", repo_root, "commit", "-q", "-m", "add plans"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", repo_root, "update-ref", "refs/remotes/origin/main", "HEAD"],
                check=True,
            )
            _create_integration_branch(repo_root, "epic-01")

            worktree_a = orchestrator.create_worktree(
                repo_root, "task-a", base_branch="origin/epic-01"
            )
            _add_commit_to_worktree(worktree_a, "task-a.txt", "task-a work")

            queue_file = os.path.join(repo_root, ".agents", "work-queue.json")
            backend = orchestrator._make_backend(queue_file)
            backend.save([{"id": "task-a", "state": "in_progress", "plan_file": plan_a}])

            with patch.object(
                orchestrator, "_validate_after_rebase", return_value=(False, "tests failed")
            ):
                with self.assertRaises(orchestrator.IntegrationFailureError):
                    orchestrator._integrate_single_pr_task(
                        repo_root=repo_root,
                        task_id="task-a",
                        integration_branch="epic-01",
                        worktree_dir=worktree_a,
                        backend=backend,
                    )

            orchestrator._mark_integration_failure(
                backend,
                queue_file,
                "task-a",
                "in_progress",
                "validation failed after rebase for task-a:\ntests failed",
            )

            queue = backend.load()["queue"]
            task = next(t for t in queue if t["id"] == "task-a")
            self.assertEqual(task["state"], "failed")
            self.assertIn("integration_failure", task)
            self.assertIn("signature", task["integration_failure"])
            self.assertIn("tests failed", task["integration_failure"]["reason"])
            self.assertNotIn("failure_signatures", task)


class TestBatchIntegrationSerialization(unittest.TestCase):
    def test_max_jobs_three_integration_steps_serialize(self):
        """R-18: with --max-jobs 3, integration steps do not interleave."""
        self.maxDiff = None
        with (
            tempfile.TemporaryDirectory() as repo_root,
            tempfile.TemporaryDirectory() as origin_root,
            tempfile.NamedTemporaryFile(mode="w", delete=False) as log,
        ):
            log_path = log.name

        os.environ["AET_INTEGRATION_LOCK_LOG"] = log_path
        original_path = os.environ.get("PATH", "")
        try:
            _init_git_repo(repo_root, origin_root)
            Path(repo_root, ".agents").mkdir(parents=True, exist_ok=True)
            Path(repo_root, ".agents", "aet-work.json").write_text(
                json.dumps(
                    {
                        "trunk_branch": "main",
                        "integration_branch": "epic-01",
                        "integration_mode": "single-pr",
                    }
                ),
                encoding="utf-8",
            )

            _write_test_workflow(repo_root)
            plans = [_write_plan(repo_root, f"task-{i}") for i in range(3)]
            subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
            subprocess.run(
                ["git", "-C", repo_root, "commit", "-q", "-m", "add plans and config"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", repo_root, "update-ref", "refs/remotes/origin/main", "HEAD"],
                check=True,
            )
            _create_integration_branch(repo_root, "epic-01")

            queue_file = os.path.join(repo_root, ".agents", "work-queue.json")
            backend = orchestrator._make_backend(queue_file)
            backend.save(
                [
                    {"id": f"task-{i}", "state": "ready", "plan_file": plans[i]}
                    for i in range(3)
                ]
            )

            # The temporary repo has no Makefile, so override the post-rebase
            # validation command to a no-op that always succeeds.
            os.environ["AET_INTEGRATION_VALIDATE_CMD"] = "true"

            # Fake adapter binary: create a commit in the worktree and exit 0.
            # Named "claude" and placed on PATH so the spawned subprocess can
            # resolve it through the normal CLIAdapter lookup.
            fake_bin_dir = Path(origin_root).parent / "fake-bin"
            fake_bin_dir.mkdir(exist_ok=True)
            fake_cli = fake_bin_dir / "claude"
            fake_cli.write_text(
                "#!/usr/bin/env python3\n"
                "import os, subprocess, pathlib, json\n"
                "wt = os.environ.get('AET_WORKTREE', '.')\n"
                "name = os.environ.get('AET_TASK_ID', 'task')\n"
                "counter_file = pathlib.Path(wt, '.stage-counter')\n"
                "counter = int(counter_file.read_text().strip()) if counter_file.exists() else 0\n"
                "counter += 1\n"
                "counter_file.write_text(str(counter))\n"
                "pathlib.Path(wt, f'{name}-{counter}.txt').write_text(f'stage {counter}')\n"
                "subprocess.run(['git', '-C', wt, 'add', '.'], check=True)\n"
                "subprocess.run(['git', '-C', wt, 'commit', '-q', '-m', f'stage {counter}'], check=True)\n"
                "from aet import evidence, telemetry\n"
                "record = {\n"
                "    'task_id': name,\n"
                "    'stage': 'qa-complete',\n"
                "    'skill': 'aet-qa',\n"
                "    'verdict': 'pass',\n"
                "    'summary': 'fake qa passed',\n"
                "    'generated_at': telemetry.iso_now(),\n"
                "    'tree_hash': '',\n"
                "    'test_command': 'make validate',\n"
                "    'tests_total': 1,\n"
                "    'tests_passed': 1,\n"
                "    'tests_failed': 0,\n"
                "}\n"
                "evidence.write_verdict(name, 'qa', record, worktree_dir=wt)\n",
                encoding="utf-8",
            )
            fake_cli.chmod(0o755)
            os.environ["PATH"] = str(fake_bin_dir) + os.pathsep + os.environ.get("PATH", "")

            adapter = CLIAdapter(
                name="claude",
                bin="claude",
                prompt_flag="-p",
                workdir_flag=None,
                headless_flag="--dangerously-skip-permissions",
            )

            args = orchestrator.argparse.Namespace(
                queue_file=queue_file,
                repo_root=repo_root,
                base="epic-01",
                isolation="standard",
                max_jobs=3,
                task_timeout=3600,
                stall_timeout=300,
                heartbeat_interval=60,
                on_failure="triage",
                run_id="test-run",
            )

            exit_code = orchestrator.run_batch(args, adapter)
            self.assertEqual(exit_code, 0)

            events = _read_lock_log(log_path)
            # Each task should produce one acquired + one releasing event.
            acquired = [e for e in events if e["event"] == "acquired"]
            releasing = [e for e in events if e["event"] == "releasing"]
            self.assertEqual(len(acquired), 3)
            self.assertEqual(len(releasing), 3)
            _assert_no_overlapping_hold(events)
        finally:
            os.environ.pop("AET_INTEGRATION_LOCK_LOG", None)
            os.environ.pop("AET_INTEGRATION_VALIDATE_CMD", None)
            os.environ["PATH"] = original_path
            try:
                os.unlink(log_path)
            except FileNotFoundError:
                pass


if __name__ == "__main__":
    unittest.main()
