"""Tests for the aet-work orchestrator."""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure the aet-work lib is on the path before importing telemetry.
from aet import evidence, session_log_claude, telemetry
from aet.cli_adapter import CLIAdapter, resolve_cli_adapter
from aet.workflow import ExecutionPolicy, Routing, Workflow, WorkflowStage

# Load the orchestrator script (no .py extension) as a module.
_ORCHESTRATOR_BIN = Path(__file__).parents[2] / "src" / "aet" / "cli" / "orchestrator.py"
_orchestrator_loader = importlib.machinery.SourceFileLoader("orchestrator", str(_ORCHESTRATOR_BIN))
_spec = importlib.util.spec_from_loader("orchestrator", _orchestrator_loader)
orchestrator = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(orchestrator)

pytestmark = pytest.mark.xdist_group("process-group")


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
        ["git", "-C", repo_root, "config", "receive.denyCurrentBranch", "ignore"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", repo_root, "push", "-u", "origin", "main"],
        check=True,
        capture_output=True,
    )


def _make_args(repo_root: str, plan_file: str) -> argparse.Namespace:
    return argparse.Namespace(
        queue_file=None,
        plan_file=plan_file,
        repo_root=repo_root,
        cli_bin="echo",
        isolation="standard",
        max_jobs=4,
        on_failure="continue",
    )


def _archive_env(archive_dir: str) -> dict[str, str]:
    """Return an environment overlay that sends telemetry to a temp archive."""
    env = os.environ.copy()
    env["AET_TELEMETRY_ARCHIVE_DIR"] = archive_dir
    env["AET_RUN_ID"] = "run-test"
    return env


def _gate_env(reports_dir: str, archive_dir: str) -> dict[str, str]:
    """Env overlay routing evidence verdicts and telemetry to temp dirs."""
    env = os.environ.copy()
    env["AET_REPORTS_DIR"] = reports_dir
    env["AET_PROJECT_ID"] = "demo/project"
    env["AET_TELEMETRY_ARCHIVE_DIR"] = archive_dir
    env["AET_RUN_ID"] = "run-test"
    return env


def _verdict_record(kind: str, verdict: str = "pass", **overrides) -> dict:
    """Build a schema-valid verdict record for ``kind``."""
    record = {
        "task_id": overrides.pop("task_id", "demo"),
        "stage": overrides.pop("stage", f"{kind}-stage"),
        "skill": overrides.pop("skill", f"aet-{kind}"),
        "verdict": verdict,
        "summary": overrides.pop("summary", "ok"),
        "generated_at": overrides.pop("generated_at", "2026-07-09T20:00:00Z"),
        "tree_hash": overrides.pop("tree_hash", "t0"),
    }
    if kind == "qa":
        record.update(
            {
                "test_command": overrides.pop("test_command", "pytest"),
                "tests_total": overrides.pop("tests_total", 3),
                "tests_passed": overrides.pop("tests_passed", 3),
                "tests_failed": overrides.pop("tests_failed", 0),
            }
        )
    elif kind in ("review", "cso"):
        record["findings"] = overrides.pop("findings", [])
    elif kind == "sync-docs":
        record["divergences"] = overrides.pop("divergences", [])
    return record


def _write_verdict(
    reports_dir: str,
    kind: str,
    verdict: str = "pass",
    task_id: str = "demo",
    **overrides,
) -> None:
    """Write a verdict for ``kind`` to the evidence home."""
    evidence.write_verdict(
        task_id=task_id,
        kind=kind,
        record=_verdict_record(kind, verdict, task_id=task_id, **overrides),
        project_slug="demo/project",
        reports_root=reports_dir,
    )


def _write_passing(reports_dir: str, *kinds: str, task_id: str = "demo") -> None:
    """Write passing verdicts for ``kinds`` to the evidence home."""
    for kind in kinds:
        _write_verdict(reports_dir, kind, "pass", task_id=task_id)


class TestEnforceBaseHygiene(unittest.TestCase):
    def test_enforce_base_hygiene_returns_true_when_main_clean(self):
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            self.assertTrue(orchestrator.enforce_base_hygiene(repo_root, "main", "main"))

    def test_enforce_base_hygiene_halts_when_main_ahead_in_interactive_mode(self):
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
                self.assertFalse(orchestrator.enforce_base_hygiene(repo_root, "main", "main"))

    def test_enforce_base_hygiene_halts_when_main_ahead_in_unattended_mode(self):
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            Path(repo_root, "ahead.txt").write_text("x", encoding="utf-8")
            subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
            subprocess.run(
                ["git", "-C", repo_root, "commit", "-q", "-m", "ahead commit"],
                check=True,
            )
            with patch.dict(os.environ, {"AET_EXECUTION_MODE": "unattended"}):
                self.assertFalse(orchestrator.enforce_base_hygiene(repo_root, "main", "main"))

    def test_enforce_base_hygiene_halts_when_main_behind_in_interactive_mode(self):
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
                self.assertFalse(orchestrator.enforce_base_hygiene(repo_root, "main", "main"))

    def test_enforce_base_hygiene_halts_when_dirty_in_interactive_mode(self):
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            Path(repo_root, "dirty.txt").write_text("x", encoding="utf-8")
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("AET_EXECUTION_MODE", None)
                self.assertFalse(orchestrator.enforce_base_hygiene(repo_root, "main", "main"))

    def test_enforce_base_hygiene_halts_when_dirty_in_unattended_mode(self):
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            Path(repo_root, "dirty.txt").write_text("x", encoding="utf-8")
            with patch.dict(os.environ, {"AET_EXECUTION_MODE": "unattended"}):
                self.assertFalse(orchestrator.enforce_base_hygiene(repo_root, "main", "main"))

    def test_enforce_base_hygiene_proceeds_when_clean_in_unattended_mode(self):
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            with patch.dict(os.environ, {"AET_EXECUTION_MODE": "unattended"}):
                self.assertTrue(orchestrator.enforce_base_hygiene(repo_root, "main", "main"))

    def test_enforce_base_hygiene_proceeds_without_origin_in_unattended_mode(self):
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            # Drop the remote-tracking ref so there is no origin/main to be
            # ahead of. No-remote projects must not be falsely halted.
            subprocess.run(
                ["git", "-C", repo_root, "update-ref", "-d", "refs/remotes/origin/main"],
                check=True,
            )
            with patch.dict(os.environ, {"AET_EXECUTION_MODE": "unattended"}):
                self.assertTrue(orchestrator.enforce_base_hygiene(repo_root, "main", "main"))

    def test_enforce_base_hygiene_ignores_untracked_queue_file(self):
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            Path(repo_root, ".agents").mkdir()
            Path(repo_root, ".agents", "work-queue.json").write_text(
                '{"tasks": []}', encoding="utf-8"
            )
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("AET_EXECUTION_MODE", None)
                self.assertTrue(orchestrator.enforce_base_hygiene(repo_root, "main", "main"))

    def test_enforce_base_hygiene_ignores_modified_queue_files(self):
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
                self.assertTrue(orchestrator.enforce_base_hygiene(repo_root, "main", "main"))

    def test_enforce_base_hygiene_still_halts_on_other_dirty_files(self):
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            Path(repo_root, ".agents").mkdir()
            Path(repo_root, ".agents", "work-queue.json").write_text(
                '{"tasks": []}', encoding="utf-8"
            )
            Path(repo_root, "dirty.txt").write_text("x", encoding="utf-8")
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("AET_EXECUTION_MODE", None)
                self.assertFalse(orchestrator.enforce_base_hygiene(repo_root, "main", "main"))


class TestDeferredDurabilityNotice(unittest.TestCase):
    def test_run_batch_prints_deferred_durability_notice(self):
        """After base hygiene passes, batch mode announces plan-durability posture."""
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            queue_file = _write_queue(
                repo_root,
                [
                    {
                        "id": "demo",
                        "title": "Demo",
                        "plan_file": "docs/plans/demo.md",
                        "blocked_by": [],
                        "state": "blocked",
                    }
                ],
            )
            args = argparse.Namespace(
                queue_file=queue_file,
                plan_file=None,
                repo_root=repo_root,
                cli_bin="echo",
                isolation="standard",
                max_jobs=1,
                task_timeout=60,
                heartbeat_interval=60,
                on_failure="continue",
            )
            with tempfile.TemporaryDirectory() as archive_dir:
                env = {"AET_TELEMETRY_ARCHIVE_DIR": archive_dir}
                buf = io.StringIO()
                with patch.dict(os.environ, env, clear=False):
                    with contextlib.redirect_stdout(buf):
                        rc = orchestrator.run_batch(args, _FAKE_ADAPTER)
                output = buf.getvalue()
                self.assertIn("Plan durability is deferred to the PR", output)
                self.assertEqual(rc, 0)

    def test_run_single_prints_deferred_durability_notice(self):
        """After base hygiene passes, single-plan mode announces plan-durability posture."""
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            plan_file = os.path.join(repo_root, "docs", "plans", "demo.md")
            Path(plan_file).parent.mkdir(parents=True, exist_ok=True)
            Path(plan_file).write_text(
                "---\nid: demo\n---\n\n# Demo\n\n_Stage: plan-approved_\n",
                encoding="utf-8",
            )
            args = _make_args(repo_root, plan_file)
            buf = io.StringIO()
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("AET_EXECUTION_MODE", None)
                with patch.object(orchestrator, "process_task", return_value=True):
                    with contextlib.redirect_stdout(buf):
                        rc = orchestrator.run_single(args, _FAKE_ADAPTER)
            output = buf.getvalue()
            self.assertIn("Plan durability is deferred to the PR", output)
            self.assertEqual(rc, 0)


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

    def test_run_single_halts_in_unattended(self):
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
            # Main hygiene fails closed in unattended mode too: the run halts
            # before process_task is reached.
            mock_process.assert_not_called()


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
            Path(repo_root, ".agents", "aet-config.json").write_text(
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
                with tempfile.TemporaryDirectory() as reports_dir:
                    env = _gate_env(reports_dir, archive_dir)
                    with patch.dict(os.environ, env, clear=False):
                        logger = telemetry.RunLogger(repo_root, run_id="r1")
                        task = {"id": "demo", "title": "Demo", "plan_file": plan_file}
                        _write_passing(reports_dir, "qa", "review", "cso", "sync-docs")

                        with patch.object(orchestrator, "run_stage", return_value=(0, None, None, "")):
                            with patch.object(
                                orchestrator, "verify_branch_has_commits", return_value=(True, "")
                            ):
                                with patch.object(
                                    orchestrator,
                                    "verify_stage_advancement",
                                    return_value=(True, ""),
                                ):
                                    result = orchestrator.process_task(
                                        task,
                                        repo_root,
                                        _FAKE_ADAPTER,
                                        "standard",
                                        logger=logger,
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
            Path(repo_root, ".agents", "aet-config.json").write_text(
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
                with tempfile.TemporaryDirectory() as reports_dir:
                    env = _gate_env(reports_dir, archive_dir)
                    with patch.dict(os.environ, env, clear=False):
                        logger = telemetry.RunLogger(repo_root, run_id="r1")
                        task = {"id": "demo", "title": "Demo", "plan_file": plan_file}
                        _write_passing(reports_dir, "qa", "review", "cso", "sync-docs")

                        with patch.object(orchestrator, "run_stage", return_value=(0, None, None, "")):
                            with patch.object(
                                orchestrator, "verify_branch_has_commits", return_value=(True, "")
                            ):
                                with patch.object(
                                    orchestrator,
                                    "verify_stage_advancement",
                                    return_value=(True, ""),
                                ):
                                    result = orchestrator.process_task(
                                        task,
                                        repo_root,
                                        _FAKE_ADAPTER,
                                        "standard",
                                        logger=logger,
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
            with self.assertRaises(orchestrator.MissingPlanError):
                orchestrator.process_task(
                    task, repo_root, _FAKE_ADAPTER, "standard"
                )


class TestSeedFailureSignature(unittest.TestCase):
    def test_seed_failure_records_environment_signature(self):
        """A seed_task_plan failure records a signature so triage gets context."""
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

            task = {"id": "demo", "title": "Demo", "plan_file": plan_file}
            with patch.object(
                orchestrator,
                "seed_task_plan",
                side_effect=RuntimeError("Could not stage docs/plans/demo.md"),
            ):
                result = orchestrator.process_task(
                    task, repo_root, _FAKE_ADAPTER, "standard"
                )

            self.assertFalse(result)
            signatures = task.get("failure_signatures", [])
            self.assertEqual(len(signatures), 1)
            entry = signatures[-1]
            self.assertEqual(entry["class"], "environment")
            self.assertEqual(entry["stage"], "seed")
            self.assertIn("Could not stage", entry["tail_preview"])
            self.assertTrue(entry["signature"])


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
                    with patch.object(
                        orchestrator, "verify_branch_has_commits", return_value=(True, "")
                    ):
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
                    with patch.object(
                        orchestrator, "verify_branch_has_commits", return_value=(True, "")
                    ):
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

            aet_state_bin = str(Path(__file__).parents[2] / "src" / "aet" / "cli" / "aet_state.py")
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

    def test_record_merge_records_delivered_size(self):
        """A sealed history record carries delivered_size paired with declared size."""
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            plan_file = os.path.join(repo_root, "docs", "plans", "demo-plan.md")
            Path(plan_file).parent.mkdir(parents=True, exist_ok=True)
            Path(plan_file).write_text(
                "---\nid: demo\nsize: M\n---\n\n# Demo\n\n_Stage: implemented_\n",
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

            # Create a feature branch with both code and planning-artifact changes.
            subprocess.run(
                ["git", "-C", repo_root, "checkout", "-b", "demo"],
                check=True,
                capture_output=True,
            )
            Path(repo_root, "src").mkdir(parents=True, exist_ok=True)
            Path(repo_root, "src", "demo.py").write_text("a\nb\nc\n", encoding="utf-8")
            Path(repo_root, "docs", "demo.md").write_text("x\ny\n", encoding="utf-8")
            subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
            subprocess.run(
                ["git", "-C", repo_root, "commit", "-q", "-m", "implement demo"],
                check=True,
            )

            subprocess.run(
                ["git", "-C", repo_root, "checkout", "main"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", repo_root, "merge", "--no-ff", "-m", "merge demo", "demo"],
                check=True,
                capture_output=True,
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
                        "state": "awaiting_merge",
                        "branch": "demo",
                    }
                ],
            )

            aet_state_bin = str(
                Path(__file__).parents[2] / "src" / "aet" / "cli" / "aet_state.py"
            )
            result = subprocess.run(
                [sys.executable, aet_state_bin, "record-merge", "demo", queue_file],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

            history_file = os.path.join(repo_root, ".agents", "work-history.jsonl")
            with open(history_file, encoding="utf-8") as f:
                settled = json.loads(f.readline())

            self.assertEqual(settled["state"], "merged")
            self.assertIn("delivered_size", settled)
            delivered = settled["delivered_size"]
            self.assertEqual(delivered["status"], "ok")
            self.assertEqual(delivered["declared_size"], "M")
            self.assertEqual(delivered["headline"], 3)
            self.assertEqual(delivered["total"], 5)
            self.assertIn("reason", delivered)

    def test_failed_measurement_still_settles_task(self):
        """A task with an invalid merge_commit settles with a failed size record."""
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            plan_file = os.path.join(repo_root, "docs", "plans", "demo-plan.md")
            Path(plan_file).parent.mkdir(parents=True, exist_ok=True)
            Path(plan_file).write_text(
                "---\nid: demo\nsize: S\n---\n\n# Demo\n",
                encoding="utf-8",
            )
            subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
            subprocess.run(
                ["git", "-C", repo_root, "commit", "-q", "-m", "add plan"],
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
                        "state": "merged",
                        "merge_commit": "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
                    }
                ],
            )
            history_file = os.path.join(repo_root, ".agents", "work-history.jsonl")

            backend = orchestrator._make_backend(queue_file)
            sealed = backend.seal("demo", history_file)
            self.assertEqual(sealed["state"], "merged")

            with open(history_file, encoding="utf-8") as f:
                settled = json.loads(f.readline())
            self.assertEqual(settled["state"], "merged")
            self.assertIn("delivered_size", settled)
            delivered = settled["delivered_size"]
            self.assertEqual(delivered["status"], "failed")
            self.assertEqual(delivered["declared_size"], "S")
            self.assertIn("reason", delivered)
            self.assertIsNotNone(delivered["reason"])


class _SpyBackend:
    """Wrapper around a real backend that records save calls."""

    def __init__(self, backend):
        self._backend = backend
        self.save_calls = []

    def load(self):
        return self._backend.load()

    def save(self, queue, wrapper=None):
        self.save_calls.append(json.loads(json.dumps(queue)))
        return self._backend.save(queue, wrapper=wrapper)

    @property
    def queue_file(self):
        return self._backend.queue_file

    @property
    def history_file(self):
        return self._backend.history_file


class TestOrchestratorLockedWrites(unittest.TestCase):
    """Regression tests for orchestrator queue mutation races (frh-02)."""

    def test_finalize_preserves_concurrent_stage_write(self):
        """_finalize_task must not overwrite a stage set while the task ran."""
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
                        "state": "in_progress",
                        "stage": "implemented",
                    }
                ],
            )
            backend = _SpyBackend(orchestrator._make_backend(queue_file))
            aet_state_bin = str(Path(__file__).parents[2] / "src" / "aet" / "cli" / "aet_state.py")
            real_subprocess_run = subprocess.run

            def fake_run(cmd, **kwargs):
                # Delegate transition calls to the real aet-state so the queue is
                # mutated through the canonical writer, but count saves via the spy.
                if aet_state_bin in cmd and "transition" in cmd:
                    return real_subprocess_run(cmd, **kwargs)
                return subprocess.CompletedProcess(cmd, 0, "", "")

            with patch.object(orchestrator.subprocess, "run", side_effect=fake_run):
                result = orchestrator._finalize_task(backend, queue_file, "demo", 0)

            self.assertEqual(result["failures"], 0)
            data = backend.load()
            task = next((t for t in data["queue"] if t.get("id") == "demo"), None)
            self.assertIsNotNone(task)
            self.assertEqual(task["state"], "awaiting_merge")
            self.assertEqual(task["stage"], "implemented")
            # _finalize_task itself must not re-save an unmutated queue. The
            # aet-state transition persists through its own backend instance,
            # so the spy only observes saves made directly by the orchestrator.
            self.assertEqual(len(backend.save_calls), 0)

    def test_mark_failed_fallback_never_writes_illegal_state(self):
        """_mark_failed must leave an already-terminal task untouched."""
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            queue_file = _write_queue(
                repo_root,
                [
                    {
                        "id": "demo",
                        "title": "Demo",
                        "state": "merged",
                    }
                ],
            )
            backend = _SpyBackend(orchestrator._make_backend(queue_file))

            orchestrator._mark_failed(backend, queue_file, "demo", "in_progress")

            data = backend.load()
            task = next((t for t in data["queue"] if t.get("id") == "demo"), None)
            self.assertIsNotNone(task)
            self.assertEqual(task["state"], "merged")
            self.assertEqual(len(backend.save_calls), 0)

    def test_run_single_survives_task_sealed_mid_run(self):
        """run_single must not crash when the queued task is sealed mid-run."""
        with tempfile.TemporaryDirectory() as repo_root:
            with tempfile.TemporaryDirectory() as archive_dir:
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

                aet_state_bin = str(
                    Path(__file__).parents[2] / "src" / "aet" / "cli" / "aet_state.py"
                )

                def seal_task_and_succeed(*_args, **_kwargs):
                    # Simulate an external actor sealing the task while it runs.
                    # Transitioning to a terminal state also removes the task
                    # from the live queue via seal_terminal.
                    subprocess.run(
                        [sys.executable, aet_state_bin, "transition", "demo", "in_progress", "abandoned", queue_file],
                        check=True,
                        capture_output=True,
                    )
                    return True

                args = _make_args(repo_root, plan_file)
                env = _archive_env(archive_dir)
                env.pop("AET_TASK_ID", None)
                with patch.dict(os.environ, env, clear=True):
                    with patch.object(
                        orchestrator, "process_task", side_effect=seal_task_and_succeed
                    ):
                        exit_code = orchestrator.run_single(args, _FAKE_ADAPTER)

                self.assertEqual(exit_code, 0)


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
    def _workflow(self) -> Workflow:
        """A three-stage workflow: plan-approved → implemented → qa-complete."""
        stages = [
            WorkflowStage(
                name="plan-approved",
                skills=["aet-tdd", "aet-implement"],
                evidence=None,
                gate_key=None,
            ),
            WorkflowStage(name="implemented", skills=["aet-qa"], evidence="qa", gate_key=None),
            WorkflowStage(
                name="qa-complete", skills=["aet-review"], evidence="review", gate_key=None
            ),
        ]
        return Workflow(
            version=1,
            name="test",
            done_state="done",
            stages=stages,
            stage_map={s.name: s for s in stages},
            execution_policy=ExecutionPolicy(
                session_groups=[["plan-approved", "implemented", "qa-complete"]]
            ),
            routing=Routing(default={"harness": "test", "model": None}, by_stage={}),
        )

    def test_builds_compound_prompt_for_multiple_stages(self):
        """run_stage_group builds a prompt containing every stage in the group."""
        workflow = self._workflow()
        stages = workflow.stages[:2]
        plan_file = "/work/docs/plans/demo.md"
        adapter = CLIAdapter(
            name="test",
            bin="echo",
            prompt_flag="-p",
            workdir_flag=None,
            headless_flag=None,
        )

        captured = {}

        def fake_popen(cmd, **_kwargs):
            captured["cmd"] = cmd
            return _StubPopen()

        with patch.object(orchestrator.subprocess, "Popen", side_effect=fake_popen):
            orchestrator.run_stage_group(
                adapter, "/repo", plan_file, "/work", stages, workflow=workflow
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
        self.assertIn("Commit your work before exiting.", prompt)
        self.assertNotIn("update the plan footer", prompt)
        self.assertNotIn("queue", prompt.lower())

    def test_returns_adapter_exit_code(self):
        """run_stage_group returns the adapter subprocess exit code."""
        workflow = self._workflow()
        stages = workflow.stages[:1]
        adapter = CLIAdapter(
            name="test",
            bin="echo",
            prompt_flag="-p",
            workdir_flag=None,
            headless_flag=None,
        )

        with patch.object(
            orchestrator.subprocess, "Popen", return_value=_StubPopen(returncode=1)
        ):
            result = orchestrator.run_stage_group(
                adapter, "/repo", "/work/plan.md", "/work", stages, workflow=workflow
            )
        self.assertEqual(result, (1, None, None, ""))


class TestStageEnabled(unittest.TestCase):
    """stage_enabled resolves a stage's gate_key against plan frontmatter."""

    def _gated(self, gate_key: str = "security_review") -> WorkflowStage:
        return WorkflowStage(name="gated", skills=["aet-cso"], evidence="cso", gate_key=gate_key)

    def test_stage_without_gate_key_always_runs(self):
        stage = WorkflowStage(name="plain", skills=[], evidence=None, gate_key=None)
        self.assertTrue(orchestrator.stage_enabled(stage, {}))

    def test_gated_stage_skips_when_frontmatter_marks_skipped(self):
        self.assertFalse(
            orchestrator.stage_enabled(self._gated(), {"security_review": "skipped"})
        )

    def test_gated_stage_runs_when_frontmatter_marks_required(self):
        self.assertTrue(
            orchestrator.stage_enabled(self._gated(), {"security_review": "required"})
        )

    def test_gated_stage_runs_when_key_missing_fail_safe(self):
        # A missing key defaults to required — the gate fails safe and runs.
        self.assertTrue(orchestrator.stage_enabled(self._gated(), {}))

    def test_gate_keys_are_independent(self):
        # A docs_sync skip must not leak into the security_review gate.
        self.assertTrue(orchestrator.stage_enabled(self._gated(), {"docs_sync": "skipped"}))


class TestGateRouting(unittest.TestCase):
    """End-to-end gate routing: plan frontmatter drives stage skip/run (wfd-01)."""

    def _setup_repo_with_plan(
        self, repo_root: str, frontmatter_extra: str = "", stage: str = "reviewed"
    ) -> str:
        _init_git_repo(repo_root)
        plan_file = os.path.join(repo_root, "docs", "plans", "demo.md")
        Path(plan_file).parent.mkdir(parents=True, exist_ok=True)
        Path(plan_file).write_text(
            f"---\nid: demo\n{frontmatter_extra}---\n\n# Demo\n\n_Stage: {stage}_\n",
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

    def _process_task_capture(self, task, repo_root, mock_group, mock_stage):
        with patch.object(
            orchestrator, "verify_branch_has_commits", return_value=(True, "")
        ):
            with patch.object(
                orchestrator, "verify_stage_advancement", return_value=(True, "")
            ):
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    result = orchestrator.process_task(
                        task, repo_root, _FAKE_ADAPTER, "standard"
                    )
        return result, buf.getvalue()

    def test_gated_stages_skip_when_plan_marks_them_skipped(self):
        with tempfile.TemporaryDirectory() as repo_root:
            plan_file = self._setup_repo_with_plan(
                repo_root,
                frontmatter_extra=(
                    "security_review: skipped\n"
                    "security_review_reason: docs-only change\n"
                    "docs_sync: skipped\n"
                    "docs_sync_reason: nothing to reconcile\n"
                ),
            )
            task = {"id": "demo", "title": "Demo", "plan_file": plan_file}
            with tempfile.TemporaryDirectory() as reports_dir:
                with tempfile.TemporaryDirectory() as archive_dir:
                    with patch.dict(
                        os.environ, _gate_env(reports_dir, archive_dir), clear=False
                    ):
                        with patch.object(
                            orchestrator, "run_stage_group", return_value=(0, None, None, "")
                        ) as mock_group:
                            with patch.object(
                                orchestrator, "run_stage", return_value=(0, None, None, "")
                            ) as mock_stage:
                                result, out = self._process_task_capture(
                                    task, repo_root, mock_group, mock_stage
                                )

        self.assertTrue(result)
        mock_group.assert_not_called()
        mock_stage.assert_not_called()
        self.assertIn("Skipping gated stage: reviewed", out)
        self.assertIn("Skipping gated stage: secure", out)
        self.assertIn("source: frontmatter", out)

    def test_gated_stages_run_when_keys_missing_fail_safe(self):
        with tempfile.TemporaryDirectory() as repo_root:
            plan_file = self._setup_repo_with_plan(repo_root)
            task = {"id": "demo", "title": "Demo", "plan_file": plan_file}
            with tempfile.TemporaryDirectory() as reports_dir:
                with tempfile.TemporaryDirectory() as archive_dir:
                    _write_passing(reports_dir, "cso", "sync-docs")
                    with patch.dict(
                        os.environ, _gate_env(reports_dir, archive_dir), clear=False
                    ):
                        with patch.object(
                            orchestrator, "run_stage_group", return_value=(0, None, None, "")
                        ) as mock_group:
                            with patch.object(
                                orchestrator, "run_stage", return_value=(0, None, None, "")
                            ) as mock_stage:
                                result, out = self._process_task_capture(
                                    task, repo_root, mock_group, mock_stage
                                )

        self.assertTrue(result)
        mock_group.assert_called_once()
        stages_arg = mock_group.call_args[0][4]
        self.assertEqual([s.name for s in stages_arg], ["reviewed", "secure"])
        mock_stage.assert_not_called()
        self.assertIn("source: default", out)

    def test_gated_stages_run_when_plan_marks_them_required(self):
        with tempfile.TemporaryDirectory() as repo_root:
            plan_file = self._setup_repo_with_plan(
                repo_root,
                frontmatter_extra=(
                    "security_review: required\n"
                    "security_review_reason: engine gate logic changed\n"
                    "docs_sync: required\n"
                    "docs_sync_reason: frontmatter contract documented in skills\n"
                ),
            )
            task = {"id": "demo", "title": "Demo", "plan_file": plan_file}
            with tempfile.TemporaryDirectory() as reports_dir:
                with tempfile.TemporaryDirectory() as archive_dir:
                    _write_passing(reports_dir, "cso", "sync-docs")
                    with patch.dict(
                        os.environ, _gate_env(reports_dir, archive_dir), clear=False
                    ):
                        with patch.object(
                            orchestrator, "run_stage_group", return_value=(0, None, None, "")
                        ) as mock_group:
                            with patch.object(
                                orchestrator, "run_stage", return_value=(0, None, None, "")
                            ) as mock_stage:
                                result, out = self._process_task_capture(
                                    task, repo_root, mock_group, mock_stage
                                )

        self.assertTrue(result)
        mock_group.assert_called_once()
        stages_arg = mock_group.call_args[0][4]
        self.assertEqual([s.name for s in stages_arg], ["reviewed", "secure"])
        mock_stage.assert_not_called()
        self.assertNotIn("Skipping gated stage", out)

    def test_mixed_gates_walk_per_stage_and_report_both_sources(self):
        # security_review skipped + docs_sync absent → only sync-docs runs, and
        # the single runnable stage falls back to the per-stage walk.
        with tempfile.TemporaryDirectory() as repo_root:
            plan_file = self._setup_repo_with_plan(
                repo_root,
                frontmatter_extra=(
                    "security_review: skipped\n"
                    "security_review_reason: no auth or data surface\n"
                ),
            )
            task = {"id": "demo", "title": "Demo", "plan_file": plan_file}
            with tempfile.TemporaryDirectory() as reports_dir:
                with tempfile.TemporaryDirectory() as archive_dir:
                    _write_passing(reports_dir, "sync-docs")
                    with patch.dict(
                        os.environ, _gate_env(reports_dir, archive_dir), clear=False
                    ):
                        with patch.object(
                            orchestrator, "run_stage_group", return_value=(0, None, None, "")
                        ) as mock_group:
                            with patch.object(
                                orchestrator, "run_stage", return_value=(0, None, None, "")
                            ) as mock_stage:
                                result, out = self._process_task_capture(
                                    task, repo_root, mock_group, mock_stage
                                )

        self.assertTrue(result)
        mock_group.assert_not_called()
        mock_stage.assert_called_once()
        self.assertEqual(mock_stage.call_args[0][4], ["aet-sync-docs"])
        self.assertIn("Skipping gated stage: reviewed", out)
        self.assertIn("source: frontmatter", out)
        self.assertIn("source: default", out)


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
        """standard isolation spawns one session per multi-stage group."""
        with tempfile.TemporaryDirectory() as repo_root:
            plan_file = self._setup_repo_with_plan(repo_root)
            task = {"id": "demo", "title": "Demo", "plan_file": plan_file}

            read_calls = []

            def staged_read_plan_stage(plan_file):
                read_calls.append(plan_file)
                # Intake consults the footer breadcrumb; gating no longer does.
                return "plan-approved"

            with tempfile.TemporaryDirectory() as reports_dir:
                _write_passing(reports_dir, "qa", "review", "cso", "sync-docs")
                with patch.dict(
                    os.environ,
                    {"AET_REPORTS_DIR": reports_dir, "AET_PROJECT_ID": "demo/project"},
                    clear=False,
                ):
                    with patch.object(
                        orchestrator, "run_stage_group", return_value=(0, None, None, "")
                    ) as mock_group:
                        with patch.object(
                            orchestrator, "run_stage", return_value=(0, None, None, "")
                        ) as mock_stage:
                            with patch.object(
                                orchestrator,
                                "verify_branch_has_commits",
                                return_value=(True, ""),
                            ):
                                with patch.object(
                                    orchestrator,
                                    "read_plan_stage",
                                    side_effect=staged_read_plan_stage,
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
                # Groups 1 and 3 each ran as a single session; group 2 (single
                # stage) still uses run_stage.
                self.assertEqual(mock_group.call_count, 2)
                self.assertEqual(mock_stage.call_count, 1)

    def test_minimal_isolation_keeps_per_stage_execution(self):
        """minimal isolation does not use run_stage_group."""
        with tempfile.TemporaryDirectory() as repo_root:
            plan_file = self._setup_repo_with_plan(repo_root)
            task = {"id": "demo", "title": "Demo", "plan_file": plan_file}

            with tempfile.TemporaryDirectory() as reports_dir:
                _write_passing(reports_dir, "qa", "review", "cso", "sync-docs")
                with patch.dict(
                    os.environ,
                    {"AET_REPORTS_DIR": reports_dir, "AET_PROJECT_ID": "demo/project"},
                    clear=False,
                ):
                    with patch.object(orchestrator, "run_stage_group") as mock_group:
                        with patch.object(
                            orchestrator, "run_stage", return_value=(0, None, None, "")
                        ) as mock_stage:
                            with patch.object(
                                orchestrator,
                                "verify_branch_has_commits",
                                return_value=(True, ""),
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

            with tempfile.TemporaryDirectory() as reports_dir:
                _write_passing(reports_dir, "qa", "review", "cso", "sync-docs")
                with patch.dict(
                    os.environ,
                    {"AET_REPORTS_DIR": reports_dir, "AET_PROJECT_ID": "demo/project"},
                    clear=False,
                ):
                    with patch.object(orchestrator, "run_stage_group") as mock_group:
                        with patch.object(
                            orchestrator, "run_stage", return_value=(0, None, None, "")
                        ) as mock_stage:
                            with patch.object(
                                orchestrator,
                                "verify_branch_has_commits",
                                return_value=(True, ""),
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

    def test_gate_fails_closed_on_missing_verdict(self):
        """A group session that exits 0 but leaves no qa verdict fails closed.

        The footer breadcrumb must not rescue the run: advancement is gated on
        evidence, not the footer.
        """
        with tempfile.TemporaryDirectory() as repo_root:
            plan_file = self._setup_repo_with_plan(repo_root, stage="plan-approved")
            task = {"id": "demo", "title": "Demo", "plan_file": plan_file}

            with tempfile.TemporaryDirectory() as reports_dir:
                with patch.dict(
                    os.environ,
                    {"AET_REPORTS_DIR": reports_dir, "AET_PROJECT_ID": "demo/project"},
                    clear=False,
                ):
                    with patch.object(
                        orchestrator, "run_stage_group", return_value=(0, None, None, "")
                    ) as mock_group:
                        with patch.object(orchestrator, "run_stage", return_value=(0, None, None, "")):
                            with patch.object(
                                orchestrator,
                                "verify_branch_has_commits",
                                return_value=(True, ""),
                            ):
                                result = orchestrator.process_task(
                                    task, repo_root, _FAKE_ADAPTER, "standard"
                                )

                self.assertFalse(result)
                mock_group.assert_called_once()

    def test_standard_group_failure_returns_false(self):
        """standard isolation returns False when the group session fails."""
        with tempfile.TemporaryDirectory() as repo_root:
            plan_file = self._setup_repo_with_plan(repo_root)
            task = {"id": "demo", "title": "Demo", "plan_file": plan_file}

            with patch.object(orchestrator, "run_stage_group", return_value=(1, None, None, "")):
                result = orchestrator.process_task(
                    task, repo_root, _FAKE_ADAPTER, "standard"
                )

            self.assertFalse(result)


class TestWorkflowDrivenTraversal(unittest.TestCase):
    """process_task walks the stage sequence declared in the workflow file.

    wfd-03: the engine's source of truth is ``workflow.load_workflow()``, not
    the deleted ``pipeline.py`` table. The packaged ``software.json`` must
    reproduce today's walk exactly; variant vocabularies must traverse by
    data alone.
    """

    def _setup_repo(self, repo_root: str, plan_body: str) -> str:
        _init_git_repo(repo_root)
        plan_file = os.path.join(repo_root, "docs", "plans", "demo.md")
        Path(plan_file).parent.mkdir(parents=True, exist_ok=True)
        Path(plan_file).write_text(plan_body, encoding="utf-8")
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

    def _write_workflow(self, repo_root: str, document: dict, name: str = "variant") -> None:
        workflow_dir = Path(repo_root, ".agents", "workflows")
        workflow_dir.mkdir(parents=True, exist_ok=True)
        Path(workflow_dir, f"{name}.json").write_text(
            json.dumps(document), encoding="utf-8"
        )

    def _run(self, task, repo_root, reports_dir, archive_dir):
        env = _gate_env(reports_dir, archive_dir)
        with patch.dict(os.environ, env, clear=False):
            with patch.object(
                orchestrator, "run_stage_group", return_value=(0, None, None, "")
            ) as mock_group:
                with patch.object(
                    orchestrator, "run_stage", return_value=(0, None, None, "")
                ) as mock_stage:
                    with patch.object(
                        orchestrator,
                        "verify_branch_has_commits",
                        return_value=(True, ""),
                    ):
                        with patch.object(
                            orchestrator,
                            "verify_stage_advancement",
                            return_value=(True, ""),
                        ):
                            buf = io.StringIO()
                            with contextlib.redirect_stdout(buf):
                                result = orchestrator.process_task(
                                    task, repo_root, _FAKE_ADAPTER, "standard"
                                )
        return result, mock_group, mock_stage, buf.getvalue()

    def test_full_traversal_from_packaged_file_matches_todays_walk(self):
        """The packaged software.json reproduces the pre-rewiring stage walk."""
        with tempfile.TemporaryDirectory() as repo_root:
            plan_file = self._setup_repo(
                repo_root,
                "---\nid: demo\n---\n\n# Demo\n\n_Stage: plan-approved_\n",
            )
            task = {"id": "demo", "title": "Demo", "plan_file": plan_file}
            with tempfile.TemporaryDirectory() as reports_dir:
                _write_passing(reports_dir, "qa", "review", "cso", "sync-docs")
                with tempfile.TemporaryDirectory() as archive_dir:
                    result, mock_group, mock_stage, _out = self._run(
                        task, repo_root, reports_dir, archive_dir
                    )

        self.assertTrue(result)
        # Groups 1 and 3 run as compound sessions; qa-complete runs solo.
        self.assertEqual(mock_group.call_count, 2)
        span1 = [s.name for s in mock_group.call_args_list[0][0][4]]
        span3 = [s.name for s in mock_group.call_args_list[1][0][4]]
        self.assertEqual(span1, ["plan-approved", "implemented"])
        self.assertEqual(span3, ["reviewed", "secure"])
        mock_stage.assert_called_once()
        stage_args = mock_stage.call_args
        self.assertEqual(stage_args[0][4], ["aet-review"])
        self.assertEqual(stage_args[0][5], "qa-complete")
        self.assertEqual(stage_args[0][6], "reviewed")
        # The verdict kind is read from the stage's evidence binding.
        self.assertEqual(stage_args.kwargs["verdict_kind"], "review")
        self.assertEqual(task.get("stage"), "synced")

    def test_entry_stage_comes_from_workflow_data(self):
        """A plan with no stage breadcrumbs starts at the workflow's entry stage."""
        variant = {
            "version": 1,
            "name": "variant",
            "done_state": "done",
            "stages": [
                {"name": "scoped", "skills": ["aet-implement"], "evidence": None, "gate_key": None},
                {"name": "wrapped", "skills": [], "evidence": None, "gate_key": None},
            ],
            "execution_policy": {"session_groups": [["scoped"]]},
            "routing": {"default": {"harness": "test", "model": None}, "by_stage": {}},
        }
        with tempfile.TemporaryDirectory() as repo_root:
            plan_file = self._setup_repo(
                repo_root,
                "---\nid: demo\nworkflow: variant\n---\n\n# Demo\n",
            )
            self._write_workflow(repo_root, variant)
            task = {"id": "demo", "title": "Demo", "plan_file": plan_file}
            with tempfile.TemporaryDirectory() as reports_dir:
                with tempfile.TemporaryDirectory() as archive_dir:
                    result, mock_group, mock_stage, _out = self._run(
                        task, repo_root, reports_dir, archive_dir
                    )

        self.assertTrue(result)
        mock_group.assert_not_called()
        mock_stage.assert_called_once()
        stage_args = mock_stage.call_args
        self.assertEqual(stage_args[0][4], ["aet-implement"])
        # Entry stage resolved from the workflow file, not a "plan-approved" literal.
        self.assertEqual(stage_args[0][5], "scoped")
        self.assertEqual(stage_args[0][6], "wrapped")
        self.assertIsNone(stage_args.kwargs["verdict_kind"])

    def test_verdict_gate_follows_stage_evidence_not_skill_name(self):
        """An aet-qa-skilled stage with ``evidence: null`` requires no verdict.

        The old skill→verdict map would have failed closed here; the binding
        now lives in the workflow file.
        """
        variant = {
            "version": 1,
            "name": "variant",
            "done_state": "done",
            "stages": [
                {"name": "scoped", "skills": ["aet-qa"], "evidence": None, "gate_key": None},
                {"name": "wrapped", "skills": [], "evidence": None, "gate_key": None},
            ],
            "execution_policy": {"session_groups": [["scoped"]]},
            "routing": {"default": {"harness": "test", "model": None}, "by_stage": {}},
        }
        with tempfile.TemporaryDirectory() as repo_root:
            plan_file = self._setup_repo(
                repo_root,
                "---\nid: demo\nworkflow: variant\n---\n\n# Demo\n",
            )
            self._write_workflow(repo_root, variant)
            task = {"id": "demo", "title": "Demo", "plan_file": plan_file}
            # Deliberately no verdicts written anywhere.
            with tempfile.TemporaryDirectory() as reports_dir:
                with tempfile.TemporaryDirectory() as archive_dir:
                    result, _mock_group, mock_stage, _out = self._run(
                        task, repo_root, reports_dir, archive_dir
                    )

        self.assertTrue(result)
        mock_stage.assert_called_once()

    def test_broken_repo_workflow_file_fails_loudly(self):
        """An unreadable repo-level workflow file fails the run at task start."""
        with tempfile.TemporaryDirectory() as repo_root:
            plan_file = self._setup_repo(
                repo_root,
                "---\nid: demo\n---\n\n# Demo\n\n_Stage: plan-approved_\n",
            )
            workflow_dir = Path(repo_root, ".agents", "workflows")
            workflow_dir.mkdir(parents=True, exist_ok=True)
            Path(workflow_dir, "software.json").write_text("{not json", encoding="utf-8")
            task = {"id": "demo", "title": "Demo", "plan_file": plan_file}
            with tempfile.TemporaryDirectory() as reports_dir:
                with tempfile.TemporaryDirectory() as archive_dir:
                    result, mock_group, mock_stage, out = self._run(
                        task, repo_root, reports_dir, archive_dir
                    )

        self.assertFalse(result)
        mock_group.assert_not_called()
        mock_stage.assert_not_called()
        self.assertIn("Cannot read workflow", out)


class TestProcessTaskCompletionGuards(unittest.TestCase):
    def test_process_task_fails_when_footer_is_terminal_but_branch_empty(self):
        """A stale terminal footer must not mark an empty branch as complete."""
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            plan_file = os.path.join(repo_root, "docs", "plans", "demo.md")
            Path(plan_file).parent.mkdir(parents=True, exist_ok=True)
            Path(plan_file).write_text(
                "---\nid: demo\n---\n\n# Demo\n\n_Stage: synced_\n",
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
            task = {"id": "demo", "title": "Demo", "plan_file": plan_file}
            result = orchestrator.process_task(
                task, repo_root, _FAKE_ADAPTER, "standard"
            )
            self.assertFalse(result)


class TestFinalizeTaskGuards(unittest.TestCase):
    def test_finalize_task_fails_when_branch_has_no_commits(self):
        """A child exit 0 with an empty branch must be treated as a failure."""
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            queue_file = _write_queue(
                repo_root,
                [
                    {
                        "id": "demo",
                        "title": "Demo",
                        "plan_file": "docs/plans/demo.md",
                        "blocked_by": [],
                        "state": "in_progress",
                        "worktree": ".worktrees/demo",
                        "branch": "demo",
                    }
                ],
            )
            subprocess.run(
                ["git", "-C", repo_root, "worktree", "add",
                 os.path.join(repo_root, ".worktrees", "demo"), "-b", "demo"],
                check=True,
                capture_output=True,
            )
            backend = orchestrator._make_backend(queue_file)
            deltas = orchestrator._finalize_task(
                backend, queue_file, "demo", 0, repo_root=repo_root
            )
            self.assertEqual(deltas["failures"], 1)
            data = backend.load()
            task = next((t for t in data["queue"] if t.get("id") == "demo"), None)
            self.assertIsNotNone(task)
            self.assertEqual(task["state"], "failed")


class TestBatchStageEnv(unittest.TestCase):
    def test_run_single_uses_stage_env_over_footer(self):
        """Batch children pass their stored stage so stale footers are ignored."""
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            plan_file = os.path.join(repo_root, "docs", "plans", "demo-plan.md")
            Path(plan_file).parent.mkdir(parents=True, exist_ok=True)
            Path(plan_file).write_text(
                "---\nid: demo\n---\n\n# Demo\n\n_Stage: synced_\n",
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

            captured = {}

            def capture_process(task, *args, **kwargs):
                captured["stage"] = task.get("stage")
                return True

            args = _make_args(repo_root, plan_file)
            with patch.dict(
                os.environ,
                {"AET_EXECUTION_MODE": "unattended", "AET_STAGE": "plan-approved"},
                clear=True,
            ):
                with patch.object(
                    orchestrator, "process_task", side_effect=capture_process
                ):
                    with patch.object(
                        orchestrator, "verify_branch_has_commits", return_value=(True, "")
                    ):
                        exit_code = orchestrator.run_single(args, _FAKE_ADAPTER)

            self.assertEqual(exit_code, 0)
            self.assertEqual(captured["stage"], "plan-approved")

class TestProcessGroupKill(unittest.TestCase):
    """Integration tests for process-group killing on timeout and shutdown."""

    def _write_fake_cli(self, repo_root: str, marker: str) -> str:
        """Create a fake agent CLI that spawns a long-lived grandchild."""
        bin_dir = Path(repo_root) / "bin"
        bin_dir.mkdir()
        fake_kimi = bin_dir / "kimi"
        helper = Path(__file__).parents[1] / "fixtures" / "sleep_until_signaled.py"
        fake_kimi.write_text(
            "#!/usr/bin/env bash\n"
            "# ignore prompt flag and prompt\n"
            f"python3 '{helper}' 300 '{marker}' &\n"
            f"exec python3 '{helper}' 300 '{marker}'\n",
            encoding="utf-8",
        )
        fake_kimi.chmod(0o755)
        return str(fake_kimi)

    def _wait_for_marker(self, marker: str, timeout: float = 15) -> None:
        """Poll until a process with the marker appears."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            result = subprocess.run(
                ["pgrep", "-f", marker], capture_output=True, text=True
            )
            if result.returncode == 0 and result.stdout.strip():
                return
            time.sleep(0.05)
        self.fail(f"Marker process {marker} did not start")

    def _wait_no_marker(self, marker: str, timeout: float = 15) -> None:
        """Poll until no process with the marker remains."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            result = subprocess.run(
                ["pgrep", "-f", marker], capture_output=True, text=True
            )
            if result.returncode != 0 or not result.stdout.strip():
                return
            time.sleep(0.05)
        self.fail(f"Marker process {marker} still alive")

    def _setup_plan_and_queue(self, repo_root: str, task_id: str) -> str:
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

    def test_timeout_kills_grandchild_process_group(self):
        """A timed-out batch child must not leave its grandchild alive."""
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            task_id = "frh-03-timeout"
            marker = f"pg-timeout-{os.getpid()}"
            fake_kimi = self._write_fake_cli(repo_root, marker)
            queue_file = self._setup_plan_and_queue(repo_root, task_id)

            adapter = resolve_cli_adapter(fake_kimi)
            args = argparse.Namespace(
                queue_file=queue_file,
                plan_file=None,
                repo_root=repo_root,
                cli_bin=fake_kimi,
                isolation="minimal",
                max_jobs=1,
                task_timeout=1,
                heartbeat_interval=999,
                on_failure="continue",
            )
            # The task times out, so the orchestrator reports failure.
            exit_code = orchestrator.run_batch(args, adapter)
            self.assertEqual(exit_code, 1)

            self._wait_no_marker(marker)
            self.assertFalse(os.path.isdir(os.path.join(repo_root, ".worktrees", task_id)))

    def test_cleanup_kills_process_groups_on_shutdown(self):
        """A graceful orchestrator shutdown must kill running process groups."""
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            task_id = "frh-03-shutdown"
            marker = f"pg-shutdown-{os.getpid()}"
            fake_kimi = self._write_fake_cli(repo_root, marker)
            queue_file = self._setup_plan_and_queue(repo_root, task_id)

            env = os.environ.copy()
            env["PATH"] = str(Path(fake_kimi).parent) + os.pathsep + env["PATH"]
            cmd = [
                sys.executable,
                str(_ORCHESTRATOR_BIN),
                "--queue-file",
                queue_file,
                "--repo-root",
                repo_root,
                "--cli-bin",
                fake_kimi,
                "--isolation",
                "minimal",
                "--max-jobs",
                "1",
                "--task-timeout",
                "600",
                "--heartbeat-interval",
                "999",
            ]
            proc = subprocess.Popen(cmd, env=env)
            try:
                self._wait_for_marker(marker)
                proc.send_signal(signal.SIGTERM)
                try:
                    proc.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
                    self.fail("Orchestrator did not shut down after SIGTERM")

                self._wait_no_marker(marker)
                self.assertFalse(
                    os.path.isdir(os.path.join(repo_root, ".worktrees", task_id))
                )
            except Exception:
                proc.kill()
                raise


class TestStageTelemetry(unittest.TestCase):
    """Stage-session telemetry emission (frh-09)."""

    # Tests in this class assert exact session/record counts, so their plans
    # take the documented skip path for both gates (telemetry, not gate
    # routing, is under test here).
    _SKIP_GATES_FM = (
        "security_review: skipped\n"
        "security_review_reason: telemetry fixture — gate routing not under test\n"
        "docs_sync: skipped\n"
        "docs_sync_reason: telemetry fixture — gate routing not under test\n"
    )

    def _setup_repo_with_plan(
        self, repo_root: str, stage: str, frontmatter_extra: str = ""
    ) -> str:
        _init_git_repo(repo_root)
        plan_file = os.path.join(repo_root, "docs", "plans", "demo.md")
        Path(plan_file).parent.mkdir(parents=True, exist_ok=True)
        Path(plan_file).write_text(
            f"---\nid: demo\n{frontmatter_extra}---\n\n# Demo\n\n_Stage: {stage}_\n",
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

    def _stage_records(self, logger, task_id: str = "demo") -> list[dict]:
        return [
            r
            for r in telemetry.read_jsonl(logger.task_log_path(task_id))
            if r.get("type") == "stage"
        ]

    def test_stage_record_emitted_per_session(self):
        """A single-stage (per-stage) session emits exactly one stage record."""
        with tempfile.TemporaryDirectory() as repo_root:
            plan_file = self._setup_repo_with_plan(
                repo_root, "qa-complete", frontmatter_extra=self._SKIP_GATES_FM
            )
            with tempfile.TemporaryDirectory() as archive_dir:
                with tempfile.TemporaryDirectory() as reports_dir:
                    env = _gate_env(reports_dir, archive_dir)
                    with patch.dict(os.environ, env, clear=False):
                        logger = telemetry.RunLogger(repo_root, run_id="r1")
                        task = {"id": "demo", "title": "Demo", "plan_file": plan_file}
                        _write_passing(reports_dir, "review")

                        with patch.object(
                            orchestrator, "run_stage", return_value=(0, None, None, "")
                        ) as mock_stage:
                            with patch.object(
                                orchestrator,
                                "verify_branch_has_commits",
                                return_value=(True, ""),
                            ):
                                with patch.object(
                                    orchestrator,
                                    "verify_stage_advancement",
                                    return_value=(True, ""),
                                ):
                                    result = orchestrator.process_task(
                                        task,
                                        repo_root,
                                        _FAKE_ADAPTER,
                                        "full",
                                        logger=logger,
                                    )

                        self.assertTrue(result)
                        mock_stage.assert_called_once()
                        records = self._stage_records(logger)
                        self.assertEqual(len(records), 1)
                        self.assertEqual(records[0]["stage"], "reviewed")
                        self.assertIsNone(records[0]["stages"])
                        self.assertEqual(records[0]["result"], "success")
                        self.assertEqual(records[0]["isolation_level"], "full")
                        self.assertEqual(records[0]["task_id"], "demo")

    def test_group_session_record_carries_stage_span(self):
        """A standard-isolation group session records the stage span it covered."""
        with tempfile.TemporaryDirectory() as repo_root:
            plan_file = self._setup_repo_with_plan(
                repo_root, "plan-approved", frontmatter_extra=self._SKIP_GATES_FM
            )
            with tempfile.TemporaryDirectory() as archive_dir:
                with tempfile.TemporaryDirectory() as reports_dir:
                    env = _gate_env(reports_dir, archive_dir)
                    with patch.dict(os.environ, env, clear=False):
                        logger = telemetry.RunLogger(repo_root, run_id="r1")
                        task = {"id": "demo", "title": "Demo", "plan_file": plan_file}
                        _write_passing(reports_dir, "qa", "review")

                        with patch.object(orchestrator, "run_stage_group", return_value=(0, None, None, "")):
                            with patch.object(orchestrator, "run_stage", return_value=(0, None, None, "")):
                                with patch.object(
                                    orchestrator,
                                    "verify_branch_has_commits",
                                    return_value=(True, ""),
                                ):
                                    with patch.object(
                                        orchestrator,
                                        "verify_stage_advancement",
                                        return_value=(True, ""),
                                    ):
                                        result = orchestrator.process_task(
                                            task,
                                            repo_root,
                                            _FAKE_ADAPTER,
                                            "standard",
                                            logger=logger,
                                        )

                        self.assertTrue(result)
                        group_records = [
                            r for r in self._stage_records(logger) if r.get("stages")
                        ]
                        self.assertEqual(len(group_records), 1)
                        self.assertEqual(group_records[0]["stage"], "qa-complete")
                        self.assertEqual(
                            group_records[0]["stages"], ["plan-approved", "implemented"]
                        )
                        self.assertEqual(group_records[0]["isolation_level"], "standard")

    def test_failed_session_emits_failure_stage_record(self):
        """A failing session still emits a stage record marked as failure."""
        with tempfile.TemporaryDirectory() as repo_root:
            plan_file = self._setup_repo_with_plan(repo_root, "qa-complete")
            with tempfile.TemporaryDirectory() as archive_dir:
                env = _archive_env(archive_dir)
                with patch.dict(os.environ, env, clear=False):
                    logger = telemetry.RunLogger(repo_root, run_id="r1")
                task = {"id": "demo", "title": "Demo", "plan_file": plan_file}

                with patch.object(orchestrator, "run_stage", return_value=(1, None, None, "")):
                    result = orchestrator.process_task(
                        task, repo_root, _FAKE_ADAPTER, "full", logger=logger
                    )

                self.assertFalse(result)
                records = self._stage_records(logger)
                self.assertEqual(len(records), 1)
                self.assertEqual(records[0]["exit_code"], 1)
                self.assertEqual(records[0]["result"], "failure")
                self.assertEqual(records[0]["stage"], "reviewed")

    def test_stage_record_records_files_and_commits(self):
        """Post-session git stats capture files modified and commits created."""
        with tempfile.TemporaryDirectory() as repo_root:
            plan_file = self._setup_repo_with_plan(
                repo_root, "qa-complete", frontmatter_extra=self._SKIP_GATES_FM
            )
            with tempfile.TemporaryDirectory() as archive_dir:
                with tempfile.TemporaryDirectory() as reports_dir:
                    env = _gate_env(reports_dir, archive_dir)
                    with patch.dict(os.environ, env, clear=False):
                        logger = telemetry.RunLogger(repo_root, run_id="r1")
                        task = {"id": "demo", "title": "Demo", "plan_file": plan_file}
                        _write_passing(reports_dir, "review")

                        def run_stage_making_commit(
                            _adapter,
                            _repo_root,
                            _plan_file,
                            worktree_dir,
                            _skills,
                            _current,
                            _next,
                            **_kwargs,
                        ):
                            Path(worktree_dir, "feature.txt").write_text(
                                "x", encoding="utf-8"
                            )
                            subprocess.run(
                                ["git", "-C", worktree_dir, "add", "."],
                                check=True,
                                capture_output=True,
                            )
                            subprocess.run(
                                ["git", "-C", worktree_dir, "commit", "-q", "-m", "feature"],
                                check=True,
                                capture_output=True,
                            )
                            return (0, None, None, "")

                        with patch.object(
                            orchestrator, "run_stage", side_effect=run_stage_making_commit
                        ):
                            with patch.object(
                                orchestrator,
                                "verify_branch_has_commits",
                                return_value=(True, ""),
                            ):
                                with patch.object(
                                    orchestrator,
                                    "verify_stage_advancement",
                                    return_value=(True, ""),
                                ):
                                    result = orchestrator.process_task(
                                        task,
                                        repo_root,
                                        _FAKE_ADAPTER,
                                        "full",
                                        logger=logger,
                                    )

                        self.assertTrue(result)
                        records = self._stage_records(logger)
                        self.assertEqual(len(records), 1)
                        self.assertEqual(records[0]["files_modified"], ["feature.txt"])
                        self.assertEqual(records[0]["commits_created"], 1)


class TestEvidenceGates(unittest.TestCase):
    """Fail-closed evidence gates and evidence-driven advancement (frh-11)."""

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

    def _run_group(
        self,
        repo_root: str,
        plan_file: str,
        reports_dir: str,
        archive_dir: str,
    ) -> tuple[bool, "telemetry.RunLogger"]:
        env = _gate_env(reports_dir, archive_dir)
        with patch.dict(os.environ, env, clear=False):
            logger = telemetry.RunLogger(repo_root, run_id="r1")
            task = {"id": "demo", "title": "Demo", "plan_file": plan_file}
            with patch.object(orchestrator, "run_stage_group", return_value=(0, None, None, "")):
                with patch.object(orchestrator, "run_stage", return_value=(0, None, None, "")):
                    with patch.object(
                        orchestrator,
                        "verify_branch_has_commits",
                        return_value=(True, ""),
                    ):
                        with patch.object(
                            orchestrator,
                            "verify_stage_advancement",
                            return_value=(True, ""),
                        ):
                            result = orchestrator.process_task(
                                task,
                                repo_root,
                                _FAKE_ADAPTER,
                                "standard",
                                logger=logger,
                            )
        return result, logger

    def test_gate_fails_on_schema_invalid_verdict(self):
        """A schema-invalid qa verdict (missing a required key) fails the gate."""
        with tempfile.TemporaryDirectory() as repo_root:
            plan_file = self._setup_repo_with_plan(repo_root)
            with tempfile.TemporaryDirectory() as reports_dir:
                with tempfile.TemporaryDirectory() as archive_dir:
                    # Write a malformed qa verdict directly, bypassing validation.
                    path = evidence.evidence_path(
                        task_id="demo",
                        kind="qa",
                        project_slug="demo/project",
                        reports_root=reports_dir,
                    )
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(
                        json.dumps(
                            {
                                "task_id": "demo",
                                "stage": "qa-complete",
                                "skill": "aet-qa",
                                "verdict": "pass",
                                "summary": "missing counts",
                                "generated_at": "2026-07-09T20:00:00Z",
                            }
                        ),
                        encoding="utf-8",
                    )
                    result, _ = self._run_group(
                        repo_root, plan_file, reports_dir, archive_dir
                    )
            self.assertFalse(result)

    def test_gate_fails_on_failing_verdict(self):
        """A well-formed qa verdict with verdict 'fail' fails the gate."""
        with tempfile.TemporaryDirectory() as repo_root:
            plan_file = self._setup_repo_with_plan(repo_root)
            with tempfile.TemporaryDirectory() as reports_dir:
                with tempfile.TemporaryDirectory() as archive_dir:
                    _write_verdict(reports_dir, "qa", "fail")
                    result, _ = self._run_group(
                        repo_root, plan_file, reports_dir, archive_dir
                    )
            self.assertFalse(result)

    def test_group_advancement_determined_by_evidence_not_footer(self):
        """A stale footer does not block advancement when verdicts pass."""
        with tempfile.TemporaryDirectory() as repo_root:
            # Footer stays at plan-approved; only evidence drives advancement.
            plan_file = self._setup_repo_with_plan(repo_root, stage="plan-approved")
            with tempfile.TemporaryDirectory() as reports_dir:
                with tempfile.TemporaryDirectory() as archive_dir:
                    _write_passing(reports_dir, "qa", "review", "cso", "sync-docs")
                    env = _gate_env(reports_dir, archive_dir)
                    with patch.dict(os.environ, env, clear=False):
                        task = {"id": "demo", "title": "Demo", "plan_file": plan_file}
                        with patch.object(
                            orchestrator, "run_stage_group", return_value=(0, None, None, "")
                        ) as mock_group:
                            with patch.object(
                                orchestrator, "run_stage", return_value=(0, None, None, "")
                            ) as mock_stage:
                                with patch.object(
                                    orchestrator,
                                    "verify_branch_has_commits",
                                    return_value=(True, ""),
                                ):
                                    with patch.object(
                                        orchestrator,
                                        "verify_stage_advancement",
                                        return_value=(True, ""),
                                    ):
                                        result = orchestrator.process_task(
                                            task,
                                            repo_root,
                                            _FAKE_ADAPTER,
                                            "standard",
                                        )
                    self.assertTrue(result)
                    # Group sessions run for both multi-stage groups (1 and 3).
                    self.assertEqual(mock_group.call_count, 2)
                    mock_stage.assert_called()

    def test_qa_verdict_derives_test_run_record(self):
        """A passing qa verdict derives a test_run telemetry record."""
        with tempfile.TemporaryDirectory() as repo_root:
            plan_file = self._setup_repo_with_plan(repo_root)
            with tempfile.TemporaryDirectory() as reports_dir:
                with tempfile.TemporaryDirectory() as archive_dir:
                    _write_verdict(
                        reports_dir,
                        "qa",
                        "pass",
                        test_command="pytest -k smoke",
                        tests_total=12,
                        tests_passed=11,
                        tests_failed=1,
                    )
                    _write_passing(reports_dir, "review", "cso", "sync-docs")
                    result, logger = self._run_group(
                        repo_root, plan_file, reports_dir, archive_dir
                    )
                    records = telemetry.read_jsonl(logger.task_log_path("demo"))
                    test_runs = [r for r in records if r.get("type") == "test_run"]
            self.assertTrue(result)
            self.assertEqual(len(test_runs), 1)
            self.assertEqual(test_runs[0]["test_command"], "pytest -k smoke")
            self.assertEqual(test_runs[0]["tests_total"], 12)
            self.assertEqual(test_runs[0]["tests_passed"], 11)
            self.assertEqual(test_runs[0]["tests_failed"], 1)
            self.assertIsNone(test_runs[0]["duration_seconds"])

    def test_verdict_emitter_writes_source_verdict(self):
        """A verdict-derived record declares itself claimed, not observed."""
        with tempfile.TemporaryDirectory() as repo_root:
            plan_file = self._setup_repo_with_plan(repo_root)
            with tempfile.TemporaryDirectory() as reports_dir:
                with tempfile.TemporaryDirectory() as archive_dir:
                    _write_verdict(
                        reports_dir,
                        "qa",
                        "pass",
                        test_command="pytest -k smoke",
                        tests_total=12,
                        tests_passed=11,
                        tests_failed=1,
                    )
                    _write_passing(reports_dir, "review", "cso", "sync-docs")
                    _result, logger = self._run_group(
                        repo_root, plan_file, reports_dir, archive_dir
                    )
                    records = telemetry.read_jsonl(logger.task_log_path("demo"))
                    test_runs = [r for r in records if r.get("type") == "test_run"]
            self.assertEqual(len(test_runs), 1)
            self.assertEqual(test_runs[0]["source"], "verdict")

    def test_verdict_emitter_no_longer_hardcodes_exit_code_zero(self):
        """A claim is not a measurement: exit_code is null and result unknown."""
        with tempfile.TemporaryDirectory() as repo_root:
            plan_file = self._setup_repo_with_plan(repo_root)
            with tempfile.TemporaryDirectory() as reports_dir:
                with tempfile.TemporaryDirectory() as archive_dir:
                    _write_verdict(
                        reports_dir,
                        "qa",
                        "pass",
                        test_command="pytest -k smoke",
                        tests_total=12,
                        tests_passed=12,
                        tests_failed=0,
                    )
                    _write_passing(reports_dir, "review", "cso", "sync-docs")
                    _result, logger = self._run_group(
                        repo_root, plan_file, reports_dir, archive_dir
                    )
                    records = telemetry.read_jsonl(logger.task_log_path("demo"))
                    test_runs = [r for r in records if r.get("type") == "test_run"]
            self.assertEqual(len(test_runs), 1)
            self.assertIsNone(test_runs[0]["exit_code"])
            self.assertEqual(test_runs[0]["result"], "unknown")

    def test_qa_verdict_classifies_full_suite_scope(self):
        """A suite-wide test command is classified as full-suite scope."""
        with tempfile.TemporaryDirectory() as repo_root:
            plan_file = self._setup_repo_with_plan(repo_root)
            with tempfile.TemporaryDirectory() as reports_dir:
                with tempfile.TemporaryDirectory() as archive_dir:
                    _write_verdict(
                        reports_dir,
                        "qa",
                        "pass",
                        test_command="make validate",
                        tests_total=42,
                        tests_passed=42,
                        tests_failed=0,
                    )
                    _write_passing(reports_dir, "review", "cso", "sync-docs")
                    result, logger = self._run_group(
                        repo_root, plan_file, reports_dir, archive_dir
                    )
                    records = telemetry.read_jsonl(logger.task_log_path("demo"))
                    test_runs = [r for r in records if r.get("type") == "test_run"]
            self.assertTrue(result)
            self.assertEqual(len(test_runs), 1)
            self.assertEqual(test_runs[0]["scope"], "full-suite")
            self.assertEqual(test_runs[0]["tests_total"], 42)

    def test_qa_verdict_classifies_impact_scope(self):
        """A path-specific test command is classified as impact scope."""
        with tempfile.TemporaryDirectory() as repo_root:
            plan_file = self._setup_repo_with_plan(repo_root)
            with tempfile.TemporaryDirectory() as reports_dir:
                with tempfile.TemporaryDirectory() as archive_dir:
                    _write_verdict(
                        reports_dir,
                        "qa",
                        "pass",
                        test_command="pytest tests/test_x.py",
                        tests_total=7,
                        tests_passed=7,
                        tests_failed=0,
                    )
                    _write_passing(reports_dir, "review", "cso", "sync-docs")
                    result, logger = self._run_group(
                        repo_root, plan_file, reports_dir, archive_dir
                    )
                    records = telemetry.read_jsonl(logger.task_log_path("demo"))
                    test_runs = [r for r in records if r.get("type") == "test_run"]
            self.assertTrue(result)
            self.assertEqual(len(test_runs), 1)
            self.assertEqual(test_runs[0]["scope"], "impact")
            self.assertEqual(test_runs[0]["tests_total"], 7)


class TestWireTestRunProvenance(unittest.TestCase):
    """Wire-derived test_run records declare themselves observed (ADR-051)."""

    def _write_wire_session(self, root: Path, command: str) -> Path:
        """Materialize a session dir holding one paired test invocation."""
        session_dir = root / "sessions" / "wd_proj" / "session_demo"
        wire = session_dir / "agents" / "main" / "wire.jsonl"
        wire.parent.mkdir(parents=True, exist_ok=True)
        call = {
            "type": "context.append_loop_event",
            "event": {
                "type": "tool.call",
                "uuid": "c1",
                "toolCallId": "c1",
                "name": "Bash",
                "args": {"command": command},
            },
            "time": 1784049800000,
        }
        result = {
            "type": "context.append_loop_event",
            "event": {
                "type": "tool.result",
                "parentUuid": "c1",
                "toolCallId": "c1",
                "result": {"output": "631 passed"},
            },
            "time": 1784049845000,
        }
        wire.write_text(
            json.dumps(call) + "\n" + json.dumps(result) + "\n", encoding="utf-8"
        )
        return session_dir

    def test_wire_emitter_writes_source_wire(self):
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            with tempfile.TemporaryDirectory() as archive_dir:
                with patch.dict(
                    os.environ,
                    {"AET_TELEMETRY_ARCHIVE_DIR": archive_dir},
                    clear=False,
                ):
                    logger = telemetry.RunLogger(repo_root, run_id="r1")
                    with patch.object(
                        orchestrator.session_log,
                        "extract_test_invocations",
                        return_value=[
                            {
                                "command": "python3 -m pytest tests/ -q",
                                "start_time": "2026-07-28T12:00:00Z",
                                "end_time": "2026-07-28T12:00:45Z",
                                "duration_seconds": 45.0,
                                "exit_code": 0,
                            }
                        ],
                    ):
                        orchestrator._emit_session_test_runs(
                            logger,
                            "demo",
                            "docs/plans/demo.md",
                            "implemented",
                            "kimi",
                            "session_demo",
                            repo_root,
                        )
                    records = telemetry.read_jsonl(logger.task_log_path("demo"))
            test_runs = [r for r in records if r.get("type") == "test_run"]
            self.assertEqual(len(test_runs), 1)
            self.assertEqual(test_runs[0]["source"], "wire")
            self.assertEqual(test_runs[0]["duration_seconds"], 45.0)
            self.assertEqual(test_runs[0]["result"], "success")


class _StubPopen:
    """subprocess.Popen stand-in for _run_with_live_tee: canned output + exit code."""

    def __init__(self, output: str = "", returncode: int = 0):
        self.stdout = io.StringIO(output)
        self._returncode = returncode

    def wait(self):
        return self._returncode


class _InstantProc:
    """A subprocess.Popen stand-in that has already exited successfully."""

    pid = 99999

    def poll(self):
        return 0

    def wait(self, timeout=None):
        return 0


class TestBatchLivePickupAndExit(unittest.TestCase):
    """run_batch frontier pickup and exit-when-idle behavior (frh-16)."""

    def _init_batch_repo(self, repo_root: str, tasks: list[dict]) -> str:
        """Init a repo, commit any referenced plan files, and write the queue."""
        _init_git_repo(repo_root)
        for task in tasks:
            plan_file = task.get("plan_file")
            if not plan_file:
                continue
            abs_plan = os.path.join(repo_root, plan_file)
            Path(abs_plan).parent.mkdir(parents=True, exist_ok=True)
            Path(abs_plan).write_text(
                f"---\nid: {task['id']}\n---\n\n# {task['id']}\n\n_Stage: plan-approved_\n",
                encoding="utf-8",
            )
        subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
        subprocess.run(
            ["git", "-C", repo_root, "commit", "-q", "-m", "add plans"], check=True
        )
        subprocess.run(
            ["git", "-C", repo_root, "update-ref", "refs/remotes/origin/main", "HEAD"],
            check=True,
        )
        return _write_queue(repo_root, tasks)

    def _merge_external_blocker(self, repo_root: str, branch: str) -> None:
        """Create ``branch`` with a commit that is an ancestor of origin/main."""
        subprocess.run(
            ["git", "-C", repo_root, "checkout", "-q", "-b", branch], check=True
        )
        Path(repo_root, f"{branch}.txt").write_text("x", encoding="utf-8")
        subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
        subprocess.run(
            ["git", "-C", repo_root, "commit", "-q", "-m", f"{branch} work"],
            check=True,
        )
        subprocess.run(["git", "-C", repo_root, "checkout", "-q", "main"], check=True)
        subprocess.run(
            ["git", "-C", repo_root, "merge", "--ff-only", branch],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", repo_root, "update-ref", "refs/remotes/origin/main", "HEAD"],
            check=True,
        )

    def _run_batch(self, args, adapter, timeout: float = 10):
        """Run run_batch in a thread; return (rc, stdout, timed_out)."""
        result = {"rc": None, "out": ""}
        orchestrator._shutdown_requested = False

        def target():
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                result["rc"] = orchestrator.run_batch(args, adapter)
            result["out"] = buf.getvalue()

        thread = threading.Thread(target=target)
        thread.start()
        thread.join(timeout)
        if thread.is_alive():
            orchestrator._shutdown_requested = True
            thread.join(2)
            return None, result["out"], True
        return result["rc"], result["out"], False

    @staticmethod
    def _patch_child_spawn(side_effect=None):
        """Patch only the long-running child spawn in run_batch.

        run_batch spawns each task's child orchestrator with
        ``start_new_session=True``; every other subprocess goes through
        ``subprocess.run`` (aet-state transitions, git) and must stay real so
        the queue and worktrees are actually mutated. We therefore delegate any
        non-session call to the real ``subprocess.Popen``.
        """
        real_popen = subprocess.Popen

        def fake_popen(*a, **kw):
            if kw.get("start_new_session"):
                if side_effect is not None:
                    return side_effect(*a, **kw)
                return _InstantProc()
            return real_popen(*a, **kw)

        return patch.object(orchestrator.subprocess, "Popen", side_effect=fake_popen)

    def _make_args(self, repo_root: str, queue_file: str, max_jobs: int):
        return argparse.Namespace(
            queue_file=queue_file,
            plan_file=None,
            repo_root=repo_root,
            cli_bin="echo",
            isolation="minimal",
            max_jobs=max_jobs,
            task_timeout=60,
            heartbeat_interval=999,
            on_failure="continue",
        )

    def test_batch_exits_with_report_when_only_awaiting_merge_remains(self):
        """A batch with only awaiting_merge tasks exits 0 with a leftover report.

        Without the exit-when-idle condition the loop spins forever on
        ``time.sleep(0.2)`` because ``awaiting_merge`` is non-terminal.
        """
        with tempfile.TemporaryDirectory() as repo_root:
            with tempfile.TemporaryDirectory() as archive_dir:
                tasks = [
                    {
                        "id": "alpha",
                        "title": "alpha",
                        "plan_file": "docs/plans/alpha.md",
                        "blocked_by": [],
                        "state": "ready",
                    }
                ]
                queue_file = self._init_batch_repo(repo_root, tasks)
                args = self._make_args(repo_root, queue_file, max_jobs=1)

                env = {
                    "AET_TELEMETRY_ARCHIVE_DIR": archive_dir,
                    "AET_PROJECT_ID": "demo/project",
                }
                with patch.dict(os.environ, env, clear=False):
                    with self._patch_child_spawn():
                        with patch.object(
                            orchestrator,
                            "verify_branch_has_commits",
                            return_value=(True, ""),
                        ):
                            rc, out, timed_out = self._run_batch(args, _FAKE_ADAPTER)

                self.assertFalse(
                    timed_out, "run_batch spun instead of exiting when idle"
                )
                self.assertEqual(rc, 0)
                self.assertIn("awaiting merge", out)

                with open(queue_file, encoding="utf-8") as f:
                    queue = json.load(f)
                task = next(t for t in queue["tasks"] if t["id"] == "alpha")
                self.assertEqual(task["state"], "awaiting_merge")

    def test_batch_spawns_task_promoted_mid_run(self):
        """A dependent promoted to ready while the batch runs is spawned.

        An external actor (here, the merge of an already-merged blocker) drives
        the forward frontier. A dependent still at ``planned`` must be promoted
        by the frontier and then picked up by the spawn loop on a later pass.
        """
        with tempfile.TemporaryDirectory() as repo_root:
            with tempfile.TemporaryDirectory() as archive_dir:
                tasks = [
                    {
                        "id": "alpha",
                        "title": "alpha",
                        "plan_file": "docs/plans/alpha.md",
                        "blocked_by": [],
                        "state": "ready",
                    },
                    {
                        "id": "blocker",
                        "title": "blocker",
                        "state": "awaiting_merge",
                        "branch": "blocker-branch",
                        "blocks": ["dependent"],
                    },
                    {
                        "id": "dependent",
                        "title": "dependent",
                        "plan_file": "docs/plans/dependent.md",
                        "blocked_by": ["blocker"],
                        "pending_blockers": 1,
                        "state": "planned",
                    },
                ]
                queue_file = self._init_batch_repo(repo_root, tasks)
                self._merge_external_blocker(repo_root, "blocker-branch")

                aet_state_bin = str(
                    Path(__file__).parents[2] / "src" / "aet" / "cli" / "aet_state.py"
                )

                def fake_popen(cmd, **kwargs):
                    if "--plan-file" in cmd:
                        plan = cmd[cmd.index("--plan-file") + 1]
                        if os.path.basename(plan) == "alpha.md":
                            # Simulate the blocker being merge-verified while
                            # the batch is alive; the frontier promotes the
                            # dependent through the real aet-state code path.
                            subprocess.run(
                                [
                                    sys.executable,
                                    aet_state_bin,
                                    "record-merge",
                                    "blocker",
                                    queue_file,
                                ],
                                cwd=repo_root,
                                check=True,
                                capture_output=True,
                            )
                    return _InstantProc()

                args = self._make_args(repo_root, queue_file, max_jobs=2)
                env = {
                    "AET_TELEMETRY_ARCHIVE_DIR": archive_dir,
                    "AET_PROJECT_ID": "demo/project",
                }
                with patch.dict(os.environ, env, clear=False):
                    with self._patch_child_spawn(side_effect=fake_popen):
                        with patch.object(
                            orchestrator,
                            "verify_branch_has_commits",
                            return_value=(True, ""),
                        ):
                            rc, out, timed_out = self._run_batch(args, _FAKE_ADAPTER)

                self.assertFalse(timed_out, "run_batch spun instead of exiting")
                self.assertEqual(rc, 0)

                with open(queue_file, encoding="utf-8") as f:
                    queue = json.load(f)
                by_id = {t["id"]: t for t in queue["tasks"]}
                # The blocker was sealed to history by record-merge.
                self.assertNotIn("blocker", by_id)
                self.assertEqual(by_id["alpha"]["state"], "awaiting_merge")
                # Dependent reached awaiting_merge only by being promoted to
                # ready mid-batch and then spawned by the loop.
                self.assertEqual(by_id["dependent"]["state"], "awaiting_merge")
                self.assertIn("awaiting merge", out)


class TestStagePromptValidationDiscipline(unittest.TestCase):
    """One-shot stage sessions must run validations foreground (session report:
    a stage agent backgrounding its own validations ended its turn with zero
    commits, producing a false completion)."""

    def test_single_stage_prompt_requires_foreground_validations(self):
        prompt = orchestrator.build_prompt(
            ["aet-implement"], "docs/plans/x.md", "plan-approved", "implemented"
        )
        self.assertIn("foreground", prompt)
        self.assertIn("never background validations", prompt)

    def test_stage_group_prompt_requires_foreground_validations(self):
        stages = [
            WorkflowStage(
                name="plan-approved",
                skills=["aet-implement"],
                evidence=None,
                gate_key=None,
            ),
            WorkflowStage(
                name="implemented", skills=["aet-qa"], evidence=None, gate_key=None
            ),
        ]
        workflow = Workflow(
            version=1,
            name="test",
            done_state="done",
            stages=stages,
            stage_map={s.name: s for s in stages},
            execution_policy=ExecutionPolicy(
                session_groups=[["plan-approved", "implemented"]]
            ),
            routing=Routing(default={"harness": "test", "model": None}, by_stage={}),
        )
        prompt = orchestrator.build_stage_group_prompt(
            "docs/plans/x.md", stages, workflow
        )
        self.assertIn("foreground", prompt)
        self.assertIn("never background validations", prompt)

    def test_single_stage_prompt_contains_no_state_mutation_duty(self):
        """The agent must not be asked to mutate plan footer, status, or queue."""
        prompt = orchestrator.build_prompt(
            ["aet-implement"], "docs/plans/x.md", "plan-approved", "implemented"
        )
        self.assertNotIn("update the plan footer", prompt)
        self.assertNotIn("footer", prompt.lower())
        self.assertNotIn("status", prompt.lower())
        self.assertNotIn("queue", prompt.lower())

    def test_stage_group_prompt_contains_no_state_mutation_duty(self):
        """The compound prompt must not ask the agent to mutate footer/status/queue."""
        stages = [
            WorkflowStage(
                name="plan-approved",
                skills=["aet-implement"],
                evidence=None,
                gate_key=None,
            ),
            WorkflowStage(
                name="implemented", skills=["aet-qa"], evidence=None, gate_key=None
            ),
        ]
        workflow = Workflow(
            version=1,
            name="test",
            done_state="done",
            stages=stages,
            stage_map={s.name: s for s in stages},
            execution_policy=ExecutionPolicy(
                session_groups=[["plan-approved", "implemented"]]
            ),
            routing=Routing(default={"harness": "test", "model": None}, by_stage={}),
        )
        prompt = orchestrator.build_stage_group_prompt(
            "docs/plans/x.md", stages, workflow
        )
        self.assertNotIn("update the plan footer", prompt)
        self.assertNotIn("footer", prompt.lower())
        self.assertNotIn("status", prompt.lower())
        self.assertNotIn("queue", prompt.lower())


class TestBatchIntegrityRefusal(unittest.TestCase):
    """A tampered queue must stop the batch with a clean refusal, not a
    traceback (ADR-024: mutating paths fail closed and name the remedy)."""

    @staticmethod
    def _stamp_and_tamper(queue_file: str) -> None:
        """Restamp the wrapper queue like write_queue would, then hand-edit."""
        import hashlib

        with open(queue_file, encoding="utf-8") as f:
            data = json.load(f)
        canon = json.dumps(
            data["tasks"], sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )
        data["revision"] = 1
        data["content_hash"] = hashlib.sha256(canon.encode()).hexdigest()
        with open(queue_file, "w", encoding="utf-8") as f:
            json.dump(data, f)
        data["tasks"][0]["title"] = "hand edited"
        with open(queue_file, "w", encoding="utf-8") as f:
            json.dump(data, f)

    def test_run_batch_refuses_cleanly_on_tampered_queue(self):
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            queue_file = _write_queue(
                repo_root,
                [
                    {
                        "id": "t1",
                        "title": "t1",
                        "plan_file": "docs/plans/t1.md",
                        "blocked_by": [],
                        "state": "ready",
                    }
                ],
            )
            self._stamp_and_tamper(queue_file)
            args = argparse.Namespace(
                queue_file=queue_file,
                plan_file=None,
                repo_root=repo_root,
                cli_bin="echo",
                isolation="standard",
                max_jobs=1,
                task_timeout=60,
                heartbeat_interval=60,
                on_failure="continue",
            )
            env = {
                "AET_TELEMETRY_ARCHIVE_DIR": os.path.join(repo_root, "telemetry")
            }
            buf = io.StringIO()
            with patch.dict(os.environ, env):
                with contextlib.redirect_stderr(buf):
                    rc = orchestrator.run_batch(args, _FAKE_ADAPTER)

            self.assertEqual(rc, 1)
            err = buf.getvalue()
            self.assertIn("queue modified outside aet state", err)
            self.assertIn("aet state heal --apply", err)


class TestUsageCapture(unittest.TestCase):
    """Stage sessions capture CLI usage output into telemetry records (uct-01)."""

    _STUB_ENVELOPE = (
        '[{"type":"result","subtype":"success","total_cost_usd":0.0123,'
        '"usage":{"input_tokens":100,"cache_creation_input_tokens":50,'
        '"cache_read_input_tokens":10,"output_tokens":25}}]'
    )

    def _stub_cli(self, directory: str, body: str) -> str:
        path = Path(directory, "stub-cli")
        path.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
        path.chmod(0o755)
        return str(path)

    def _claude_stub_adapter(self, directory: str) -> CLIAdapter:
        bin_path = self._stub_cli(directory, f"echo '{self._STUB_ENVELOPE}'")
        return CLIAdapter(
            name="claude",
            bin=bin_path,
            prompt_flag="-p",
            workdir_flag=None,
            headless_flag=None,
            usage_mode="json-envelope",
        )

    def test_run_stage_returns_exit_code_and_parsed_usage(self):
        with tempfile.TemporaryDirectory() as tmp:
            adapter = self._claude_stub_adapter(tmp)
            exit_code, usage, session_dir, _output = orchestrator.run_stage(
                adapter, tmp, "plan.md", tmp, ["skill"], "a", "b"
            )
        self.assertEqual(exit_code, 0)
        self.assertIsNotNone(usage)
        # 100 + 50 (cache creation) + 10 (cache read) input-side; 25 output.
        self.assertEqual(usage["total_tokens"], 185)
        self.assertAlmostEqual(usage["cost_usd"], 0.0123)

    def test_run_stage_without_usage_mode_returns_none_usage(self):
        with tempfile.TemporaryDirectory() as tmp:
            exit_code, usage, session_dir, _output = orchestrator.run_stage(
                _FAKE_ADAPTER, tmp, "plan.md", tmp, ["skill"], "a", "b"
            )
        self.assertEqual(exit_code, 0)
        self.assertIsNone(usage)

    def test_live_output_still_streams_to_terminal(self):
        with tempfile.TemporaryDirectory() as tmp:
            bin_path = self._stub_cli(tmp, "echo marker-line-from-stub")
            adapter = CLIAdapter(
                name="test",
                bin=bin_path,
                prompt_flag="-p",
                workdir_flag=None,
                headless_flag=None,
            )
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                orchestrator.run_stage(adapter, tmp, "plan.md", tmp, ["s"], "a", "b")
        self.assertIn("marker-line-from-stub", buf.getvalue())

    def test_emit_stage_session_records_usage_fields(self):
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            logger = telemetry.RunLogger(repo_root, run_id="r1")
            usage = {
                "input_tokens": 160,
                "output_tokens": 25,
                "total_tokens": 185,
                "cost_usd": 0.0123,
            }
            orchestrator._emit_stage_session(
                logger,
                "demo",
                "docs/plans/demo.md",
                "claude",
                "full",
                "implemented",
                None,
                repo_root,
                "2026-07-12T00:00:00Z",
                "2026-07-12T00:01:00Z",
                0,
                usage=usage,
            )
            records = telemetry.read_jsonl(logger.task_log_path("demo"))
        self.assertEqual(records[0]["token_count"], 185)
        self.assertAlmostEqual(records[0]["cost_estimate"], 0.0123)

    def test_emit_stage_session_without_usage_records_nulls(self):
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            logger = telemetry.RunLogger(repo_root, run_id="r1")
            orchestrator._emit_stage_session(
                logger,
                "demo",
                "docs/plans/demo.md",
                "kimi",
                "full",
                "implemented",
                None,
                repo_root,
                "2026-07-12T00:00:00Z",
                "2026-07-12T00:01:00Z",
                0,
            )
            records = telemetry.read_jsonl(logger.task_log_path("demo"))
        self.assertIsNone(records[0]["token_count"])
        self.assertIsNone(records[0]["cost_estimate"])

    def test_emit_stage_session_populates_actual_stages_for_group(self):
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            logger = telemetry.RunLogger(repo_root, run_id="r1")
            orchestrator._emit_stage_session(
                logger,
                "demo",
                "docs/plans/demo.md",
                "kimi",
                "standard",
                "implemented",
                ["plan-approved", "implemented"],
                repo_root,
                "2026-07-12T00:00:00Z",
                "2026-07-12T00:01:00Z",
                0,
            )
            records = telemetry.read_jsonl(logger.task_log_path("demo"))
        self.assertEqual(records[0]["actual_stages"], ["plan-approved", "implemented"])

    def test_emit_stage_session_populates_actual_stages_for_single_stage(self):
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            logger = telemetry.RunLogger(repo_root, run_id="r1")
            orchestrator._emit_stage_session(
                logger,
                "demo",
                "docs/plans/demo.md",
                "kimi",
                "full",
                "implemented",
                None,
                repo_root,
                "2026-07-12T00:00:00Z",
                "2026-07-12T00:01:00Z",
                0,
            )
            records = telemetry.read_jsonl(logger.task_log_path("demo"))
        self.assertEqual(records[0]["actual_stages"], ["implemented"])

    def test_emit_stage_session_captures_plan_snapshot(self):
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            plan_file = Path(repo_root, "docs", "plans", "demo.md")
            plan_file.parent.mkdir(parents=True, exist_ok=True)
            plan_file.write_text(
                "---\n"
                "id: demo\n"
                "size: M\n"
                "pipeline: standard\n"
                "security_review: required\n"
                "---\n\n# Demo\n",
                encoding="utf-8",
            )
            logger = telemetry.RunLogger(repo_root, run_id="r1")
            orchestrator._emit_stage_session(
                logger,
                "demo",
                str(plan_file),
                "kimi",
                "full",
                "implemented",
                None,
                repo_root,
                "2026-07-12T00:00:00Z",
                "2026-07-12T00:01:00Z",
                0,
            )
            records = telemetry.read_jsonl(logger.task_log_path("demo"))
        self.assertEqual(
            records[0]["plan_snapshot"],
            {"size": "M", "pipeline": "standard", "security_review": "required"},
        )

    def test_emit_stage_session_increments_attempt_per_stage(self):
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            logger = telemetry.RunLogger(repo_root, run_id="r1")
            for _ in range(3):
                orchestrator._emit_stage_session(
                    logger,
                    "demo",
                    "docs/plans/demo.md",
                    "kimi",
                    "full",
                    "implemented",
                    None,
                    repo_root,
                    "2026-07-12T00:00:00Z",
                    "2026-07-12T00:01:00Z",
                    0,
                )
            records = telemetry.read_jsonl(logger.task_log_path("demo"))
        self.assertEqual([r["attempt"] for r in records], [1, 2, 3])

    def test_emit_stage_session_classifies_failure_for_nonzero_exit(self):
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            logger = telemetry.RunLogger(repo_root, run_id="r1")
            orchestrator._emit_stage_session(
                logger,
                "demo",
                "docs/plans/demo.md",
                "kimi",
                "full",
                "implemented",
                None,
                repo_root,
                "2026-07-12T00:00:00Z",
                "2026-07-12T00:01:00Z",
                1,
                output="test FAILED: assertion error",
                verdict_recorded=True,
            )
            records = telemetry.read_jsonl(logger.task_log_path("demo"))
        self.assertEqual(records[0]["failure_class"], "design")

    def _append_stage(self, logger, task_id, token_count, cost_estimate):
        logger.append_record(
            telemetry.stage_record(
                run_id=logger.run_id,
                task_id=task_id,
                plan_file="docs/plans/demo.md",
                stage="implemented",
                agent_cli="claude",
                isolation_level="full",
                start_time="2026-07-12T00:00:00Z",
                end_time="2026-07-12T00:01:00Z",
                exit_code=0,
                token_count=token_count,
                cost_estimate=cost_estimate,
            ),
            task_id=task_id,
        )

    def test_usage_aggregates_sum_non_null_stage_records(self):
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            logger = telemetry.RunLogger(repo_root, run_id="r1")
            self._append_stage(logger, "t1", 100, 0.5)
            self._append_stage(logger, "t2", None, None)
            self._append_stage(logger, "t3", 85, 0.0123)
            tokens, cost = orchestrator._usage_aggregates(logger)
        self.assertEqual(tokens, 185)
        self.assertAlmostEqual(cost, 0.5123)

    def test_usage_aggregates_all_null_returns_none(self):
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            logger = telemetry.RunLogger(repo_root, run_id="r1")
            self._append_stage(logger, "t1", None, None)
            self._append_stage(logger, "t2", None, None)
            tokens, cost = orchestrator._usage_aggregates(logger)
        self.assertIsNone(tokens)
        self.assertIsNone(cost)

    def test_usage_aggregates_ignore_work_history_copy(self):
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            logger = telemetry.RunLogger(repo_root, run_id="r1")
            self._append_stage(logger, "t1", 100, 0.5)
            history = Path(repo_root, "work-history.jsonl")
            history.write_text('{"type": "stage", "token_count": 9999}\n', encoding="utf-8")
            logger.copy_work_history(history)
            tokens, _cost = orchestrator._usage_aggregates(logger)
        self.assertEqual(tokens, 100)

    def test_stub_cli_flows_end_to_end_into_run_summary(self):
        """Plan validation: stub CLI usage lands in the stage record and summary."""
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            logger = telemetry.RunLogger(repo_root, run_id="r1")
            adapter = self._claude_stub_adapter(repo_root)
            exit_code, usage, session_dir, _output = orchestrator.run_stage(
                adapter,
                repo_root,
                "docs/plans/demo.md",
                repo_root,
                ["skill"],
                "plan-approved",
                "implemented",
            )
            orchestrator._emit_stage_session(
                logger,
                "demo",
                "docs/plans/demo.md",
                adapter.name,
                "full",
                "implemented",
                None,
                repo_root,
                "2026-07-12T00:00:00Z",
                "2026-07-12T00:01:00Z",
                exit_code,
                usage=usage,
            )
            tokens, cost = orchestrator._usage_aggregates(logger)
            summary = telemetry.run_summary_record(
                run_id="r1",
                start_time="2026-07-12T00:00:00Z",
                end_time="2026-07-12T00:02:00Z",
                tasks_spawned=1,
                tasks_succeeded=1,
                tasks_failed=0,
                total_tokens=tokens,
                total_cost_usd=cost,
            )
            records = telemetry.read_jsonl(logger.task_log_path("demo"))
        self.assertEqual(records[0]["token_count"], 185)
        self.assertAlmostEqual(records[0]["cost_estimate"], 0.0123)
        self.assertEqual(summary["total_tokens"], 185)
        self.assertAlmostEqual(summary["total_cost_usd"], 0.0123)


class TestWireTestRunEmission(unittest.TestCase):
    """Adapter-dispatched test_run records from session logs (tap-03/tap-04)."""

    @staticmethod
    def _tool_call(uuid, command, time_ms):
        return json.dumps(
            {
                "type": "context.append_loop_event",
                "event": {
                    "type": "tool.call",
                    "uuid": uuid,
                    "toolCallId": uuid,
                    "name": "Bash",
                    "args": {"command": command},
                },
                "time": time_ms,
            }
        )

    @staticmethod
    def _tool_result(uuid, output, time_ms, is_error=None):
        result = {"output": output}
        if is_error is not None:
            result["isError"] = is_error
        return json.dumps(
            {
                "type": "context.append_loop_event",
                "event": {
                    "type": "tool.result",
                    "parentUuid": uuid,
                    "toolCallId": uuid,
                    "result": result,
                },
                "time": time_ms,
            }
        )

    def _write_session(self, root, session_id, wires):
        session_dir = Path(root) / "sessions" / "wd_proj_abc123" / session_id
        for agent_id, lines in wires.items():
            wire = session_dir / "agents" / agent_id / "wire.jsonl"
            wire.parent.mkdir(parents=True, exist_ok=True)
            wire.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return session_dir

    def _write_claude_transcript(self, home, cwd, session_id, records):
        # Match the reader: transcripts live under the resolved cwd slug.
        resolved_cwd = str(Path(cwd).resolve())
        transcript_dir = (
            home / ".claude" / "projects" / session_log_claude.cwd_slug(resolved_cwd)
        )
        transcript_dir.mkdir(parents=True, exist_ok=True)
        transcript = transcript_dir / f"{session_id}.jsonl"
        transcript.write_text(
            "\n".join(json.dumps(r) for r in records) + "\n",
            encoding="utf-8",
        )
        return transcript

    def _emit(self, logger, repo_root, session_ref, agent_cli="kimi"):
        orchestrator._emit_stage_session(
            logger,
            "demo",
            "docs/plans/demo.md",
            agent_cli,
            "standard",
            "implemented",
            None,
            repo_root,
            "2026-07-14T00:00:00Z",
            "2026-07-14T00:30:00Z",
            0,
            usage=None,
            session_ref=session_ref,
        )

    def _resolve_kimi_session_dir(self, home, session_id):
        """Return the session dir that usage.resolve_kimi_session_dir_from_id finds."""
        from aet.usage import resolve_kimi_session_dir_from_id

        return resolve_kimi_session_dir_from_id(session_id, kimi_home=home / ".kimi-code")

    def test_emit_stage_session_emits_one_test_run_per_wire_invocation(self):
        """A fixture kimi session yields one test_run per test invocation
        with classified scope and measured duration."""
        t0 = 1784049800000  # 2026-07-14T17:23:20Z
        session_id = "session_t1"
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            logger = telemetry.RunLogger(repo_root, run_id="r1")
            with tempfile.TemporaryDirectory() as home:
                home_path = Path(home)
                self._write_session(
                    home_path / ".kimi-code",
                    session_id,
                    {
                        "main": [
                            self._tool_call("c1", "python3 -m pytest tests/ -q", t0),
                            self._tool_result("c1", "631 passed", t0 + 60_000),
                            self._tool_call("c2", "pytest tests/test_panel_serve.py", t0 + 100_000),
                            self._tool_result(
                                "c2",
                                "1 failed\nCommand failed with exit code: 1.",
                                t0 + 105_000,
                                is_error=True,
                            ),
                            self._tool_call("c3", "git status", t0 + 200_000),
                            self._tool_result("c3", "clean", t0 + 201_000),
                        ],
                        "agent_7f3a": [
                            self._tool_call("s1", "make validate", t0 + 300_000),
                            self._tool_result("s1", "ok", t0 + 340_000),
                        ],
                    },
                )
                with patch.dict(os.environ, {"HOME": home}):
                    self._emit(logger, repo_root, session_id)
            records = telemetry.read_jsonl(logger.task_log_path("demo"))
        stage_record = records[0]
        self.assertEqual(stage_record["type"], "stage")
        self.assertEqual(stage_record["session_identifier"], session_id)
        test_runs = [r for r in records if r.get("type") == "test_run"]
        self.assertEqual(len(test_runs), 3)

        self.assertEqual(test_runs[0]["test_command"], "python3 -m pytest tests/ -q")
        self.assertEqual(test_runs[0]["scope"], "full-suite")
        self.assertEqual(test_runs[0]["duration_seconds"], 60.0)
        self.assertEqual(test_runs[0]["exit_code"], 0)
        self.assertEqual(test_runs[0]["result"], "success")

        self.assertEqual(test_runs[1]["test_command"], "pytest tests/test_panel_serve.py")
        self.assertEqual(test_runs[1]["scope"], "impact")
        self.assertEqual(test_runs[1]["duration_seconds"], 5.0)
        self.assertEqual(test_runs[1]["exit_code"], 1)
        self.assertEqual(test_runs[1]["result"], "failure")

        self.assertEqual(test_runs[2]["test_command"], "make validate")
        self.assertEqual(test_runs[2]["scope"], "full-suite")
        self.assertEqual(test_runs[2]["duration_seconds"], 40.0)

        for record in test_runs:
            self.assertEqual(record["stage"], "implemented")
            self.assertEqual(record["run_id"], "r1")
            self.assertEqual(record["task_id"], "demo")
            self.assertEqual(record["plan_file"], "docs/plans/demo.md")

    def test_emit_stage_session_without_session_ref_emits_no_test_runs(self):
        """Non-kimi CLIs and unresolvable sessions emit nothing."""
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            logger = telemetry.RunLogger(repo_root, run_id="r1")
            self._emit(logger, repo_root, None, agent_cli="claude")
            records = telemetry.read_jsonl(logger.task_log_path("demo"))
        self.assertEqual([r["type"] for r in records], ["stage"])
        self.assertIsNone(records[0].get("session_identifier"))

    def test_emit_stage_session_with_unresolvable_ref_emits_no_test_runs(self):
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            logger = telemetry.RunLogger(repo_root, run_id="r1")
            self._emit(logger, repo_root, "no-such-session")
            records = telemetry.read_jsonl(logger.task_log_path("demo"))
        self.assertEqual([r["type"] for r in records], ["stage"])

    def test_unpaired_wire_call_yields_null_duration_record(self):
        t0 = 1784049800000
        session_id = "session_t2"
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            logger = telemetry.RunLogger(repo_root, run_id="r1")
            with tempfile.TemporaryDirectory() as home:
                home_path = Path(home)
                self._write_session(
                    home_path / ".kimi-code",
                    session_id,
                    {"main": [self._tool_call("c1", "pytest tests/", t0)]},
                )
                with patch.dict(os.environ, {"HOME": home}):
                    self._emit(logger, repo_root, session_id)
            records = telemetry.read_jsonl(logger.task_log_path("demo"))
        test_runs = [r for r in records if r.get("type") == "test_run"]
        self.assertEqual(len(test_runs), 1)
        self.assertIsNone(test_runs[0]["end_time"])
        self.assertIsNone(test_runs[0]["duration_seconds"])
        self.assertIsNone(test_runs[0]["exit_code"])
        self.assertEqual(test_runs[0]["result"], "unknown")

    def test_emit_test_runs_noop_on_null_session_reference(self):
        """A null reference short-circuits before dispatch, same as before."""
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            logger = telemetry.RunLogger(repo_root, run_id="r1")
            self._emit(logger, repo_root, None, agent_cli="kimi")
            records = telemetry.read_jsonl(logger.task_log_path("demo"))
        self.assertEqual([r["type"] for r in records], ["stage"])

    def test_emit_test_runs_survives_extraction_exception(self):
        """Extraction failures are defensive and never block the stage record."""
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            logger = telemetry.RunLogger(repo_root, run_id="r1")
            with patch("aet.session_log.extract_test_invocations") as mock_extract:
                mock_extract.side_effect = RuntimeError("boom")
                self._emit(logger, repo_root, "session_x", agent_cli="kimi")
            records = telemetry.read_jsonl(logger.task_log_path("demo"))
        self.assertEqual([r["type"] for r in records], ["stage"])

    def test_session_reference_resolved_per_adapter_without_name_branch(self):
        """The spawn path delegates resolution to the adapter; no adapter.name branch.

        A custom adapter whose resolver returns a non-None identifier proves the
        orchestrator passes it through. If the orchestrator branched on
        adapter.name, the custom adapter would be treated as unresolvable.
        """

        class CustomAdapter(CLIAdapter):
            def resolve_session_ref(self, output, workdir=None):
                return "custom-sid"

        with tempfile.TemporaryDirectory() as tmp:
            adapter = CustomAdapter(
                name="custom",
                bin="echo",
                prompt_flag="-p",
                workdir_flag=None,
                headless_flag=None,
            )
            exit_code, usage, session_ref = orchestrator._spawn_session(
                adapter, ["echo", "hi"], tmp, os.environ.copy()
            )
        self.assertEqual(exit_code, 0)
        self.assertIsNone(usage)
        self.assertEqual(session_ref, "custom-sid")

    def test_emit_stage_session_emits_claude_test_runs_from_transcript(self):
        """A fixture Claude transcript yields observed test_run records."""
        t0 = "2026-07-14T17:23:20Z"
        cwd = "/tmp/proj"
        session_id = "s1"
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            logger = telemetry.RunLogger(repo_root, run_id="r1")
            with tempfile.TemporaryDirectory() as home:
                self._write_claude_transcript(
                    Path(home),
                    cwd,
                    session_id,
                    [
                        {
                            "type": "system",
                            "subtype": "init",
                            "cwd": cwd,
                            "session_id": session_id,
                        },
                        {
                            "role": "assistant",
                            "timestamp": t0,
                            "message": {
                                "content": [
                                    {
                                        "type": "tool_use",
                                        "id": "tu1",
                                        "name": "Bash",
                                        "input": {"command": "pytest tests/"},
                                    }
                                ]
                            },
                        },
                        {
                            "role": "user",
                            "timestamp": "2026-07-14T17:24:20Z",
                            "message": {
                                "content": [
                                    {
                                        "type": "tool_result",
                                        "tool_use_id": "tu1",
                                        "is_error": False,
                                    }
                                ]
                            },
                        },
                    ],
                )
                with patch("pathlib.Path.home", return_value=Path(home)):
                    self._emit(logger, cwd, session_id, agent_cli="claude")
            records = telemetry.read_jsonl(logger.task_log_path("demo"))
        stage_record = records[0]
        self.assertEqual(stage_record["type"], "stage")
        self.assertEqual(stage_record["session_identifier"], session_id)
        test_runs = [r for r in records if r.get("type") == "test_run"]
        self.assertEqual(len(test_runs), 1)
        self.assertEqual(test_runs[0]["test_command"], "pytest tests/")
        self.assertEqual(test_runs[0]["duration_seconds"], 60.0)
        self.assertEqual(test_runs[0]["exit_code"], 0)

    def test_spawn_session_resolves_kimi_session_ref(self):
        """The spawn path threads the resolved session identifier for kimi sessions."""
        with tempfile.TemporaryDirectory() as tmp:
            bin_path = Path(tmp, "kimi-stub")
            bin_path.write_text(
                "#!/bin/sh\necho 'To resume this session: kimi -r session_stub1'\n",
                encoding="utf-8",
            )
            bin_path.chmod(0o755)
            adapter = CLIAdapter(
                name="kimi",
                bin=str(bin_path),
                prompt_flag="-p",
                workdir_flag=None,
                headless_flag=None,
                usage_mode="wire-file",
            )
            home = Path(tmp, "kimi-home")
            self._write_session(home / ".kimi-code", "session_stub1", {"main": []})
            env = os.environ.copy()
            with patch.dict(os.environ, {"HOME": str(home)}):
                exit_code, _usage, session_ref = orchestrator._spawn_session(
                    adapter, [str(bin_path)], tmp, env
                )
        self.assertEqual(exit_code, 0)
        self.assertEqual(session_ref, "session_stub1")

    def test_spawn_session_non_kimi_yields_none_session_ref(self):
        with tempfile.TemporaryDirectory() as tmp:
            adapter = CLIAdapter(
                name="test",
                bin="echo",
                prompt_flag="-p",
                workdir_flag=None,
                headless_flag=None,
            )
            exit_code, usage, session_ref = orchestrator._spawn_session(
                adapter, ["echo", "hi"], tmp, os.environ.copy()
            )
        self.assertEqual(exit_code, 0)
        self.assertIsNone(usage)
        self.assertIsNone(session_ref)

    def test_orchestrated_claude_stage_writes_observed_test_run(self):
        """R-6 end-to-end: an orchestrated claude stage emits an observed test_run.

        A stub claude binary writes a real transcript and JSON envelope; the
        orchestrator's run_stage + _emit_stage_session path turns that into a
        stage record carrying a session identifier and a test_run record with a
        non-null duration.
        """
        session_id = "r6-e2e-session"

        def _write_stub(home: Path, repo_root: str) -> Path:
            stub = home / "claude-stub"
            call_record = json.dumps(
                {
                    "timestamp": "2026-07-28T17:00:00Z",
                    "sessionId": session_id,
                    "cwd": "__CWD__",
                    "role": "assistant",
                    "message": {
                        "content": [
                            {
                                "type": "tool_use",
                                "name": "Bash",
                                "id": "tu1",
                                "input": {"command": "pytest tests/"},
                            }
                        ]
                    },
                }
            )
            result_record = json.dumps(
                {
                    "timestamp": "2026-07-28T17:01:00Z",
                    "sessionId": session_id,
                    "cwd": "__CWD__",
                    "role": "user",
                    "message": {
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": "tu1",
                                "is_error": False,
                            }
                        ]
                    },
                }
            )
            envelope = json.dumps(
                {
                    "type": "result",
                    "session_id": session_id,
                    "usage": {"input_tokens": 1, "output_tokens": 1},
                }
            )
            lines = [
                "#!/usr/bin/env python3",
                "from pathlib import Path",
                "import json, os, subprocess, sys",
                "cwd = os.getcwd()",
                'home = os.path.expanduser("~")',
                'slug = cwd.rstrip("/").replace("/", "-")',
                'transcript_dir = os.path.join(home, ".claude", "projects", slug)',
                "os.makedirs(transcript_dir, exist_ok=True)",
                f'transcript = os.path.join(transcript_dir, "{session_id}.jsonl")',
                'with open(transcript, "w") as f:',
                f'    f.write({call_record!r}.replace("__CWD__", cwd) + "\\n")',
                f'    f.write({result_record!r}.replace("__CWD__", cwd) + "\\n")',
                f'print({envelope!r})',
                'Path("r6.txt").write_text("done", encoding="utf-8")',
                'subprocess.run(["git", "add", "."], check=True)',
                'subprocess.run(["git", "commit", "-m", "r6 e2e"], check=True)',
            ]
            stub.write_text("\n".join(lines) + "\n", encoding="utf-8")
            stub.chmod(0o755)
            return stub

        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            repo_root = str(home / "repo")
            _init_git_repo(repo_root)
            # Ensure a base commit exists so the stage can create a new one.
            Path(repo_root, "base.txt").write_text("base", encoding="utf-8")
            subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
            subprocess.run(["git", "-C", repo_root, "commit", "-m", "base"], check=True)

            stub = _write_stub(home, repo_root)
            adapter = CLIAdapter(
                name="claude",
                bin=str(stub),
                prompt_flag="-p",
                workdir_flag=None,
                headless_flag="--dangerously-skip-permissions",
                usage_mode="json-envelope",
            )
            plan_file = "docs/plans/r6-test.md"

            logger = telemetry.RunLogger(repo_root, run_id="r6-run")
            with patch.dict(os.environ, {"HOME": str(home)}):
                exit_code, usage, session_ref, output = orchestrator.run_stage(
                    adapter,
                    repo_root,
                    plan_file,
                    repo_root,
                    ["aet-qa"],
                    "run",
                    "done",
                    task_id="r6-task",
                    run_id="r6-run",
                )
                self.assertEqual(exit_code, 0)
                self.assertEqual(session_ref, session_id)
                self.assertIsNotNone(usage)

                orchestrator._emit_stage_session(
                    logger,
                    "r6-task",
                    plan_file,
                    "claude",
                    "full",
                    "run",
                    None,
                    repo_root,
                    "2026-07-28T17:00:00Z",
                    "2026-07-28T17:01:00Z",
                    exit_code,
                    usage=usage,
                    session_ref=session_ref,
                )

            records = telemetry.read_jsonl(logger.task_log_path("r6-task"))
        stage_records = [r for r in records if r.get("type") == "stage"]
        test_runs = [r for r in records if r.get("type") == "test_run"]
        self.assertEqual(len(stage_records), 1)
        self.assertEqual(stage_records[0]["session_identifier"], session_id)
        self.assertEqual(len(test_runs), 1)
        self.assertEqual(test_runs[0]["test_command"], "pytest tests/")
        self.assertEqual(test_runs[0]["duration_seconds"], 60.0)
        self.assertEqual(test_runs[0]["exit_code"], 0)


class TestQaFreshnessInjection(unittest.TestCase):
    """The orchestrator injects a QA-freshness clause into stage prompts."""

    def test_freshness_clause_mapping(self):
        skip = orchestrator._freshness_clause(evidence.SKIP)
        lint = orchestrator._freshness_clause(evidence.LINT_ONLY)
        self.assertIn("do NOT re-run", skip)
        self.assertIn("lint/format", lint)
        self.assertEqual(orchestrator._freshness_clause(evidence.RUN), "")
        self.assertEqual(orchestrator._freshness_clause(""), "")

    def test_decision_empty_without_task_id(self):
        self.assertEqual(orchestrator._qa_freshness_decision(None, "/x", "/y"), "")

    def test_decision_never_raises_on_bad_paths(self):
        # A non-existent worktree yields a string (RUN), never an exception.
        self.assertIsInstance(
            orchestrator._qa_freshness_decision("demo", "/nope", "/nope"), str
        )

    def _write_qa_pass(self, repo: str, reports: str) -> None:
        # No tree_hash in the record → write_verdict stamps the real repo hash.
        evidence.write_verdict(
            task_id="demo",
            kind="qa",
            record={
                "task_id": "demo",
                "stage": "qa-complete",
                "skill": "aet-qa",
                "verdict": "pass",
                "summary": "green",
                "generated_at": "2026-07-13T00:00:00Z",
                "test_command": "make validate",
                "tests_total": 1,
                "tests_passed": 1,
                "tests_failed": 0,
            },
            project_slug="demo/project",
            reports_root=reports,
            worktree_dir=repo,
        )

    def _capture_run_stage(self, repo: str) -> dict:
        captured: dict = {}

        # Patch the spawn (not subprocess.Popen) so the real git calls the
        # freshness check makes still run against the temp repo.
        def fake_spawn(adapter, cmd, worktree_dir, env, **kwargs):
            captured["cmd"] = cmd
            captured["env"] = env
            return 0, None, None, ""

        with patch.object(orchestrator, "_spawn_session_with_tail", side_effect=fake_spawn):
            orchestrator.run_stage(
                _FAKE_ADAPTER,
                repo,
                str(Path(repo) / "docs" / "plans" / "demo.md"),
                repo,
                ["aet-review"],
                "qa-complete",
                "reviewed",
                task_id="demo",
                run_id="run-test",
            )
        return captured

    def test_fresh_qa_verdict_injects_skip_clause(self):
        with tempfile.TemporaryDirectory() as repo, tempfile.TemporaryDirectory() as reports:
            _init_git_repo(repo)
            env = {"AET_REPORTS_DIR": reports, "AET_PROJECT_ID": "demo/project"}
            with patch.dict(os.environ, env, clear=False):
                for k in ("AET_EVIDENCE_PATH", "AET_EVIDENCE_PATH_QA"):
                    os.environ.pop(k, None)
                self._write_qa_pass(repo, reports)
                captured = self._capture_run_stage(repo)
            self.assertEqual(captured["env"].get("AET_QA_FRESHNESS"), evidence.SKIP)
            self.assertIn("do NOT re-run", " ".join(captured["cmd"]))

    def test_changed_tree_omits_clause(self):
        with tempfile.TemporaryDirectory() as repo, tempfile.TemporaryDirectory() as reports:
            _init_git_repo(repo)
            env = {"AET_REPORTS_DIR": reports, "AET_PROJECT_ID": "demo/project"}
            with patch.dict(os.environ, env, clear=False):
                for k in ("AET_EVIDENCE_PATH", "AET_EVIDENCE_PATH_QA"):
                    os.environ.pop(k, None)
                self._write_qa_pass(repo, reports)
                Path(repo, "src.py").write_text("x = 1\n", encoding="utf-8")
                captured = self._capture_run_stage(repo)
            self.assertNotEqual(captured["env"].get("AET_QA_FRESHNESS"), evidence.SKIP)
            self.assertNotIn("do NOT re-run", " ".join(captured["cmd"]))

    def _capture_run_stage_group(self, repo: str) -> dict:
        captured: dict = {}

        def fake_spawn(adapter, cmd, worktree_dir, env, **kwargs):
            captured["cmd"] = cmd
            captured["env"] = env
            return 0, None, None, ""

        stages = [
            WorkflowStage(
                name="reviewed", skills=["aet-review"], evidence="review", gate_key=None
            ),
        ]
        workflow = Workflow(
            version=1,
            name="test",
            done_state="done",
            stages=stages,
            stage_map={s.name: s for s in stages},
            execution_policy=ExecutionPolicy(session_groups=[["reviewed"]]),
            routing=Routing(default={"harness": "test", "model": None}, by_stage={}),
        )
        with patch.object(orchestrator, "_spawn_session_with_tail", side_effect=fake_spawn):
            orchestrator.run_stage_group(
                _FAKE_ADAPTER,
                repo,
                str(Path(repo) / "docs" / "plans" / "demo.md"),
                repo,
                stages,
                task_id="demo",
                run_id="run-test",
                workflow=workflow,
            )
        return captured

    def test_fresh_qa_verdict_injects_skip_clause_in_group_prompt(self):
        with tempfile.TemporaryDirectory() as repo, tempfile.TemporaryDirectory() as reports:
            _init_git_repo(repo)
            env = {"AET_REPORTS_DIR": reports, "AET_PROJECT_ID": "demo/project"}
            with patch.dict(os.environ, env, clear=False):
                for k in ("AET_EVIDENCE_PATH", "AET_EVIDENCE_PATH_QA"):
                    os.environ.pop(k, None)
                self._write_qa_pass(repo, reports)
                captured = self._capture_run_stage_group(repo)
            self.assertEqual(captured["env"].get("AET_QA_FRESHNESS"), evidence.SKIP)
            self.assertIn("do NOT re-run", " ".join(captured["cmd"]))


class TestHandoffInjection(unittest.TestCase):
    """The orchestrator injects a run-scoped handoff note into stage prompts."""

    def _write_handoff_note(self, repo: str, run_id: str = "run-test") -> None:
        from aet import handoff

        handoff.append_entry(
            repo,
            run_id,
            stage="plan-approved",
            decisions=["use JSON"],
            pre_existing_failures=["flaky integration"],
            validation_commands=["make test"],
            evidence_path="/path/to/evidence.json",
            recorded_at="2026-08-10T09:30:00+00:00",
        )

    def _capture_run_stage(self, repo: str, run_id: str = "run-test") -> dict:
        captured: dict = {}

        def fake_spawn(adapter, cmd, worktree_dir, env, **kwargs):
            captured["cmd"] = cmd
            captured["env"] = env
            return 0, None, None, ""

        with patch.object(orchestrator, "_spawn_session_with_tail", side_effect=fake_spawn):
            orchestrator.run_stage(
                _FAKE_ADAPTER,
                repo,
                str(Path(repo) / "docs" / "plans" / "demo.md"),
                repo,
                ["aet-implement"],
                "plan-approved",
                "implemented",
                task_id="demo",
                run_id=run_id,
            )
        return captured

    def test_handoff_note_injects_block_for_next_stage(self):
        with tempfile.TemporaryDirectory() as repo:
            _init_git_repo(repo)
            self._write_handoff_note(repo)
            captured = self._capture_run_stage(repo)
            prompt = " ".join(captured["cmd"])
            self.assertIn("Run handoff note", prompt)
            self.assertIn("[stage: plan-approved]", prompt)
            self.assertIn("decisions: use JSON", prompt)
            self.assertIn("pre-existing failures: flaky integration", prompt)
            self.assertIn("validation commands: make test", prompt)
            self.assertIn("evidence path: /path/to/evidence.json", prompt)

    def test_missing_handoff_note_keeps_prompt_identical(self):
        with tempfile.TemporaryDirectory() as repo:
            _init_git_repo(repo)
            captured = self._capture_run_stage(repo)
            prompt_with_empty_clause = orchestrator.build_prompt(
                ["aet-implement"],
                str(Path(repo) / "docs" / "plans" / "demo.md"),
                "plan-approved",
                "implemented",
            )
            self.assertEqual(captured["cmd"][-1], prompt_with_empty_clause)

    def test_handoff_clause_never_raises_on_bad_paths(self):
        # A missing repo yields an empty clause, never an exception.
        self.assertEqual(orchestrator._handoff_clause("/nope", "run-test"), "")

    def test_handoff_note_injects_block_in_group_prompt(self):
        with tempfile.TemporaryDirectory() as repo:
            _init_git_repo(repo)
            self._write_handoff_note(repo)
            captured: dict = {}

            def fake_spawn(adapter, cmd, worktree_dir, env, **kwargs):
                captured["cmd"] = cmd
                captured["env"] = env
                return 0, None, None, ""

            stages = [
                WorkflowStage(
                    name="implemented",
                    skills=["aet-implement"],
                    evidence=None,
                    gate_key=None,
                ),
            ]
            workflow = Workflow(
                version=1,
                name="test",
                done_state="done",
                stages=stages,
                stage_map={s.name: s for s in stages},
                execution_policy=ExecutionPolicy(session_groups=[["implemented"]]),
                routing=Routing(default={"harness": "test", "model": None}, by_stage={}),
            )
            with patch.object(orchestrator, "_spawn_session_with_tail", side_effect=fake_spawn):
                orchestrator.run_stage_group(
                    _FAKE_ADAPTER,
                    repo,
                    str(Path(repo) / "docs" / "plans" / "demo.md"),
                    repo,
                    stages,
                    task_id="demo",
                    run_id="run-test",
                    workflow=workflow,
                )
            prompt = " ".join(captured["cmd"])
            self.assertIn("Run handoff note", prompt)
            self.assertIn("decisions: use JSON", prompt)

    def test_missing_handoff_note_keeps_group_prompt_identical(self):
        with tempfile.TemporaryDirectory() as repo:
            _init_git_repo(repo)
            captured: dict = {}

            def fake_spawn(adapter, cmd, worktree_dir, env, **kwargs):
                captured["cmd"] = cmd
                return 0, None, None, ""

            stages = [
                WorkflowStage(
                    name="implemented",
                    skills=["aet-implement"],
                    evidence=None,
                    gate_key=None,
                ),
            ]
            workflow = Workflow(
                version=1,
                name="test",
                done_state="done",
                stages=stages,
                stage_map={s.name: s for s in stages},
                execution_policy=ExecutionPolicy(session_groups=[["implemented"]]),
                routing=Routing(default={"harness": "test", "model": None}, by_stage={}),
            )
            with patch.object(orchestrator, "_spawn_session_with_tail", side_effect=fake_spawn):
                orchestrator.run_stage_group(
                    _FAKE_ADAPTER,
                    repo,
                    str(Path(repo) / "docs" / "plans" / "demo.md"),
                    repo,
                    stages,
                    task_id="demo",
                    run_id="run-test",
                    workflow=workflow,
                )
            prompt_with_empty_clause = orchestrator.build_stage_group_prompt(
                str(Path(repo) / "docs" / "plans" / "demo.md"),
                stages,
                workflow,
            )
            self.assertEqual(captured["cmd"][-1], prompt_with_empty_clause)


if __name__ == "__main__":
    unittest.main()
