"""Tests for the `aet state reset` single-task repair command."""

import importlib.machinery
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_AET_STATE_PY = Path(__file__).parents[2] / "src" / "aet" / "cli" / "aet_state.py"
_state_spec = importlib.util.spec_from_loader(
    "aet_state", importlib.machinery.SourceFileLoader("aet_state", str(_AET_STATE_PY))
)
aet_state = importlib.util.module_from_spec(_state_spec)
_state_spec.loader.exec_module(aet_state)

_INIT_QUEUE_PY = Path(__file__).parents[2] / "src" / "aet" / "cli" / "init_queue.py"
_init_spec = importlib.util.spec_from_loader(
    "init_queue", importlib.machinery.SourceFileLoader("init_queue", str(_INIT_QUEUE_PY))
)
init_queue = importlib.util.module_from_spec(_init_spec)
_init_spec.loader.exec_module(init_queue)


class MockResult:
    def __init__(self, returncode, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _git_mock(responses):
    """Return a mock subprocess.run that answers git commands."""

    def mock_run(cmd, **kwargs):
        args = tuple(cmd[1:])
        rc, out, err = responses.get(args, (1, "", ""))
        return MockResult(rc, out, err)

    return mock_run


def _make_queue(tmpdir, task):
    queue_path = Path(tmpdir) / "work-queue.json"
    history_path = queue_path.with_name("work-history.jsonl")
    history_path.write_text("", encoding="utf-8")
    queue_path.write_text(json.dumps({"tasks": [task]}), encoding="utf-8")
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
            with open(queue_path, "r", encoding="utf-8") as f:
                after = json.load(f)
            task = after["tasks"][0]
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
            with open(queue_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["tasks"].append(
                {
                    "id": "t2",
                    "state": "planned",
                    "plan_file": plan_path2,
                    "branch": None,
                }
            )
            with open(queue_path, "w", encoding="utf-8") as f:
                json.dump(data, f)

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
            with open(queue_path, "r", encoding="utf-8") as f:
                after = json.load(f)
            by_id = {t["id"]: t for t in after["tasks"]}
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
                apply=False,
                force=False,
            )
            stdout_capture = io.StringIO()
            with patch.object(aet_state.subprocess, "run", side_effect=_git_mock(responses)):
                with patch.object(aet_state.sys, "stdout", stdout_capture):
                    rc = aet_state.cmd_reset(args)

            self.assertEqual(rc, 0)
            output = stdout_capture.getvalue()
            self.assertIn("t1: in_progress -> ready", output)

            with open(queue_path, "r", encoding="utf-8") as f:
                after = json.load(f)
            self.assertEqual(after["tasks"][0]["state"], "in_progress")
            self.assertEqual(after["tasks"][0]["branch"], "feat-t1")

    def test_reset_round_trips_through_init_queue_unchanged(self):
        """After reset, init-queue reproduces the same state and no runtime fields."""
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

            reset_args = aet_state.argparse.Namespace(
                command="reset",
                task_id="t1",
                queue=str(queue_path),
                apply=True,
                force=False,
            )
            with patch.object(aet_state.subprocess, "run", side_effect=_git_mock(responses)):
                rc = aet_state.cmd_reset(reset_args)
            self.assertEqual(rc, 0)

            # Run init-queue over the same plans directory.
            history_file = str(queue_path.with_name("work-history.jsonl"))
            rc = init_queue._run(
                queue_file=str(queue_path),
                history_file=history_file,
                plans_dir=Path(tmpdir) / "docs" / "plans",
                prds_dir=Path(tmpdir) / "docs" / "prds",
                config=str(Path(tmpdir) / ".agents" / "aet-work.json"),
                force=False,
            )
            self.assertEqual(rc, 0)

            with open(queue_path, "r", encoding="utf-8") as f:
                after = json.load(f)
            task = after["tasks"][0]
            self.assertEqual(task["state"], "ready")
            self.assertIsNone(task.get("branch"))
            self.assertIsNone(task.get("worktree"))


if __name__ == "__main__":
    unittest.main()
