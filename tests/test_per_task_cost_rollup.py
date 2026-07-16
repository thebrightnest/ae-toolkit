"""Tests for per-task token/cost rollup to the ledger record (ADR-031)."""

from __future__ import annotations

import ast
import importlib.machinery
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Ensure the aet-work lib is on the path before importing telemetry.
sys.path.insert(0, str(Path(__file__).parent.parent / "aet-work" / "lib"))

import telemetry

# Load the orchestrator script (no .py extension) as a module.
_ORCHESTRATOR_BIN = Path(__file__).parent.parent / "aet-work" / "bin" / "orchestrator"
sys.path.insert(0, str(_ORCHESTRATOR_BIN.parent))
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


def _append_stage(logger, task_id, token_count, cost_estimate):
    """Append a stage record for ``task_id`` to the run archive."""
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


class TestPerTaskUsageAggregates(unittest.TestCase):
    """Unit tests for the per-task token/cost aggregation helper."""

    def test_rollup_sums_stage_records_for_task(self):
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            logger = telemetry.RunLogger(repo_root, run_id="r1")
            _append_stage(logger, "t1", 100, 0.5)
            _append_stage(logger, "t2", 50, 0.1)
            _append_stage(logger, "t1", 85, 0.0123)
            tokens, cost = orchestrator._task_usage_aggregates(logger, "t1")
        self.assertEqual(tokens, 185)
        self.assertAlmostEqual(cost, 0.5123)

    def test_rollup_preserves_null_for_all_null_task(self):
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            logger = telemetry.RunLogger(repo_root, run_id="r1")
            _append_stage(logger, "t1", None, None)
            _append_stage(logger, "t1", None, None)
            tokens, cost = orchestrator._task_usage_aggregates(logger, "t1")
        self.assertIsNone(tokens)
        self.assertIsNone(cost)

    def test_rollup_ignores_other_tasks_and_non_stage_records(self):
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            logger = telemetry.RunLogger(repo_root, run_id="r1")
            _append_stage(logger, "t1", 100, 0.5)
            _append_stage(logger, "t2", 999, 9.99)
            logger.append_record(
                telemetry.run_summary_record(
                    run_id="r1",
                    start_time="2026-07-12T00:00:00Z",
                    end_time="2026-07-12T00:01:00Z",
                    tasks_spawned=1,
                    tasks_succeeded=1,
                    tasks_failed=0,
                    total_tokens=9999,
                    total_cost_usd=99.99,
                ),
                task_id="t1",
            )
            tokens, cost = orchestrator._task_usage_aggregates(logger, "t1")
        self.assertEqual(tokens, 100)
        self.assertAlmostEqual(cost, 0.5)


class TestPerTaskCostLedgerWrite(unittest.TestCase):
    """Integration tests for writing rolled-up cost to the task ledger record."""

    def _make_task(self, task_id, plan_file, worktree):
        return {
            "id": task_id,
            "state": "in_progress",
            "plan_file": plan_file,
            "branch": task_id,
            "worktree": worktree,
            "blocked_by": [],
            "blocks": [],
            "pending_blockers": 0,
            "history": [],
        }

    def test_cost_written_to_ledger_record_at_close(self):
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            worktree = Path(repo_root) / ".worktrees" / "nsr-06"
            worktree.mkdir(parents=True)

            queue_file = str(Path(repo_root) / ".agents" / "work-queue.json")
            backend = orchestrator._make_backend(queue_file)
            task = self._make_task("nsr-06", "docs/plans/nsr-06.md", str(worktree))
            backend.save([task])

            logger = telemetry.RunLogger(repo_root, run_id="r1")
            _append_stage(logger, "nsr-06", 100, 0.5)
            _append_stage(logger, "nsr-06", 85, 0.0123)

            with patch.object(
                orchestrator, "verify_branch_has_commits", return_value=(True, "")
            ), patch.object(orchestrator, "_maybe_auto_merge", return_value=False):
                orchestrator._finalize_task(
                    backend, queue_file, "nsr-06", 0, repo_root=repo_root, logger=logger
                )

            queue = backend.load(verify=False)["queue"]
            task = next((t for t in queue if t.get("id") == "nsr-06"), None)
            self.assertIsNotNone(task)
            self.assertEqual(task["cost"]["tokens"], 185)
            self.assertAlmostEqual(task["cost"]["usd"], 0.5123)
            self.assertEqual(task["state"], "awaiting_merge")

    def test_cost_null_preserved_when_task_has_no_usage(self):
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            worktree = Path(repo_root) / ".worktrees" / "nsr-06"
            worktree.mkdir(parents=True)

            queue_file = str(Path(repo_root) / ".agents" / "work-queue.json")
            backend = orchestrator._make_backend(queue_file)
            task = self._make_task("nsr-06", "docs/plans/nsr-06.md", str(worktree))
            backend.save([task])

            logger = telemetry.RunLogger(repo_root, run_id="r1")
            _append_stage(logger, "nsr-06", None, None)

            with patch.object(
                orchestrator, "verify_branch_has_commits", return_value=(True, "")
            ), patch.object(orchestrator, "_maybe_auto_merge", return_value=False):
                orchestrator._finalize_task(
                    backend, queue_file, "nsr-06", 0, repo_root=repo_root, logger=logger
                )

            queue = backend.load(verify=False)["queue"]
            task = next((t for t in queue if t.get("id") == "nsr-06"), None)
            self.assertIsNotNone(task)
            self.assertIsNone(task.get("cost"))


class TestCostAnalyticsOnlyGuard(unittest.TestCase):
    """Static guarantee that cost is never read by a runtime control path."""

    def test_no_control_path_reads_cost(self):
        source = _ORCHESTRATOR_BIN.read_text(encoding="utf-8")
        tree = ast.parse(source)

        reads = []
        for node in ast.walk(tree):
            # task["cost"] in a non-assignment (Store) context
            if isinstance(node, ast.Subscript):
                if (
                    isinstance(node.value, ast.Name)
                    and node.value.id == "task"
                    and isinstance(node.slice, ast.Constant)
                    and node.slice.value == "cost"
                    and not isinstance(node.ctx, ast.Store)
                ):
                    reads.append(getattr(node, "lineno", 0))
            # task.get("cost", ...)
            if isinstance(node, ast.Call):
                func = node.func
                if (
                    isinstance(func, ast.Attribute)
                    and func.attr == "get"
                    and isinstance(func.value, ast.Name)
                    and func.value.id == "task"
                    and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and node.args[0].value == "cost"
                ):
                    reads.append(getattr(node, "lineno", 0))

        self.assertEqual(
            reads,
            [],
            f"orchestrator reads task['cost'] on line(s) {reads}; "
            "cost must be write-only from the runtime's perspective",
        )
