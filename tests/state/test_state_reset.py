"""Tests for the `aet state reset` single-task repair command."""

import importlib.machinery
import importlib.util
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from aet.backends.git_refs_backend import GitRefsBackend
from aet.breaker import BreakerStore
from aet.queue import LEASE_HELD_EXIT_CODE, acquire_lease
from tests.state._helpers import init_git_repo, load_git_queue, seed_git_queue

_AET_STATE_PY = Path(__file__).parents[2] / "src" / "aet" / "cli" / "aet_state.py"

_state_spec = importlib.util.spec_from_loader(
    "aet_state", importlib.machinery.SourceFileLoader("aet_state", str(_AET_STATE_PY))
)
aet_state = importlib.util.module_from_spec(_state_spec)
_state_spec.loader.exec_module(aet_state)

class MockResult:
    def __init__(self, returncode, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _git_mock(responses):
    """Return a mock subprocess.run that answers git commands.

    Unknown git commands are delegated to the real subprocess so the
    git-refs backend can operate on the temporary repository.
    """
    real_run = __import__("subprocess").run

    def mock_run(cmd, **kwargs):
        args = tuple(cmd[1:])
        if args in responses:
            rc, out, err = responses[args]
            return MockResult(rc, out, err)
        return real_run(cmd, **kwargs)

    return mock_run


def _make_queue(tmpdir, task):
    repo_root = Path(tmpdir)
    init_git_repo(repo_root)
    queue_path, history_path = seed_git_queue(repo_root, [task])
    return queue_path


def _make_plan(tmpdir, task_id, blocked_by=None):
    """Write a minimal sprint plan with a covering PRD for round-trip tests."""
    plans_dir = Path(tmpdir) / "docs" / "plans"
    prds_dir = Path(tmpdir) / "docs" / "prds"
    plans_dir.mkdir(parents=True, exist_ok=True)
    prds_dir.mkdir(parents=True, exist_ok=True)

    prd_path = prds_dir / f"{task_id}-prd.md"
    prd_path.write_text(
        "# PRD\n\n## Requirements\n\n- R-11\n",
        encoding="utf-8",
    )

    plan_path = plans_dir / f"{task_id}.md"
    blocked_by = blocked_by or []
    plan_path.write_text(
        "---\n"
        f"id: {task_id}\n"
        "size: S\n"
        "status: queued\n"
        f"blocked_by: [{', '.join(repr(b) for b in blocked_by)}]\n"
        "---\n\n"
        f"# Plan {task_id}\n\n"
        f"PRD: docs/prds/{task_id}-prd.md\n\n"
        "## Task List\n"
        f"- Reset un-starts the task (traces: R-11)\n\n"
        "## Validation Steps\n"
        "- tests/state/test_state_reset.py covers the reset command\n",
        encoding="utf-8",
    )
    return str(plan_path)


class TestStateReset(unittest.TestCase):
    """`aet state reset` recomputes a single task and clears stale runtime fields."""

    def test_reset_unstarts_in_progress_task_to_ready(self):
        """reset moves an in_progress task with a deleted branch back to ready."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = _make_plan(tmpdir, "t1")
            queue_path = _make_queue(
                tmpdir,
                {
                    "id": "t1",
                    "state": "in_progress",
                    "plan_file": plan_path,
                    "branch": "feat-t1",
                    "worktree": "/nonexistent/worktree",
                },
            )

            responses = {
                ("show-ref", "--verify", "--quiet", "refs/heads/feat-t1"): (1, "", ""),
            }

            args = aet_state.argparse.Namespace(
                command="reset",
                task_id="t1",
                queue=str(queue_path),
                apply=True,
                force=False,
            )
            with patch.object(aet_state.subprocess, "run", side_effect=_git_mock(responses)):
                rc = aet_state.cmd_reset(args)

            self.assertEqual(rc, 0)
            task = load_git_queue(queue_path)[0]
            self.assertEqual(task["state"], "ready")
            self.assertNotIn("branch", task)
            self.assertNotIn("worktree", task)
            self.assertTrue(any(h["by"] == "reset" for h in task.get("history", [])))

    def test_reset_unstarts_awaiting_merge_task_to_blocked(self):
        """reset moves an awaiting_merge task with live blockers back to blocked."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = _make_plan(tmpdir, "t1", blocked_by=["t2"])
            plan_path2 = _make_plan(tmpdir, "t2")
            queue_path = _make_queue(
                tmpdir,
                {
                    "id": "t1",
                    "state": "awaiting_merge",
                    "plan_file": plan_path,
                    "branch": "feat-t1",
                    "blocked_by": ["t2"],
                    "pending_blockers": 1,
                },
            )
            backend = GitRefsBackend(
                queue_file=str(queue_path),
                history_file=str(queue_path.with_name("work-history.jsonl")),
            )
            queue = backend.load()["queue"]
            queue.append(
                {
                    "id": "t2",
                    "state": "planned",
                    "plan_file": plan_path2,
                    "branch": None,
                }
            )
            backend.save(queue)

            responses = {
                ("show-ref", "--verify", "--quiet", "refs/heads/feat-t1"): (1, "", ""),
                ("show-ref", "--verify", "--quiet", "refs/heads/None"): (1, "", ""),
            }

            args = aet_state.argparse.Namespace(
                command="reset",
                task_id="t1",
                queue=str(queue_path),
                apply=True,
                force=False,
            )
            with patch.object(aet_state.subprocess, "run", side_effect=_git_mock(responses)):
                rc = aet_state.cmd_reset(args)

            self.assertEqual(rc, 0)
            by_id = {t["id"]: t for t in load_git_queue(queue_path)}
            self.assertEqual(by_id["t1"]["state"], "blocked")
            self.assertNotIn("branch", by_id["t1"])

    def test_reset_dry_run_reports_without_mutating(self):
        """reset --dry-run reports the proposed repair without changing the queue."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = _make_plan(tmpdir, "t1")
            queue_path = _make_queue(
                tmpdir,
                {
                    "id": "t1",
                    "state": "in_progress",
                    "plan_file": plan_path,
                    "branch": "feat-t1",
                },
            )

            responses = {
                ("show-ref", "--verify", "--quiet", "refs/heads/feat-t1"): (1, "", ""),
            }

            args = aet_state.argparse.Namespace(
                command="reset",
                task_id="t1",
                queue=str(queue_path),
                dry_run=True,
                force=False,
            )
            stdout_capture = io.StringIO()
            with patch.object(aet_state.subprocess, "run", side_effect=_git_mock(responses)):
                with patch.object(aet_state.sys, "stdout", stdout_capture):
                    rc = aet_state.cmd_reset(args)

            self.assertEqual(rc, 0)
            output = stdout_capture.getvalue()
            self.assertIn("t1: in_progress -> ready", output)

            task = load_git_queue(queue_path)[0]
            self.assertEqual(task["state"], "in_progress")
            self.assertEqual(task["branch"], "feat-t1")

    def test_reset_live_by_default(self):
        """Reset mutates queue state live without requiring --apply."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            init_git_repo(repo_root)
            plan_path = _make_plan(tmpdir, "t1")
            queue_path, _ = seed_git_queue(
                repo_root,
                [
                    {
                        "id": "t1",
                        "state": "in_progress",
                        "plan_file": plan_path,
                    }
                ],
            )

            args = aet_state.argparse.Namespace(
                command="reset",
                task_id="t1",
                queue=str(queue_path),
                force=False,
            )
            rc = aet_state.cmd_reset(args)
            self.assertEqual(rc, 0)
            task = load_git_queue(queue_path)[0]
            self.assertEqual(task["state"], "ready")

    def test_reset_dry_run_flag(self):
        """reset --dry-run reports the proposed repair without mutating queue or git state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            init_git_repo(repo_root)
            plan_path = _make_plan(tmpdir, "t1")
            queue_path, _ = seed_git_queue(
                repo_root,
                [
                    {
                        "id": "t1",
                        "state": "in_progress",
                        "plan_file": plan_path,
                        "branch": "feat-t1",
                    }
                ],
            )

            args = aet_state.argparse.Namespace(
                command="reset",
                task_id="t1",
                queue=str(queue_path),
                dry_run=True,
                force=False,
            )
            stdout_capture = io.StringIO()
            with patch.object(aet_state.sys, "stdout", stdout_capture):
                rc = aet_state.cmd_reset(args)

            self.assertEqual(rc, 0)
            output = stdout_capture.getvalue()
            self.assertIn("t1: in_progress -> ready", output)
            self.assertIn("[dry-run]", output)

            task = load_git_queue(queue_path)[0]
            self.assertEqual(task["state"], "in_progress")
            self.assertEqual(task["branch"], "feat-t1")

    def test_soft_reset_preserves_worktree_and_resets_ready(self):
        """Soft reset preserves existing worktree directory and branch while setting state to ready."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            init_git_repo(repo_root)
            (repo_root / "README.md").write_text("initial")
            import subprocess
            subprocess.run(["git", "-C", str(repo_root), "add", "."], check=True)
            subprocess.run(["git", "-C", str(repo_root), "commit", "-m", "init"], check=True)
            subprocess.run(["git", "-C", str(repo_root), "branch", "feat-t1"], check=True)

            wt_dir = repo_root / ".worktrees" / "t1"
            wt_dir.mkdir(parents=True)
            (wt_dir / "work.txt").write_text("uncommitted work")

            plan_path = _make_plan(tmpdir, "t1")
            queue_path, _ = seed_git_queue(
                repo_root,
                [
                    {
                        "id": "t1",
                        "state": "in_progress",
                        "plan_file": plan_path,
                        "branch": "feat-t1",
                        "worktree": str(wt_dir),
                        "failure_signatures": ["sig1"],
                    }
                ],
            )

            args = aet_state.argparse.Namespace(
                command="reset",
                task_id="t1",
                queue=str(queue_path),
                hard=False,
                force=False,
            )
            rc = aet_state.cmd_reset(args)
            self.assertEqual(rc, 0)

            task = load_git_queue(queue_path)[0]
            self.assertEqual(task["state"], "ready")
            self.assertEqual(task["branch"], "feat-t1")
            self.assertEqual(task["worktree"], str(wt_dir))
            self.assertNotIn("failure_signatures", task)
            self.assertTrue(wt_dir.is_dir())
            self.assertEqual((wt_dir / "work.txt").read_text(), "uncommitted work")
            rc_br = subprocess.run(
                ["git", "-C", str(repo_root), "show-ref", "--verify", "--quiet", "refs/heads/feat-t1"]
            ).returncode
            self.assertEqual(rc_br, 0)

    def test_hard_reset_cleans_worktree_and_branch(self):
        """Hard reset removes worktree directory, deletes branch, and clears runtime fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            init_git_repo(repo_root)
            (repo_root / "README.md").write_text("initial")
            import subprocess
            subprocess.run(["git", "-C", str(repo_root), "add", "."], check=True)
            subprocess.run(["git", "-C", str(repo_root), "commit", "-m", "init"], check=True)
            subprocess.run(["git", "-C", str(repo_root), "branch", "feat-t1"], check=True)

            wt_dir = repo_root / ".worktrees" / "t1"
            wt_dir.mkdir(parents=True)
            (wt_dir / "work.txt").write_text("work to delete")

            plan_path = _make_plan(tmpdir, "t1")
            queue_path, _ = seed_git_queue(
                repo_root,
                [
                    {
                        "id": "t1",
                        "state": "in_progress",
                        "plan_file": plan_path,
                        "branch": "feat-t1",
                        "worktree": str(wt_dir),
                        "run_id": "run-123",
                        "stage": "implement",
                        "failure_signatures": ["sig1"],
                    }
                ],
            )

            args = aet_state.argparse.Namespace(
                command="reset",
                task_id="t1",
                queue=str(queue_path),
                hard=True,
                force=False,
            )
            rc = aet_state.cmd_reset(args)
            self.assertEqual(rc, 0)

            task = load_git_queue(queue_path)[0]
            self.assertEqual(task["state"], "ready")
            self.assertNotIn("branch", task)
            self.assertNotIn("worktree", task)
            self.assertNotIn("run_id", task)
            self.assertNotIn("stage", task)
            self.assertNotIn("failure_signatures", task)
            self.assertFalse(wt_dir.exists())
            rc_br = subprocess.run(
                ["git", "-C", str(repo_root), "show-ref", "--verify", "--quiet", "refs/heads/feat-t1"]
            ).returncode
            self.assertNotEqual(rc_br, 0)

    def test_reset_clears_failure_signatures_and_breaker(self):
        """Reset clears task failure signatures and prunes task from BreakerStore."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            init_git_repo(repo_root)
            (repo_root / "README.md").write_text("initial")
            import subprocess
            subprocess.run(["git", "-C", str(repo_root), "add", "."], check=True)
            subprocess.run(["git", "-C", str(repo_root), "commit", "-m", "init"], check=True)

            store = BreakerStore(repo_root)
            store.save({"timeout": {"t1", "t2"}, "compile_error": {"t1"}})

            plan_path = _make_plan(tmpdir, "t1")
            queue_path, _ = seed_git_queue(
                repo_root,
                [
                    {
                        "id": "t1",
                        "state": "failed",
                        "plan_file": plan_path,
                        "failure_signatures": ["timeout", "compile_error"],
                    }
                ],
            )

            args = aet_state.argparse.Namespace(
                command="reset",
                task_id="t1",
                queue=str(queue_path),
                force=False,
            )
            rc = aet_state.cmd_reset(args)
            self.assertEqual(rc, 0)

            task = load_git_queue(queue_path)[0]
            self.assertEqual(task["state"], "ready")
            self.assertNotIn("failure_signatures", task)
            tally = store.load()
            self.assertEqual(tally, {"timeout": {"t2"}})

    def test_reset_stage_flag(self):
        """--stage updates stage on soft reset, while hard reset clears stage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            init_git_repo(repo_root)
            (repo_root / "README.md").write_text("initial")
            import subprocess
            subprocess.run(["git", "-C", str(repo_root), "add", "."], check=True)
            subprocess.run(["git", "-C", str(repo_root), "commit", "-m", "init"], check=True)

            plan_path = _make_plan(tmpdir, "t1")
            queue_path, _ = seed_git_queue(
                repo_root,
                [
                    {
                        "id": "t1",
                        "state": "in_progress",
                        "plan_file": plan_path,
                        "stage": "qa",
                    }
                ],
            )

            # Soft reset with --stage
            args = aet_state.argparse.Namespace(
                command="reset",
                task_id="t1",
                queue=str(queue_path),
                stage="implement",
                force=False,
            )
            rc = aet_state.cmd_reset(args)
            self.assertEqual(rc, 0)
            task = load_git_queue(queue_path)[0]
            self.assertEqual(task["stage"], "implement")

            # Hard reset clears stage
            args_hard = aet_state.argparse.Namespace(
                command="reset",
                task_id="t1",
                queue=str(queue_path),
                hard=True,
                force=False,
            )
            rc = aet_state.cmd_reset(args_hard)
            self.assertEqual(rc, 0)
            task = load_git_queue(queue_path)[0]
            self.assertNotIn("stage", task)

    def test_reset_lease_guard_and_force(self):
        """Reset is blocked by active run lease unless --force is given."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            init_git_repo(repo_root)
            plan_path = _make_plan(tmpdir, "t1")
            queue_path, _ = seed_git_queue(
                repo_root,
                [
                    {
                        "id": "t1",
                        "state": "in_progress",
                        "plan_file": plan_path,
                    }
                ],
            )

            # Hold a lease with current process pid
            with patch.dict(os.environ, {"AET_RUN_ID": "run-local"}):
                acquire_lease(str(queue_path), "run-other")

                # Without force: refused
                args = aet_state.argparse.Namespace(
                    command="reset",
                    task_id="t1",
                    queue=str(queue_path),
                    force=False,
                )
                rc = aet_state.cmd_reset(args)
                self.assertEqual(rc, LEASE_HELD_EXIT_CODE)
                task = load_git_queue(queue_path)[0]
                self.assertEqual(task["state"], "in_progress")

                # With force: succeeds
                args_force = aet_state.argparse.Namespace(
                    command="reset",
                    task_id="t1",
                    queue=str(queue_path),
                    force=True,
                )
                rc = aet_state.cmd_reset(args_force)
                self.assertEqual(rc, 0)
                task = load_git_queue(queue_path)[0]
                self.assertEqual(task["state"], "ready")

if __name__ == "__main__":
    unittest.main()
