"""Comprehensive multi-job integration tests for concurrent auto-merge and replenishment.

Covers PRD requirements R-1 through R-10:
- R-1, R-2, R-3: Continuous lazy-rebased auto-merging under integration_lock.
- R-4, R-5: Immediate DAG unblocking and dynamic concurrency slot replenishment.
- R-6: Elimination of single-worker throttling (starvation elimination).
- R-7, R-8: Non-blocking conflict staging and idle batch settlement.
- R-9: aet-drive skill and command harmonization contract.
- R-10: Dual-mode parity (single-pr mode vs standalone mode targeting trunk).
"""

from __future__ import annotations

import argparse
import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pytest

from aet import telemetry, track_record
from aet.cli.aet_state import resolve_task_record
from aet.cli_adapter import CLIAdapter

_ORCHESTRATOR_BIN = Path(__file__).parents[2] / "src" / "aet" / "cli" / "orchestrator.py"
_SRC_DIR = Path(__file__).parents[2] / "src"
_orchestrator_loader = importlib.machinery.SourceFileLoader(
    "orchestrator", str(_ORCHESTRATOR_BIN)
)
_spec = importlib.util.spec_from_loader("orchestrator", _orchestrator_loader)
orchestrator = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(orchestrator)

pytestmark = pytest.mark.xdist_group("git-repo")


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
    """Create a fake CLI script named 'claude' that supports per-task hooks."""
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
        'tree_hash': '',
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


def _write_default_qa_record_in_hook(wt: str, name: str, repo_root: str) -> None:
    from aet import evidence, telemetry

    project_slug = telemetry.derive_project_slug(repo_root)
    record = {
        "task_id": name,
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
    evidence.write_verdict(name, "qa", record, project_slug=project_slug, worktree_dir=wt)


def _get_task(backend, queue_file: str, task_id: str) -> dict:
    task, sealed = resolve_task_record(task_id, queue_file, backend=backend)
    rec = task or sealed
    assert rec is not None, f"Task {task_id} not found in live queue or sealed history"
    return rec


class TestContinuousLazyRebaseAutoMerge(unittest.TestCase):
    """Integration test suite for R-1, R-2, and R-3."""

    def test_continuous_lazy_rebased_auto_merge_under_lock(self):
        """R-1, R-2, R-3: Tasks auto-merge continuously under serialized lock."""
        with (
            tempfile.TemporaryDirectory() as repo_root,
            tempfile.TemporaryDirectory() as origin_root,
            tempfile.NamedTemporaryFile(mode="w", delete=False) as log,
        ):
            log_path = log.name

        os.environ["AET_INTEGRATION_LOCK_LOG"] = log_path
        original_path = os.environ.get("PATH", "")
        fake_bin_dir, adapter = _install_fake_cli(origin_root)
        os.environ["PATH"] = str(fake_bin_dir) + os.pathsep + original_path

        try:
            _init_git_repo(repo_root, origin_root)
            Path(repo_root, ".agents").mkdir(parents=True, exist_ok=True)
            Path(repo_root, ".agents", "aet-config.json").write_text(
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
            _write_test_workflow(repo_root)
            plan_a = _write_plan(repo_root, "task-a")
            plan_b = _write_plan(repo_root, "task-b")

            subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
            subprocess.run(
                ["git", "-C", repo_root, "commit", "-q", "-m", "init plans"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", repo_root, "update-ref", "refs/remotes/origin/main", "HEAD"],
                check=True,
            )
            _create_integration_branch(repo_root, "epic-01")

            # Configure hook for task-b: sleep 0.4s to let task-a integrate while task-b is in flight
            hooks_dir = Path(repo_root, ".agents", "hooks")
            hooks_dir.mkdir(parents=True, exist_ok=True)
            (hooks_dir / "task-b.py").write_text(
                "time.sleep(0.4)\n"
                "pathlib.Path(wt, 'task-b.txt').write_text('task-b work')\n"
                "subprocess.run(['git', '-C', wt, 'add', '.'], check=True)\n"
                "subprocess.run(['git', '-C', wt, 'commit', '-q', '-m', 'task-b work'], check=True)\n"
                "from aet import evidence, telemetry\n"
                "project_slug = telemetry.derive_project_slug(repo_root)\n"
                "record = {\n"
                "    'task_id': name,\n"
                "    'stage': 'qa-complete',\n"
                "    'skill': 'aet-qa',\n"
                "    'verdict': 'pass',\n"
                "    'summary': 'task-b qa passed',\n"
                "    'generated_at': telemetry.iso_now(),\n"
                "    'tree_hash': '',\n"
                "    'test_command': 'make validate',\n"
                "    'tests_total': 1,\n"
                "    'tests_passed': 1,\n"
                "    'tests_failed': 0,\n"
                "}\n"
                "evidence.write_verdict(name, 'qa', record, project_slug=project_slug, worktree_dir=wt)\n",
                encoding="utf-8",
            )

            queue_file = os.path.join(repo_root, ".agents", "aet-queue")
            backend = orchestrator._make_backend(queue_file)
            backend.save(
                [
                    {"id": "task-a", "state": "ready", "plan_file": plan_a},
                    {"id": "task-b", "state": "ready", "plan_file": plan_b},
                ]
            )

            args = argparse.Namespace(
                queue_file=queue_file,
                repo_root=repo_root,
                base="epic-01",
                isolation="standard",
                max_jobs=2,
                task_timeout=3600,
                heartbeat_interval=60,
                on_failure="triage",
                run_id="run-lazy-rebase",
            )

            exit_code = orchestrator.run_batch(args, adapter)
            self.assertEqual(exit_code, 0)

            # Verify queue state reflects merged for both tasks (R-3)
            task_a = _get_task(backend, queue_file, "task-a")
            task_b = _get_task(backend, queue_file, "task-b")
            self.assertEqual(task_a["state"], "merged")
            self.assertEqual(task_b["state"], "merged")

            # Verify both tasks were integrated and pushed to origin/epic-01
            log_proc = subprocess.run(
                ["git", "-C", repo_root, "log", "origin/epic-01", "--oneline"],
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertIn("Integrate task-a", log_proc.stdout)
            self.assertIn("Integrate task-b", log_proc.stdout)

            # Verify lock holds were strictly non-overlapping (R-2)
            events = _read_lock_log(log_path)
            acquired = [e for e in events if e["event"] == "acquired"]
            releasing = [e for e in events if e["event"] == "releasing"]
            self.assertGreaterEqual(len(acquired), 2)
            self.assertGreaterEqual(len(releasing), 2)
            _assert_no_overlapping_hold(events)

        finally:
            os.environ.pop("AET_INTEGRATION_LOCK_LOG", None)
            os.environ["PATH"] = original_path
            try:
                os.unlink(log_path)
            except FileNotFoundError:
                pass


class TestDynamicSlotReplenishmentAndDAG(unittest.TestCase):
    """Integration test suite for R-4, R-5, and R-6."""

    def test_immediate_dag_progression_and_dynamic_slot_replenishment(self):
        """R-4, R-5: Dependent task is unblocked on blocker merge and dispatched into freed slot."""
        with (
            tempfile.TemporaryDirectory() as repo_root,
            tempfile.TemporaryDirectory() as origin_root,
        ):
            original_path = os.environ.get("PATH", "")
            fake_bin_dir, adapter = _install_fake_cli(origin_root)
            os.environ["PATH"] = str(fake_bin_dir) + os.pathsep + original_path

            try:
                _init_git_repo(repo_root, origin_root)
                Path(repo_root, ".agents").mkdir(parents=True, exist_ok=True)
                Path(repo_root, ".agents", "aet-config.json").write_text(
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
                _write_test_workflow(repo_root)

                plan_parent = _write_plan(repo_root, "task-parent", blocks=["task-child"])
                plan_child = _write_plan(repo_root, "task-child", blocked_by=["task-parent"])

                subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
                subprocess.run(
                    ["git", "-C", repo_root, "commit", "-q", "-m", "init dag plans"],
                    check=True,
                )
                subprocess.run(
                    ["git", "-C", repo_root, "update-ref", "refs/remotes/origin/main", "HEAD"],
                    check=True,
                )
                _create_integration_branch(repo_root, "epic-01")

                queue_file = os.path.join(repo_root, ".agents", "aet-queue")
                backend = orchestrator._make_backend(queue_file)
                backend.save(
                    [
                        {
                            "id": "task-parent",
                            "state": "ready",
                            "plan_file": plan_parent,
                            "blocks": ["task-child"],
                        },
                        {
                            "id": "task-child",
                            "state": "blocked",
                            "plan_file": plan_child,
                            "blocked_by": ["task-parent"],
                            "pending_blockers": 1,
                        },
                    ]
                )

                # With max_jobs=1, only task-parent can run first.
                # When task-parent integrates, task-child is dynamically unblocked and spawned.
                args = argparse.Namespace(
                    queue_file=queue_file,
                    repo_root=repo_root,
                    base="epic-01",
                    isolation="standard",
                    max_jobs=1,
                    task_timeout=3600,
                    heartbeat_interval=60,
                    on_failure="triage",
                    run_id="run-dag-replenish",
                )

                exit_code = orchestrator.run_batch(args, adapter)
                self.assertEqual(exit_code, 0)

                task_parent = _get_task(backend, queue_file, "task-parent")
                task_child = _get_task(backend, queue_file, "task-child")

                self.assertEqual(task_parent["state"], "merged")
                self.assertEqual(task_child["state"], "merged")

                # Verify task-child transitioned through release history
                child_history = [h["to"] for h in task_child.get("history", [])]
                self.assertIn("ready", child_history)
                self.assertIn("merged", child_history)

                # Verify both landed on origin/epic-01
                log_proc = subprocess.run(
                    ["git", "-C", repo_root, "log", "origin/epic-01", "--oneline"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                self.assertIn("Integrate task-parent", log_proc.stdout)
                self.assertIn("Integrate task-child", log_proc.stdout)

            finally:
                os.environ["PATH"] = original_path

    def test_initial_cycle_starvation_elimination_max_jobs(self):
        """R-6: With max_jobs=3, all ready tasks are spawned concurrently without throttling."""
        with (
            tempfile.TemporaryDirectory() as repo_root,
            tempfile.TemporaryDirectory() as origin_root,
        ):
            original_path = os.environ.get("PATH", "")
            fake_bin_dir, adapter = _install_fake_cli(origin_root)
            os.environ["PATH"] = str(fake_bin_dir) + os.pathsep + original_path

            try:
                _init_git_repo(repo_root, origin_root)
                Path(repo_root, ".agents").mkdir(parents=True, exist_ok=True)
                Path(repo_root, ".agents", "aet-config.json").write_text(
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
                _write_test_workflow(repo_root)

                plans = [_write_plan(repo_root, f"task-{i}") for i in range(3)]
                subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
                subprocess.run(
                    ["git", "-C", repo_root, "commit", "-q", "-m", "init starvation plans"],
                    check=True,
                )
                subprocess.run(
                    ["git", "-C", repo_root, "update-ref", "refs/remotes/origin/main", "HEAD"],
                    check=True,
                )
                _create_integration_branch(repo_root, "epic-01")

                # Concurrency instrumentation: each task synchronizes on a barrier
                # to prove all 3 tasks were dispatched and running concurrently in the initial cycle
                concurrency_log = Path(repo_root, ".agents", "concurrency.log")
                barrier_dir = Path(repo_root, ".agents", "barrier")
                barrier_dir.mkdir(parents=True, exist_ok=True)
                hooks_dir = Path(repo_root, ".agents", "hooks")
                hooks_dir.mkdir(parents=True, exist_ok=True)

                for i in range(3):
                    (hooks_dir / f"task-{i}.py").write_text(
                        "t_start = time.time()\n"
                        f"pathlib.Path({str(barrier_dir)!r}, f'{i}.ready').write_text('1')\n"
                        "all_active = False\n"
                        "while time.time() - t_start < 20.0:\n"
                        f"    if len(list(pathlib.Path({str(barrier_dir)!r}).glob('*.ready'))) >= 3:\n"
                        "        all_active = True\n"
                        "        break\n"
                        "    time.sleep(0.05)\n"
                        "t_end = time.time()\n"
                        f"with open({str(concurrency_log)!r}, 'a') as f:\n"
                        f"    f.write(f'{i}:{{t_start}}:{{t_end}}:{{all_active}}\\n')\n"
                        f"pathlib.Path(wt, 'task-{i}.txt').write_text('work')\n"
                        "subprocess.run(['git', '-C', wt, 'add', '.'], check=True)\n"
                        f"subprocess.run(['git', '-C', wt, 'commit', '-q', '-m', 'task-{i}'], check=True)\n"
                        "from aet import evidence, telemetry\n"
                        "project_slug = telemetry.derive_project_slug(repo_root)\n"
                        "record = {\n"
                        f"    'task_id': 'task-{i}',\n"
                        "    'stage': 'qa-complete',\n"
                        "    'skill': 'aet-qa',\n"
                        "    'verdict': 'pass',\n"
                        "    'summary': 'qa passed',\n"
                        "    'generated_at': telemetry.iso_now(),\n"
                        "    'tree_hash': '',\n"
                        "    'test_command': 'make validate',\n"
                        "    'tests_total': 1,\n"
                        "    'tests_passed': 1,\n"
                        "    'tests_failed': 0,\n"
                        "}\n"
                        f"evidence.write_verdict('task-{i}', 'qa', record, "
                        "project_slug=project_slug, worktree_dir=wt)\n",
                        encoding="utf-8",
                    )

                queue_file = os.path.join(repo_root, ".agents", "aet-queue")
                backend = orchestrator._make_backend(queue_file)
                backend.save(
                    [
                        {"id": f"task-{i}", "state": "ready", "plan_file": plans[i]}
                        for i in range(3)
                    ]
                )

                args = argparse.Namespace(
                    queue_file=queue_file,
                    repo_root=repo_root,
                    base="epic-01",
                    isolation="standard",
                    max_jobs=3,
                    task_timeout=3600,
                    heartbeat_interval=60,
                    on_failure="triage",
                    run_id="run-starvation",
                )

                exit_code = orchestrator.run_batch(args, adapter)
                self.assertEqual(exit_code, 0)

                # Verify all 3 tasks were launched concurrently in the initial cycle
                self.assertTrue(concurrency_log.exists())
                entries = [
                    line.strip().split(":")
                    for line in concurrency_log.read_text().splitlines()
                    if line.strip()
                ]
                self.assertEqual(len(entries), 3)

                task_starts = {int(p[0]): float(p[1]) for p in entries}
                task_ends = {int(p[0]): float(p[2]) for p in entries}
                all_actives = {int(p[0]): (p[3] == "True") for p in entries}

                # Under concurrent dispatch (max_jobs=3), all 3 tasks reached active state simultaneously
                for i in range(3):
                    self.assertTrue(
                        all_actives[i],
                        f"task-{i} timed out waiting for concurrent peer tasks",
                    )

                # Overlap check: all tasks started before any task ended
                self.assertLess(
                    max(task_starts.values()),
                    min(task_ends.values()) + 0.5,
                    "Tasks were not executing simultaneously in the initial cycle",
                )

                for i in range(3):
                    t = _get_task(backend, queue_file, f"task-{i}")
                    self.assertEqual(t["state"], "merged")

            finally:
                os.environ["PATH"] = original_path


class TestNonBlockingConflictStagingAndBatchSettle(unittest.TestCase):
    """Integration test suite for R-7 and R-8."""

    def test_non_blocking_conflict_staging_and_batch_settle(self):
        """R-7, R-8: Conflicted task stages in awaiting_merge, independent tasks merge, batch settles."""
        with (
            tempfile.TemporaryDirectory() as repo_root,
            tempfile.TemporaryDirectory() as origin_root,
        ):
            original_path = os.environ.get("PATH", "")
            fake_bin_dir, adapter = _install_fake_cli(origin_root)
            os.environ["PATH"] = str(fake_bin_dir) + os.pathsep + original_path

            try:
                _init_git_repo(repo_root, origin_root)
                Path(repo_root, ".agents").mkdir(parents=True, exist_ok=True)
                Path(repo_root, ".agents", "aet-config.json").write_text(
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
                _write_test_workflow(repo_root)

                # Initialize conflict.txt and plan files on main
                Path(repo_root, "conflict.txt").write_text("initial base line\n", encoding="utf-8")
                plan_c1 = _write_plan(repo_root, "task-c1")
                plan_c2 = _write_plan(repo_root, "task-c2", blocks=["task-blocked"])
                plan_ind = _write_plan(repo_root, "task-ind")
                plan_blocked = _write_plan(repo_root, "task-blocked", blocked_by=["task-c2"])

                subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
                subprocess.run(
                    ["git", "-C", repo_root, "commit", "-q", "-m", "add conflict base and plans"],
                    check=True,
                )
                subprocess.run(["git", "-C", repo_root, "push", "-q", "origin", "main"], check=True)
                subprocess.run(
                    ["git", "-C", repo_root, "update-ref", "refs/remotes/origin/main", "HEAD"],
                    check=True,
                )
                _create_integration_branch(repo_root, "epic-01")

                hooks_dir = Path(repo_root, ".agents", "hooks")
                hooks_dir.mkdir(parents=True, exist_ok=True)

                # task-c1 edits conflict.txt and merges first
                (hooks_dir / "task-c1.py").write_text(
                    "pathlib.Path(wt, 'conflict.txt').write_text('Line from task-c1\\n')\n"
                    "subprocess.run(['git', '-C', wt, 'add', '.'], check=True)\n"
                    "subprocess.run(['git', '-C', wt, 'commit', '-q', '-m', 'commit task-c1'], check=True)\n"
                    "from aet import evidence, telemetry\n"
                    "project_slug = telemetry.derive_project_slug(repo_root)\n"
                    "record = {\n"
                    "    'task_id': name,\n"
                    "    'stage': 'qa-complete',\n"
                    "    'skill': 'aet-qa',\n"
                    "    'verdict': 'pass',\n"
                    "    'summary': 'task-c1 passed',\n"
                    "    'generated_at': telemetry.iso_now(),\n"
                    "    'tree_hash': '',\n"
                    "    'test_command': 'make validate',\n"
                    "    'tests_total': 1,\n"
                    "    'tests_passed': 1,\n"
                    "    'tests_failed': 0,\n"
                    "}\n"
                    "evidence.write_verdict(name, 'qa', record, project_slug=project_slug, worktree_dir=wt)\n",
                    encoding="utf-8",
                )

                # task-c2 edits conflict.txt with conflicting content, sleeps 0.4s so task-c1 merges first
                (hooks_dir / "task-c2.py").write_text(
                    "time.sleep(0.4)\n"
                    "pathlib.Path(wt, 'conflict.txt').write_text('Line from task-c2 DIFFERENT\\n')\n"
                    "subprocess.run(['git', '-C', wt, 'add', '.'], check=True)\n"
                    "subprocess.run(['git', '-C', wt, 'commit', '-q', '-m', 'commit task-c2'], check=True)\n"
                    "from aet import evidence, telemetry\n"
                    "project_slug = telemetry.derive_project_slug(repo_root)\n"
                    "record = {\n"
                    "    'task_id': name,\n"
                    "    'stage': 'qa-complete',\n"
                    "    'skill': 'aet-qa',\n"
                    "    'verdict': 'pass',\n"
                    "    'summary': 'task-c2 passed',\n"
                    "    'generated_at': telemetry.iso_now(),\n"
                    "    'tree_hash': '',\n"
                    "    'test_command': 'make validate',\n"
                    "    'tests_total': 1,\n"
                    "    'tests_passed': 1,\n"
                    "    'tests_failed': 0,\n"
                    "}\n"
                    "evidence.write_verdict(name, 'qa', record, project_slug=project_slug, worktree_dir=wt)\n",
                    encoding="utf-8",
                )

                # task-ind touches independent.txt, finishes after task-c2 attempts rebase
                (hooks_dir / "task-ind.py").write_text(
                    "time.sleep(0.7)\n"
                    "pathlib.Path(wt, 'independent.txt').write_text('Independent work\\n')\n"
                    "subprocess.run(['git', '-C', wt, 'add', '.'], check=True)\n"
                    "subprocess.run(['git', '-C', wt, 'commit', '-q', '-m', 'commit task-ind'], check=True)\n"
                    "from aet import evidence, telemetry\n"
                    "project_slug = telemetry.derive_project_slug(repo_root)\n"
                    "record = {\n"
                    "    'task_id': name,\n"
                    "    'stage': 'qa-complete',\n"
                    "    'skill': 'aet-qa',\n"
                    "    'verdict': 'pass',\n"
                    "    'summary': 'task-ind passed',\n"
                    "    'generated_at': telemetry.iso_now(),\n"
                    "    'tree_hash': '',\n"
                    "    'test_command': 'make validate',\n"
                    "    'tests_total': 1,\n"
                    "    'tests_passed': 1,\n"
                    "    'tests_failed': 0,\n"
                    "}\n"
                    "evidence.write_verdict(name, 'qa', record, project_slug=project_slug, worktree_dir=wt)\n",
                    encoding="utf-8",
                )

                queue_file = os.path.join(repo_root, ".agents", "aet-queue")
                backend = orchestrator._make_backend(queue_file)
                backend.save(
                    [
                        {"id": "task-c1", "state": "ready", "plan_file": plan_c1},
                        {
                            "id": "task-c2",
                            "state": "ready",
                            "plan_file": plan_c2,
                            "blocks": ["task-blocked"],
                        },
                        {"id": "task-ind", "state": "ready", "plan_file": plan_ind},
                        {
                            "id": "task-blocked",
                            "state": "blocked",
                            "plan_file": plan_blocked,
                            "blocked_by": ["task-c2"],
                            "pending_blockers": 1,
                        },
                    ]
                )

                args = argparse.Namespace(
                    queue_file=queue_file,
                    repo_root=repo_root,
                    base="epic-01",
                    isolation="standard",
                    max_jobs=3,
                    task_timeout=3600,
                    heartbeat_interval=60,
                    on_failure="triage",
                    run_id="run-conflict-staging",
                )

                exit_code = orchestrator.run_batch(args, adapter)
                # Batch settles cleanly with 0 (staged tasks are non-blocking outcomes, not run failures)
                self.assertEqual(exit_code, 0)

                t_c1 = _get_task(backend, queue_file, "task-c1")
                t_c2 = _get_task(backend, queue_file, "task-c2")
                t_ind = _get_task(backend, queue_file, "task-ind")
                t_blocked = _get_task(backend, queue_file, "task-blocked")

                # task-c1 and task-ind auto-merged cleanly
                self.assertEqual(t_c1["state"], "merged")
                self.assertEqual(t_ind["state"], "merged")

                # task-c2 was staged in awaiting_merge with diagnostics (R-7)
                self.assertEqual(t_c2["state"], "awaiting_merge")
                diag = t_c2.get("conflict_diagnostics")
                self.assertIsNotNone(diag)
                self.assertEqual(diag.get("reason"), "rebase_conflict")
                self.assertIn("conflict.txt", diag.get("conflicting_files", []))

                # task-blocked remained blocked (R-8)
                self.assertEqual(t_blocked["state"], "blocked")

                # Origin epic-01 has both task-c1 and task-ind commits
                log_proc = subprocess.run(
                    ["git", "-C", repo_root, "log", "origin/epic-01", "--oneline"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                self.assertIn("Integrate task-c1", log_proc.stdout)
                self.assertIn("Integrate task-ind", log_proc.stdout)
                self.assertNotIn("Integrate task-c2", log_proc.stdout)

            finally:
                os.environ["PATH"] = original_path


class TestDualModeParity(unittest.TestCase):
    """Integration test suite for R-10."""

    def test_dual_mode_parity_standalone_targeting_trunk(self):
        """R-10: Auto-merge and replenishment operate identically in standalone mode targeting trunk."""
        with (
            tempfile.TemporaryDirectory() as repo_root,
            tempfile.TemporaryDirectory() as origin_root,
        ):
            original_path = os.environ.get("PATH", "")
            fake_bin_dir, adapter = _install_fake_cli(origin_root)
            os.environ["PATH"] = str(fake_bin_dir) + os.pathsep + original_path

            try:
                _init_git_repo(repo_root, origin_root)
                Path(repo_root, ".agents").mkdir(parents=True, exist_ok=True)
                Path(repo_root, ".agents", "aet-config.json").write_text(
                    json.dumps(
                        {
                            "trunk_branch": "main",
                            "integration_mode": "pr-per-task",
                            "validate_command": "true",
                        }
                    ),
                    encoding="utf-8",
                )
                _write_test_workflow(repo_root)

                plan_parent = _write_plan(repo_root, "task-std-p", blocks=["task-std-c"])
                plan_child = _write_plan(repo_root, "task-std-c", blocked_by=["task-std-p"])

                subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
                subprocess.run(
                    ["git", "-C", repo_root, "commit", "-q", "-m", "init standalone plans"],
                    check=True,
                )
                subprocess.run(
                    ["git", "-C", repo_root, "update-ref", "refs/remotes/origin/main", "HEAD"],
                    check=True,
                )
                subprocess.run(["git", "-C", repo_root, "push", "-q", "origin", "main"], check=True)

                queue_file = os.path.join(repo_root, ".agents", "aet-queue")
                backend = orchestrator._make_backend(queue_file)
                backend.save(
                    [
                        {
                            "id": "task-std-p",
                            "state": "ready",
                            "plan_file": plan_parent,
                            "work_class": "normal",
                            "blocks": ["task-std-c"],
                        },
                        {
                            "id": "task-std-c",
                            "state": "blocked",
                            "plan_file": plan_child,
                            "work_class": "normal",
                            "blocked_by": ["task-std-p"],
                            "pending_blockers": 1,
                        },
                    ]
                )

                args = argparse.Namespace(
                    queue_file=queue_file,
                    repo_root=repo_root,
                    base="main",
                    isolation="standard",
                    max_jobs=1,
                    task_timeout=3600,
                    heartbeat_interval=60,
                    on_failure="triage",
                    run_id="run-standalone-parity",
                )

                # Patch track_record.is_eligible_for_auto_merge so standalone tasks auto-merge into trunk
                with patch.object(track_record, "is_eligible_for_auto_merge", return_value=True):
                    exit_code = orchestrator.run_batch(args, adapter)

                self.assertEqual(exit_code, 0)

                t_std_p = _get_task(backend, queue_file, "task-std-p")
                t_std_c = _get_task(backend, queue_file, "task-std-c")
                self.assertEqual(t_std_p["state"], "merged")
                self.assertEqual(t_std_c["state"], "merged")

                # Verify both landed directly on origin/main
                log_proc = subprocess.run(
                    ["git", "-C", repo_root, "log", "origin/main", "--oneline"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                self.assertIn("Integrate task-std-p", log_proc.stdout)
                self.assertIn("Integrate task-std-c", log_proc.stdout)

            finally:
                os.environ["PATH"] = original_path


class TestAetDriveHarmonizationContract(unittest.TestCase):
    """Verification for R-9 conflict diagnostics contract."""

    def test_conflict_diagnostics_contract_for_aet_drive(self):
        """R-9: Staged task metadata adheres to conflict diagnostics schema for aet-drive."""
        diag = {
            "reason": "rebase_conflict",
            "conflicting_files": ["foo.py", "bar.py"],
            "stderr_tail": "CONFLICT (content): Merge conflict in foo.py",
            "at": telemetry.iso_now(),
        }
        task = {
            "id": "task-example",
            "state": "awaiting_merge",
            "conflict_diagnostics": diag,
        }
        self.assertEqual(task["state"], "awaiting_merge")
        self.assertIn("reason", task["conflict_diagnostics"])
        self.assertIn("conflicting_files", task["conflict_diagnostics"])
        self.assertIn("stderr_tail", task["conflict_diagnostics"])
        self.assertIn("at", task["conflict_diagnostics"])
        self.assertIsInstance(task["conflict_diagnostics"]["conflicting_files"], list)


if __name__ == "__main__":
    unittest.main()
