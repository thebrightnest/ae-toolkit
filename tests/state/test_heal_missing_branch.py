"""Tests for healing tasks whose branch/worktree has disappeared."""

import importlib.machinery
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from aet.backends.git_refs_backend import GitRefsBackend
from tests.state._helpers import init_git_repo, load_git_queue, seed_git_queue

_AET_STATE_PY = Path(__file__).parents[2] / "src" / "aet" / "cli" / "aet_state.py"

_spec = importlib.util.spec_from_loader(
    "aet_state", importlib.machinery.SourceFileLoader("aet_state", str(_AET_STATE_PY))
)
aet_state = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(aet_state)


class MockResult:
    def __init__(self, returncode, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _git_mock(responses):
    """Return a mock subprocess.run that answers git commands.

    responses maps tuple(git_args) -> (returncode, stdout, stderr).
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


def _make_queue(tmpdir, tasks):
    """Create a git-refs queue and history sidecar under tmpdir."""
    repo_root = Path(tmpdir)
    init_git_repo(repo_root)
    if not isinstance(tasks, list):
        tasks = [tasks]
    queue_path, history_path = seed_git_queue(repo_root, tasks)
    return queue_path


def _make_plan(tmpdir, task_id, blocked_by=None):
    """Write a minimal plan file for task_id under tmpdir/docs/plans."""
    plans_dir = Path(tmpdir) / "docs" / "plans"
    plans_dir.mkdir(parents=True, exist_ok=True)
    plan_path = plans_dir / f"{task_id}.md"
    plan_path.write_text("# Plan\n", encoding="utf-8")
    return str(plan_path)


class TestHealMissingBranch(unittest.TestCase):
    """Heal closes the gap where a deleted branch leaves a task stuck."""

    def test_heal_moves_in_progress_to_ready_and_clears_runtime(self):
        """An in_progress task whose branch is gone heals to ready and is unstarted."""
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
                command="heal",
                queue=str(queue_path),
                apply=True,
                force=False,
            )
            with patch.object(aet_state.subprocess, "run", side_effect=_git_mock(responses)):
                rc = aet_state.cmd_heal(args)

            self.assertEqual(rc, 0)
            task = load_git_queue(queue_path)[0]
            self.assertEqual(task["state"], "ready")
            self.assertNotIn("branch", task)
            self.assertNotIn("worktree", task)
            self.assertTrue(any(h["by"] == "heal" for h in task.get("history", [])))

    def test_heal_moves_awaiting_merge_to_ready_when_branch_deleted(self):
        """An awaiting_merge task with no merge verification heals to ready."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = _make_plan(tmpdir, "t1")
            queue_path = _make_queue(
                tmpdir,
                {
                    "id": "t1",
                    "state": "awaiting_merge",
                    "plan_file": plan_path,
                    "branch": "feat-t1",
                    "worktree": str(Path(tmpdir) / "wt"),
                },
            )

            responses = {
                ("show-ref", "--verify", "--quiet", "refs/heads/feat-t1"): (1, "", ""),
            }

            args = aet_state.argparse.Namespace(
                command="heal",
                queue=str(queue_path),
                apply=True,
                force=False,
            )
            with patch.object(aet_state.subprocess, "run", side_effect=_git_mock(responses)):
                rc = aet_state.cmd_heal(args)

            self.assertEqual(rc, 0)
            task = load_git_queue(queue_path)[0]
            self.assertEqual(task["state"], "ready")
            self.assertNotIn("branch", task)
            self.assertNotIn("worktree", task)

    def test_heal_moves_in_progress_to_blocked_when_blockers_not_terminal(self):
        """An in_progress task with live blockers heals to blocked."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = _make_plan(tmpdir, "t1")
            plan_path2 = _make_plan(tmpdir, "t2")
            queue_path = _make_queue(
                tmpdir,
                {
                    "id": "t1",
                    "state": "in_progress",
                    "plan_file": plan_path,
                    "branch": "feat-t1",
                    "blocked_by": ["t2"],
                    "pending_blockers": 1,
                },
            )
            # Append the blocker to the queue so derive_status can resolve it.
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
                command="heal",
                queue=str(queue_path),
                apply=True,
                force=False,
            )
            with patch.object(aet_state.subprocess, "run", side_effect=_git_mock(responses)):
                rc = aet_state.cmd_heal(args)

            self.assertEqual(rc, 0)
            by_id = {t["id"]: t for t in load_git_queue(queue_path)}
            self.assertEqual(by_id["t1"]["state"], "blocked")
            self.assertNotIn("branch", by_id["t1"])

    def test_heal_dry_run_reports_missing_branch_pair(self):
        """Dry-run heal reports the in_progress -> ready pair without mutating."""
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
                command="heal",
                queue=str(queue_path),
                apply=False,
                force=False,
            )
            stdout_capture = io.StringIO()
            with patch.object(aet_state.subprocess, "run", side_effect=_git_mock(responses)):
                with patch.object(aet_state.sys, "stdout", stdout_capture):
                    rc = aet_state.cmd_heal(args)

            self.assertEqual(rc, 0)
            output = stdout_capture.getvalue()
            self.assertIn("t1: in_progress -> ready", output)
            self.assertIn("branch no longer exists", output)

            task = load_git_queue(queue_path)[0]
            self.assertEqual(task["state"], "in_progress")
            self.assertEqual(task["branch"], "feat-t1")

    def test_audit_reports_missing_branch_pair(self):
        """audit names the (ready|blocked, in_progress) discrepancy."""
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
                command="audit",
                queue=str(queue_path),
                dry_run=False,
            )
            stdout_capture = io.StringIO()
            with patch.object(aet_state.subprocess, "run", side_effect=_git_mock(responses)):
                with patch.object(aet_state.sys, "stdout", stdout_capture):
                    rc = aet_state.cmd_audit(args)

            self.assertEqual(rc, 0)
            results = json.loads(stdout_capture.getvalue())
            self.assertEqual(results["t1"]["stored"], "in_progress")
            self.assertEqual(results["t1"]["derived"], "ready")
            self.assertTrue(results["t1"]["discrepancy"])


if __name__ == "__main__":
    unittest.main()
