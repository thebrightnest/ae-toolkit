"""Tests for the aet-work orchestrator."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Ensure the aet-work lib is on the path before importing telemetry.
sys.path.insert(0, str(Path(__file__).parent.parent / "aet-work" / "lib"))

import telemetry
from cli_adapter import CLIAdapter
from pipeline import Stage

# Load the orchestrator script (no .py extension) as a module.
_ORCHESTRATOR_BIN = Path(__file__).parent.parent / "aet-work" / "bin" / "orchestrator"
sys.path.insert(0, str(_ORCHESTRATOR_BIN.parent))
_orchestrator_loader = importlib.machinery.SourceFileLoader("orchestrator", str(_ORCHESTRATOR_BIN))
_spec = importlib.util.spec_from_loader("orchestrator", _orchestrator_loader)
orchestrator = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(orchestrator)


_FAKE_ADAPTER = CLIAdapter(
    name="test",
    bin="echo",
    prompt_flag="-p",
    workdir_flag=None,
    headless_flag=None,
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
    # Create a fake origin/main ref so hygiene checks have a base.
    subprocess.run(
        ["git", "-C", repo_root, "branch", "-M", "main"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", repo_root, "remote", "add", "origin", repo_root],
        check=True,
    )
    subprocess.run(
        ["git", "-C", repo_root, "update-ref", "refs/remotes/origin/main", "HEAD"],
        check=True,
    )


def _make_args(repo_root: str, plan_file: str) -> argparse.Namespace:
    return argparse.Namespace(
        queue_file=None,
        plan_file=plan_file,
        repo_root=repo_root,
        cli_bin="echo",
        isolation="standard",
        max_jobs=4,
    )


def _archive_env(archive_dir: str) -> dict[str, str]:
    """Return an environment overlay that sends telemetry to a temp archive."""
    env = os.environ.copy()
    env["AET_TELEMETRY_ARCHIVE_DIR"] = archive_dir
    env["AET_RUN_ID"] = "run-test"
    return env


class TestEnforceMainHygiene(unittest.TestCase):
    def test_enforce_main_hygiene_returns_true_when_main_clean(self):
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            self.assertTrue(orchestrator.enforce_main_hygiene(repo_root))

    def test_enforce_main_hygiene_halts_when_main_ahead_in_interactive_mode(self):
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            Path(repo_root, "ahead.txt").write_text("x", encoding="utf-8")
            subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
            subprocess.run(
                ["git", "-C", repo_root, "commit", "-q", "-m", "ahead commit"],
                check=True,
            )
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("AET_EXECUTION_MODE", None)
                self.assertFalse(orchestrator.enforce_main_hygiene(repo_root))

    def test_enforce_main_hygiene_warns_and_continues_when_main_ahead_in_unattended_mode(self):
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            Path(repo_root, "ahead.txt").write_text("x", encoding="utf-8")
            subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
            subprocess.run(
                ["git", "-C", repo_root, "commit", "-q", "-m", "ahead commit"],
                check=True,
            )
            with patch.dict(os.environ, {"AET_EXECUTION_MODE": "unattended"}):
                self.assertTrue(orchestrator.enforce_main_hygiene(repo_root))

    def test_enforce_main_hygiene_halts_when_main_behind_in_interactive_mode(self):
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            # Move origin/main forward while local main stays behind.
            subprocess.run(
                ["git", "-C", repo_root, "update-ref", "refs/remotes/origin/main", "HEAD~0"],
                check=True,
            )
            # Create another commit on a detached branch to advance origin ref.
            Path(repo_root, "remote.txt").write_text("x", encoding="utf-8")
            subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
            new_head = subprocess.run(
                ["git", "-C", repo_root, "commit-tree", "HEAD^{tree}", "-m", "remote commit"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            subprocess.run(
                ["git", "-C", repo_root, "update-ref", "refs/remotes/origin/main", new_head],
                check=True,
            )
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("AET_EXECUTION_MODE", None)
                self.assertFalse(orchestrator.enforce_main_hygiene(repo_root))

    def test_enforce_main_hygiene_halts_when_dirty_in_interactive_mode(self):
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            Path(repo_root, "dirty.txt").write_text("x", encoding="utf-8")
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("AET_EXECUTION_MODE", None)
                self.assertFalse(orchestrator.enforce_main_hygiene(repo_root))

    def test_enforce_main_hygiene_warns_when_dirty_in_unattended_mode(self):
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            Path(repo_root, "dirty.txt").write_text("x", encoding="utf-8")
            with patch.dict(os.environ, {"AET_EXECUTION_MODE": "unattended"}):
                self.assertTrue(orchestrator.enforce_main_hygiene(repo_root))

    def test_enforce_main_hygiene_ignores_untracked_queue_file(self):
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            Path(repo_root, ".agents").mkdir()
            Path(repo_root, ".agents", "work-queue.json").write_text(
                '{"tasks": []}', encoding="utf-8"
            )
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("AET_EXECUTION_MODE", None)
                self.assertTrue(orchestrator.enforce_main_hygiene(repo_root))

    def test_enforce_main_hygiene_ignores_modified_queue_files(self):
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            Path(repo_root, ".agents").mkdir()
            queue_file = Path(repo_root, ".agents", "work-queue.json")
            queue_file.write_text('{"tasks": []}', encoding="utf-8")
            subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
            subprocess.run(
                ["git", "-C", repo_root, "commit", "-q", "-m", "add queue"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", repo_root, "update-ref", "refs/remotes/origin/main", "HEAD"],
                check=True,
            )
            queue_file.write_text('{"tasks": [{"id": "x"}]}', encoding="utf-8")
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("AET_EXECUTION_MODE", None)
                self.assertTrue(orchestrator.enforce_main_hygiene(repo_root))

    def test_enforce_main_hygiene_still_halts_on_other_dirty_files(self):
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            Path(repo_root, ".agents").mkdir()
            Path(repo_root, ".agents", "work-queue.json").write_text(
                '{"tasks": []}', encoding="utf-8"
            )
            Path(repo_root, "dirty.txt").write_text("x", encoding="utf-8")
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("AET_EXECUTION_MODE", None)
                self.assertFalse(orchestrator.enforce_main_hygiene(repo_root))


class TestRunSingleHygiene(unittest.TestCase):
    def test_run_single_halts_when_main_ahead(self):
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            Path(repo_root, "ahead.txt").write_text("x", encoding="utf-8")
            subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
            subprocess.run(
                ["git", "-C", repo_root, "commit", "-q", "-m", "ahead commit"],
                check=True,
            )
            args = _make_args(repo_root, "docs/plans/demo.md")
            with patch.dict(
                os.environ, {"AET_EXECUTION_MODE": ""}, clear=True
            ):
                with patch.object(orchestrator, "process_task") as mock_process:
                    exit_code = orchestrator.run_single(args, _FAKE_ADAPTER)
            self.assertEqual(exit_code, 1)
            mock_process.assert_not_called()

    def test_run_single_halts_when_main_behind(self):
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            new_head = subprocess.run(
                ["git", "-C", repo_root, "commit-tree", "HEAD^{tree}", "-m", "remote commit"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            subprocess.run(
                ["git", "-C", repo_root, "update-ref", "refs/remotes/origin/main", new_head],
                check=True,
            )
            args = _make_args(repo_root, "docs/plans/demo.md")
            with patch.dict(
                os.environ, {"AET_EXECUTION_MODE": ""}, clear=True
            ):
                with patch.object(orchestrator, "process_task") as mock_process:
                    exit_code = orchestrator.run_single(args, _FAKE_ADAPTER)
            self.assertEqual(exit_code, 1)
            mock_process.assert_not_called()

    def test_run_single_halts_when_main_dirty(self):
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            Path(repo_root, "dirty.txt").write_text("x", encoding="utf-8")
            args = _make_args(repo_root, "docs/plans/demo.md")
            with patch.dict(
                os.environ, {"AET_EXECUTION_MODE": ""}, clear=True
            ):
                with patch.object(orchestrator, "process_task") as mock_process:
                    exit_code = orchestrator.run_single(args, _FAKE_ADAPTER)
            self.assertEqual(exit_code, 1)
            mock_process.assert_not_called()

    def test_run_single_warns_in_unattended(self):
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            Path(repo_root, "ahead.txt").write_text("x", encoding="utf-8")
            subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
            subprocess.run(
                ["git", "-C", repo_root, "commit", "-q", "-m", "ahead commit"],
                check=True,
            )
            args = _make_args(repo_root, "docs/plans/demo.md")
            with patch.dict(
                os.environ, {"AET_EXECUTION_MODE": "unattended"}, clear=True
            ):
                with patch.object(
                    orchestrator, "process_task", return_value=False
                ) as mock_process:
                    exit_code = orchestrator.run_single(args, _FAKE_ADAPTER)
            self.assertEqual(exit_code, 1)
            # In unattended mode hygiene warns and continues; process_task is
            # reached but fails because the plan file is missing.
            mock_process.assert_called_once()


class TestDependencyWarmup(unittest.TestCase):
    def test_process_task_creates_symlink_dependencies_in_worktree(self):
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            plan_file = os.path.join(repo_root, "docs", "plans", "demo.md")
            Path(plan_file).parent.mkdir(parents=True, exist_ok=True)
            Path(plan_file).write_text(
                "---\nid: demo\n---\n\n# Demo\n\n_Stage: plan-approved_\n",
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

            Path(repo_root, ".agents").mkdir(parents=True, exist_ok=True)
            Path(repo_root, "app", "node_modules", "pkg").mkdir(parents=True, exist_ok=True)
            Path(repo_root, ".agents", "aet-work.json").write_text(
                json.dumps(
                    {
                        "symlink_dependencies": [
                            {
                                "name": "node_modules",
                                "source": "app/node_modules",
                                "target": "app/node_modules",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            with tempfile.TemporaryDirectory() as archive_dir:
                env = _archive_env(archive_dir)
                with patch.dict(os.environ, env, clear=False):
                    logger = telemetry.RunLogger(repo_root, run_id="r1")
                task = {"id": "demo", "title": "Demo", "plan_file": plan_file}

                with patch.object(orchestrator, "run_stage", return_value=0):
                    with patch.object(
                        orchestrator, "verify_branch_has_commits", return_value=(True, "")
                    ):
                        with patch.object(
                            orchestrator,
                            "verify_stage_advancement",
                            return_value=(True, ""),
                        ):
                            result = orchestrator.process_task(
                                task, repo_root, _FAKE_ADAPTER, "standard", logger=logger
                            )

                self.assertTrue(result)
                worktree_dir = os.path.join(repo_root, ".worktrees", "demo")
                node_link = Path(worktree_dir, "app", "node_modules")
                self.assertTrue(node_link.is_symlink())
                self.assertTrue(
                    node_link.resolve().samefile(Path(repo_root, "app", "node_modules"))
                )

                records = telemetry.read_jsonl(logger.task_log_path("demo"))
                issues = [r for r in records if r.get("type") == "environment_issue"]
                self.assertEqual(len(issues), 0)


class TestEnvironmentIssueEmission(unittest.TestCase):
    def test_process_task_emits_environment_issue_for_missing_dependency(self):
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            plan_file = os.path.join(repo_root, "docs", "plans", "demo.md")
            Path(plan_file).parent.mkdir(parents=True, exist_ok=True)
            Path(plan_file).write_text(
                "---\nid: demo\n---\n\n# Demo\n\n_Stage: plan-approved_\n",
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

            Path(repo_root, ".agents").mkdir(parents=True, exist_ok=True)
            Path(repo_root, ".agents", "aet-work.json").write_text(
                json.dumps(
                    {
                        "symlink_dependencies": [
                            {
                                "name": "node_modules",
                                "source": "app/node_modules",
                                "target": "app/node_modules",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            with tempfile.TemporaryDirectory() as archive_dir:
                env = _archive_env(archive_dir)
                with patch.dict(os.environ, env, clear=False):
                    logger = telemetry.RunLogger(repo_root, run_id="r1")
                task = {"id": "demo", "title": "Demo", "plan_file": plan_file}

                with patch.object(orchestrator, "run_stage", return_value=0):
                    with patch.object(
                        orchestrator, "verify_branch_has_commits", return_value=(True, "")
                    ):
                        with patch.object(
                            orchestrator,
                            "verify_stage_advancement",
                            return_value=(True, ""),
                        ):
                            result = orchestrator.process_task(
                                task, repo_root, _FAKE_ADAPTER, "standard", logger=logger
                            )

                self.assertTrue(result)
                records = telemetry.read_jsonl(logger.task_log_path("demo"))
                issues = [r for r in records if r.get("type") == "environment_issue"]
                self.assertEqual(len(issues), 1)
                self.assertEqual(issues[0]["run_id"], "r1")
                self.assertEqual(issues[0]["task_id"], "demo")
            self.assertEqual(issues[0]["dependency"], "app/node_modules")
            self.assertEqual(issues[0]["issue_type"], "missing_dependency")


class TestProcessTaskPlanPresence(unittest.TestCase):
    def test_process_task_fails_when_plan_missing_in_worktree(self):
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            # The plan file path is inside the repo but does not exist anywhere.
            plan_file = os.path.join(repo_root, "docs", "plans", "missing.md")
            task = {"id": "missing", "title": "missing", "plan_file": plan_file}
            result = orchestrator.process_task(
                task, repo_root, _FAKE_ADAPTER, "standard"
            )
            self.assertFalse(result)


def _write_queue(repo_root: str, tasks: list[dict]) -> str:
    """Write a wrapper-format queue file and return its path."""
    queue_file = os.path.join(repo_root, ".agents", "work-queue.json")
    Path(queue_file).parent.mkdir(parents=True, exist_ok=True)
    with open(queue_file, "w", encoding="utf-8") as f:
        json.dump(
            {
                "queue_updated_at": "2026-06-18T00:00:00Z",
                "source_prd": "docs/prds/demo-prd.md",
                "tasks": tasks,
            },
            f,
            indent=2,
        )
    return queue_file


class TestRunOneQueueBookkeeping(unittest.TestCase):
    def test_run_single_records_branch_and_worktree_when_plan_is_queued(self):
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            plan_file = os.path.join(repo_root, "docs", "plans", "demo-plan.md")
            Path(plan_file).parent.mkdir(parents=True, exist_ok=True)
            Path(plan_file).write_text(
                "---\nid: demo\n---\n\n# Demo\n\n_Stage: implemented_\n",
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

            _write_queue(
                repo_root,
                [
                    {
                        "id": "demo",
                        "title": "Demo",
                        "plan_file": "docs/plans/demo-plan.md",
                        "blocked_by": [],
                        "state": "planned",
                    }
                ],
            )

            args = _make_args(repo_root, plan_file)
            with patch.dict(
                os.environ, {"AET_EXECUTION_MODE": "unattended"}, clear=True
            ):
                with patch.object(orchestrator, "process_task", return_value=True):
                    exit_code = orchestrator.run_single(args, _FAKE_ADAPTER)

            self.assertEqual(exit_code, 0)
            with open(os.path.join(repo_root, ".agents", "work-queue.json"), encoding="utf-8") as f:
                queue = json.load(f)
            task = queue["tasks"][0]
            self.assertEqual(task["state"], "awaiting_merge")
            self.assertNotIn("status", task)
            self.assertEqual(task["branch"], "demo")
            self.assertEqual(task["worktree"], ".worktrees/demo")

    def test_run_single_does_not_mutate_queue_when_plan_not_queued(self):
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            plan_file = os.path.join(repo_root, "docs", "plans", "other-plan.md")
            Path(plan_file).parent.mkdir(parents=True, exist_ok=True)
            Path(plan_file).write_text(
                "---\nid: other\n---\n\n# Other\n\n_Stage: implemented_\n",
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

            _write_queue(
                repo_root,
                [
                    {
                        "id": "demo",
                        "title": "Demo",
                        "plan_file": "docs/plans/demo-plan.md",
                        "blocked_by": [],
                        "state": "planned",
                    }
                ],
            )

            args = _make_args(repo_root, plan_file)
            with patch.dict(
                os.environ, {"AET_EXECUTION_MODE": "unattended"}, clear=True
            ):
                with patch.object(orchestrator, "process_task", return_value=True):
                    exit_code = orchestrator.run_single(args, _FAKE_ADAPTER)

            self.assertEqual(exit_code, 0)
            with open(os.path.join(repo_root, ".agents", "work-queue.json"), encoding="utf-8") as f:
                queue = json.load(f)
            task = queue["tasks"][0]
            self.assertEqual(task["state"], "planned")
            self.assertNotIn("status", task)
            self.assertEqual(task.get("branch"), None)
            self.assertEqual(task.get("worktree"), None)

    def test_run_single_does_not_mutate_queue_when_spawned_by_batch(self):
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            plan_file = os.path.join(repo_root, "docs", "plans", "demo-plan.md")
            Path(plan_file).parent.mkdir(parents=True, exist_ok=True)
            Path(plan_file).write_text(
                "---\nid: demo\n---\n\n# Demo\n\n_Stage: implemented_\n",
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

            _write_queue(
                repo_root,
                [
                    {
                        "id": "demo",
                        "title": "Demo",
                        "plan_file": "docs/plans/demo-plan.md",
                        "blocked_by": [],
                        "state": "planned",
                    }
                ],
            )

            args = _make_args(repo_root, plan_file)
            with patch.dict(
                os.environ,
                {"AET_EXECUTION_MODE": "unattended", "AET_TASK_ID": "demo"},
                clear=True,
            ):
                with patch.object(orchestrator, "process_task", return_value=True):
                    exit_code = orchestrator.run_single(args, _FAKE_ADAPTER)

            self.assertEqual(exit_code, 0)
            with open(os.path.join(repo_root, ".agents", "work-queue.json"), encoding="utf-8") as f:
                queue = json.load(f)
            task = queue["tasks"][0]
            self.assertEqual(task["state"], "planned")
            self.assertNotIn("status", task)
            self.assertEqual(task.get("branch"), None)
            self.assertEqual(task.get("worktree"), None)

    def test_record_merge_succeeds_after_run_one(self):
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            plan_file = os.path.join(repo_root, "docs", "plans", "demo-plan.md")
            Path(plan_file).parent.mkdir(parents=True, exist_ok=True)
            Path(plan_file).write_text(
                "---\nid: demo\n---\n\n# Demo\n\n_Stage: implemented_\n",
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

            queue_file = _write_queue(
                repo_root,
                [
                    {
                        "id": "demo",
                        "title": "Demo",
                        "plan_file": "docs/plans/demo-plan.md",
                        "blocked_by": [],
                        "state": "planned",
                    }
                ],
            )

            args = _make_args(repo_root, plan_file)
            with patch.dict(
                os.environ, {"AET_EXECUTION_MODE": "unattended"}, clear=True
            ):
                with patch.object(orchestrator, "process_task", return_value=True):
                    exit_code = orchestrator.run_single(args, _FAKE_ADAPTER)
            self.assertEqual(exit_code, 0)

            # Simulate the branch being merged into origin/main by fast-forwarding
            # the local main to the worktree branch tip, then updating origin/main.
            subprocess.run(
                ["git", "-C", repo_root, "checkout", "main"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", repo_root, "merge", "--ff-only", "demo"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", repo_root, "update-ref", "refs/remotes/origin/main", "HEAD"],
                check=True,
            )

            aet_state_bin = str(Path(__file__).parent.parent / "aet-work" / "bin" / "aet-state")
            result = subprocess.run(
                [sys.executable, aet_state_bin, "record-merge", "demo", queue_file],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

            with open(queue_file, encoding="utf-8") as f:
                queue = json.load(f)
            self.assertEqual(queue["tasks"], [])

            history_file = os.path.join(repo_root, ".agents", "work-history.jsonl")
            with open(history_file, encoding="utf-8") as f:
                settled = json.loads(f.readline())
            self.assertEqual(settled["state"], "merged")
            self.assertIn("merge_commit", settled)
            self.assertIsNotNone(settled["merge_commit"])


class TestRunSummaryTelemetry(unittest.TestCase):
    def test_run_summary_record_includes_new_fields(self):
        record = telemetry.run_summary_record(
            run_id="r1",
            start_time="2026-06-18T00:00:00Z",
            end_time="2026-06-18T00:00:01Z",
            tasks_spawned=2,
            tasks_succeeded=1,
            tasks_failed=1,
            outcome="failure",
            exit_code=1,
            task_ids=["t1", "t2"],
            final_stage="implemented",
        )
        self.assertEqual(record["outcome"], "failure")
        self.assertEqual(record["exit_code"], 1)
        self.assertEqual(record["task_ids"], ["t1", "t2"])
        self.assertEqual(record["final_stage"], "implemented")

    def test_run_summary_written_on_success(self):
        with tempfile.TemporaryDirectory() as repo_root:
            with tempfile.TemporaryDirectory() as archive_dir:
                _init_git_repo(repo_root)
                plan_file = os.path.join(repo_root, "docs", "plans", "demo.md")
                Path(plan_file).parent.mkdir(parents=True, exist_ok=True)
                Path(plan_file).write_text(
                    "---\nid: demo\n---\n\n# Demo\n\n_Stage: implemented_\n",
                    encoding="utf-8",
                )
                subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
                subprocess.run(
                    ["git", "-C", repo_root, "commit", "-q", "-m", "add plan"],
                    check=True,
                )
                # Refresh origin/main so hygiene passes.
                subprocess.run(
                    ["git", "-C", repo_root, "update-ref", "refs/remotes/origin/main", "HEAD"],
                    check=True,
                )

                args = _make_args(repo_root, plan_file)
                with patch.dict(
                    os.environ, _archive_env(archive_dir), clear=True
                ):
                    with patch.object(orchestrator, "process_task", return_value=True):
                        exit_code = orchestrator.run_single(args, _FAKE_ADAPTER)
                self.assertEqual(exit_code, 0)

                last_run = Path(archive_dir).glob("*/*/*/*/last-run.json")
                summary = json.loads(next(iter(last_run)).read_text(encoding="utf-8"))
                self.assertEqual(summary["exit_code"], 0)
                self.assertEqual(summary["outcome"], "success")

    def test_run_summary_written_on_failure(self):
        with tempfile.TemporaryDirectory() as repo_root:
            with tempfile.TemporaryDirectory() as archive_dir:
                _init_git_repo(repo_root)
                plan_file = os.path.join(repo_root, "docs", "plans", "demo.md")
                Path(plan_file).parent.mkdir(parents=True, exist_ok=True)
                Path(plan_file).write_text(
                    "---\nid: demo\n---\n\n# Demo\n\n_Stage: implemented_\n",
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

                args = _make_args(repo_root, plan_file)
                with patch.dict(
                    os.environ, _archive_env(archive_dir), clear=True
                ):
                    with patch.object(orchestrator, "process_task", return_value=False):
                        exit_code = orchestrator.run_single(args, _FAKE_ADAPTER)
                self.assertEqual(exit_code, 1)

                last_run = Path(archive_dir).glob("*/*/*/*/last-run.json")
                summary = json.loads(next(iter(last_run)).read_text(encoding="utf-8"))
                self.assertEqual(summary["exit_code"], 1)
                self.assertEqual(summary["outcome"], "failure")


class TestRunStageGroup(unittest.TestCase):
    def test_builds_compound_prompt_for_multiple_stages(self):
        """run_stage_group builds a prompt containing every stage in the group."""
        stages = [
            Stage(name="plan-approved", skills=["aet-tdd", "aet-implement"], next_stage="implemented"),
            Stage(name="implemented", skills=["aet-qa"], next_stage="qa-complete"),
        ]
        plan_file = "/work/docs/plans/demo.md"
        adapter = CLIAdapter(
            name="test",
            bin="echo",
            prompt_flag="-p",
            workdir_flag=None,
            headless_flag=None,
        )

        captured = {}

        def fake_run(cmd, **_kwargs):
            captured["cmd"] = cmd
            return subprocess.CompletedProcess(cmd, 0)

        with patch.object(orchestrator.subprocess, "run", side_effect=fake_run):
            orchestrator.run_stage_group(
                adapter, "/repo", plan_file, "/work", stages
            )

        # cmd == ["echo", "-p", prompt]
        self.assertEqual(captured["cmd"][0], "echo")
        prompt = captured["cmd"][2]
        self.assertIn("plan-approved", prompt)
        self.assertIn("implemented", prompt)
        self.assertIn("aet-tdd", prompt)
        self.assertIn("aet-implement", prompt)
        self.assertIn("aet-qa", prompt)
        self.assertIn("Target stage: implemented", prompt)
        self.assertIn("Target stage: qa-complete", prompt)
        self.assertIn("Commit your work and update the plan footer", prompt)

    def test_returns_adapter_exit_code(self):
        """run_stage_group returns the adapter subprocess exit code."""
        stages = [
            Stage(name="plan-approved", skills=["aet-tdd", "aet-implement"], next_stage="implemented"),
        ]
        adapter = CLIAdapter(
            name="test",
            bin="echo",
            prompt_flag="-p",
            workdir_flag=None,
            headless_flag=None,
        )

        with patch.object(orchestrator.subprocess, "run", return_value=subprocess.CompletedProcess(["false"], 1)):
            result = orchestrator.run_stage_group(
                adapter, "/repo", "/work/plan.md", "/work", stages
            )
        self.assertEqual(result, 1)


class TestStageGroupSessionReuse(unittest.TestCase):
    def _setup_repo_with_plan(self, repo_root: str, stage: str = "plan-approved") -> str:
        _init_git_repo(repo_root)
        plan_file = os.path.join(repo_root, "docs", "plans", "demo.md")
        Path(plan_file).parent.mkdir(parents=True, exist_ok=True)
        Path(plan_file).write_text(
            f"---\nid: demo\n---\n\n# Demo\n\n_Stage: {stage}_\n",
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
        return plan_file

    def test_standard_isolation_runs_group_session_for_two_stage_group(self):
        """standard isolation spawns one session for a two-stage group."""
        with tempfile.TemporaryDirectory() as repo_root:
            plan_file = self._setup_repo_with_plan(repo_root)
            task = {"id": "demo", "title": "Demo", "plan_file": plan_file}

            read_calls = []

            def staged_read_plan_stage(plan_file):
                read_calls.append(plan_file)
                # First call is intake; subsequent calls observe group-session result.
                if len(read_calls) == 1:
                    return "plan-approved"
                return "qa-complete"

            with patch.object(orchestrator, "run_stage_group", return_value=0) as mock_group:
                with patch.object(orchestrator, "run_stage", return_value=0) as mock_stage:
                    with patch.object(
                        orchestrator, "verify_branch_has_commits", return_value=(True, "")
                    ):
                        with patch.object(
                            orchestrator, "read_plan_stage", side_effect=staged_read_plan_stage
                        ):
                            with patch.object(
                                orchestrator,
                                "verify_stage_advancement",
                                return_value=(True, ""),
                            ):
                                result = orchestrator.process_task(
                                    task, repo_root, _FAKE_ADAPTER, "standard"
                                )

            self.assertTrue(result)
            mock_group.assert_called_once()
            # Group 1 ran as a single session; group 2 (single stage) still uses run_stage.
            self.assertEqual(mock_stage.call_count, 1)

    def test_minimal_isolation_keeps_per_stage_execution(self):
        """minimal isolation does not use run_stage_group."""
        with tempfile.TemporaryDirectory() as repo_root:
            plan_file = self._setup_repo_with_plan(repo_root)
            task = {"id": "demo", "title": "Demo", "plan_file": plan_file}

            with patch.object(orchestrator, "run_stage_group") as mock_group:
                with patch.object(orchestrator, "run_stage", return_value=0) as mock_stage:
                    with patch.object(
                        orchestrator, "verify_branch_has_commits", return_value=(True, "")
                    ):
                        with patch.object(
                            orchestrator,
                            "verify_stage_advancement",
                            return_value=(True, ""),
                        ):
                            result = orchestrator.process_task(
                                task, repo_root, _FAKE_ADAPTER, "minimal"
                            )

            self.assertTrue(result)
            mock_group.assert_not_called()
            mock_stage.assert_called()

    def test_full_isolation_keeps_per_stage_execution(self):
        """full isolation does not use run_stage_group."""
        with tempfile.TemporaryDirectory() as repo_root:
            plan_file = self._setup_repo_with_plan(repo_root)
            task = {"id": "demo", "title": "Demo", "plan_file": plan_file}

            with patch.object(orchestrator, "run_stage_group") as mock_group:
                with patch.object(orchestrator, "run_stage", return_value=0) as mock_stage:
                    with patch.object(
                        orchestrator, "verify_branch_has_commits", return_value=(True, "")
                    ):
                        with patch.object(
                            orchestrator,
                            "verify_stage_advancement",
                            return_value=(True, ""),
                        ):
                            result = orchestrator.process_task(
                                task, repo_root, _FAKE_ADAPTER, "full"
                            )

            self.assertTrue(result)
            mock_group.assert_not_called()
            mock_stage.assert_called()

    def test_standard_fallback_to_per_stage_when_group_does_not_advance(self):
        """standard isolation falls back to per-stage if group verification fails."""
        with tempfile.TemporaryDirectory() as repo_root:
            plan_file = self._setup_repo_with_plan(repo_root, stage="plan-approved")
            task = {"id": "demo", "title": "Demo", "plan_file": plan_file}

            read_calls = []

            def staged_read_plan_stage(plan_file):
                read_calls.append(plan_file)
                # First call is intake; subsequent calls observe partial progress.
                if len(read_calls) == 1:
                    return "plan-approved"
                return "implemented"

            with patch.object(orchestrator, "run_stage_group", return_value=0) as mock_group:
                with patch.object(orchestrator, "run_stage", return_value=0) as mock_stage:
                    with patch.object(
                        orchestrator, "verify_branch_has_commits", return_value=(True, "")
                    ):
                        with patch.object(
                            orchestrator, "read_plan_stage", side_effect=staged_read_plan_stage
                        ):
                            # Per-stage fallback for implemented and qa-complete succeeds.
                            with patch.object(
                                orchestrator,
                                "verify_stage_advancement",
                                side_effect=[(True, ""), (True, "")],
                            ):
                                result = orchestrator.process_task(
                                    task, repo_root, _FAKE_ADAPTER, "standard"
                                )

            self.assertTrue(result)
            mock_group.assert_called_once()
            mock_stage.assert_called()

    def test_standard_group_failure_returns_false(self):
        """standard isolation returns False when the group session fails."""
        with tempfile.TemporaryDirectory() as repo_root:
            plan_file = self._setup_repo_with_plan(repo_root)
            task = {"id": "demo", "title": "Demo", "plan_file": plan_file}

            with patch.object(orchestrator, "run_stage_group", return_value=1):
                result = orchestrator.process_task(
                    task, repo_root, _FAKE_ADAPTER, "standard"
                )

            self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
