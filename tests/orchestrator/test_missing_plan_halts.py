"""Tests for the orchestrator halting when the resolved base lacks the plan."""

from __future__ import annotations

import argparse
import importlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pytest

from aet import telemetry
from aet.cli_adapter import CLIAdapter

_ORCHESTRATOR_BIN = Path(__file__).parents[2] / "src" / "aet" / "cli" / "orchestrator.py"
_orchestrator_loader = importlib.machinery.SourceFileLoader("orchestrator", str(_ORCHESTRATOR_BIN))
_spec = importlib.util.spec_from_loader("orchestrator", _orchestrator_loader)
orchestrator = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(orchestrator)

pytestmark = pytest.mark.xdist_group("git-repo")

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


def _make_args(repo_root: str, plan_file: str, base: str | None = None) -> argparse.Namespace:
    return argparse.Namespace(
        queue_file=None,
        plan_file=plan_file,
        repo_root=repo_root,
        cli_bin="echo",
        isolation="standard",
        max_jobs=4,
        on_failure="continue",
        base=base,
    )


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


class TestMissingPlanHalt(unittest.TestCase):
    def test_process_task_raises_missing_plan_error(self):
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            plan_file = os.path.join(repo_root, "docs", "plans", "missing.md")
            task = {"id": "missing", "title": "missing", "plan_file": plan_file}

            with self.assertRaises(orchestrator.MissingPlanError) as ctx:
                orchestrator.process_task(
                    task, repo_root, _FAKE_ADAPTER, "standard", base_branch="origin/main"
                )

            message = str(ctx.exception)
            self.assertIn("origin/main", message)
            self.assertIn("docs/plans/missing.md", message)
            self.assertIn("--base", message)
            self.assertIn("AET_WORK_BASE_BRANCH", message)

    def test_run_single_returns_code_two_for_missing_plan(self):
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            plan_file = os.path.join(repo_root, "docs", "plans", "missing.md")
            args = _make_args(repo_root, plan_file)
            with patch.dict(os.environ, {"AET_EXECUTION_MODE": "unattended"}, clear=True):
                exit_code = orchestrator.run_single(args, _FAKE_ADAPTER)
            self.assertEqual(exit_code, 2)


class TestFinalizeTaskMissingPlan(unittest.TestCase):
    def test_finalize_task_does_not_requeue_on_missing_plan_exit(self):
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            queue_file = _write_queue(
                repo_root,
                [
                    {
                        "id": "demo",
                        "title": "Demo",
                        "plan_file": "docs/plans/missing.md",
                        "blocked_by": [],
                        "state": "in_progress",
                    }
                ],
            )
            backend = orchestrator._make_backend(queue_file)
            logger = telemetry.RunLogger(repo_root)

            deltas = orchestrator._finalize_task(
                backend,
                queue_file,
                "demo",
                2,
                repo_root=repo_root,
                logger=logger,
                on_failure="triage",
                adapter=None,
                worktree_dir=None,
            )

            self.assertEqual(deltas["successes"], 0)
            self.assertEqual(deltas["failures"], 1)
            self.assertTrue(deltas["stop_spawn"])
            queue = backend.load()["queue"]
            task = next(t for t in queue if t["id"] == "demo")
            self.assertEqual(task["state"], "failed")


if __name__ == "__main__":
    unittest.main()
