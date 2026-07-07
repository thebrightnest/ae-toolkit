"""Tests for orchestrator backend abstraction usage."""

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

# Load the orchestrator script (no .py extension) as a module.
_ORCHESTRATOR_BIN = Path(__file__).parent.parent / "aet-work" / "bin" / "orchestrator"
sys.path.insert(0, str(_ORCHESTRATOR_BIN.parent))
_orchestrator_loader = importlib.machinery.SourceFileLoader(
    "orchestrator", str(_ORCHESTRATOR_BIN)
)
_spec = importlib.util.spec_from_loader("orchestrator", _orchestrator_loader)
orchestrator = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(orchestrator)

from cli_adapter import CLIAdapter  # noqa: E402


_FAKE_ADAPTER = CLIAdapter(
    name="test",
    bin="echo",
    prompt_flag="-p",
    workdir_flag=None,
    headless_flag=None,
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


class FakeBackend:
    """In-memory backend that records every load/save call."""

    def __init__(self, queue: list[dict]):
        self.queue_file = "/fake/work-queue.json"
        self.history_file = "/fake/work-history.jsonl"
        self._queue = list(queue)
        self.calls: list[tuple[str, dict]] = []

    def load(self) -> dict:
        self.calls.append(("load", {}))
        return {"queue": list(self._queue), "history": []}

    def save(
        self, queue: list[dict], wrapper: dict | None = None
    ) -> None:
        self.calls.append(("save", {"queue": list(queue), "wrapper": wrapper}))
        self._queue = list(queue)

    def transition(
        self,
        task_id: str,
        from_state: str | None,
        to_state: str,
        by: str = "system",
        evidence: dict | None = None,
    ) -> bool:
        self.calls.append(
            (
                "transition",
                {
                    "task_id": task_id,
                    "from_state": from_state,
                    "to_state": to_state,
                },
            )
        )
        for task in self._queue:
            if task.get("id") == task_id:
                task["state"] = to_state
                return True
        return False

    def plan_drift(self, plans_dir: str | Path) -> list[str]:
        self.calls.append(("plan_drift", {"plans_dir": str(plans_dir)}))
        return []

    def close(self) -> None:
        self.calls.append(("close", {}))

    def sync_task(self, task: dict, is_new: bool) -> None:
        self.calls.append(("sync_task", {"task": task, "is_new": is_new}))


class TestRunSingleBackend(unittest.TestCase):
    def test_run_single_loads_queue_through_backend(self):
        """run_single reads the queued task via backend.load()."""
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
                        "state": "in_progress",
                    }
                ],
            )

            backend = FakeBackend([])
            backend.queue_file = os.path.join(repo_root, ".agents", "work-queue.json")
            backend.history_file = os.path.join(
                repo_root, ".agents", "work-history.jsonl"
            )

            args = _make_args(repo_root, plan_file)
            with patch.dict(
                os.environ,
                {"AET_EXECUTION_MODE": "unattended", "AET_PROJECT_ID": "tests"},
                clear=True,
            ):
                with patch.object(orchestrator, "process_task", return_value=True):
                    with patch.object(
                        orchestrator, "create_backend", return_value=backend
                    ):
                        exit_code = orchestrator.run_single(args, _FAKE_ADAPTER)

            self.assertEqual(exit_code, 0)
            self.assertTrue(any(c[0] == "load" for c in backend.calls))

    def test_run_single_saves_worktree_branch_metadata_through_backend(self):
        """run_single persists worktree/branch metadata via backend.save()."""
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
                        "state": "in_progress",
                    }
                ],
            )

            backend = FakeBackend(
                [
                    {
                        "id": "demo",
                        "title": "Demo",
                        "plan_file": "docs/plans/demo-plan.md",
                        "blocked_by": [],
                        "state": "in_progress",
                    }
                ]
            )
            backend.queue_file = os.path.join(repo_root, ".agents", "work-queue.json")
            backend.history_file = os.path.join(
                repo_root, ".agents", "work-history.jsonl"
            )

            args = _make_args(repo_root, plan_file)
            with patch.dict(
                os.environ,
                {"AET_EXECUTION_MODE": "unattended", "AET_PROJECT_ID": "tests"},
                clear=True,
            ):
                with patch.object(orchestrator, "process_task", return_value=True):
                    with patch.object(
                        orchestrator, "create_backend", return_value=backend
                    ):
                        exit_code = orchestrator.run_single(args, _FAKE_ADAPTER)

            self.assertEqual(exit_code, 0)
            save_calls = [c for c in backend.calls if c[0] == "save"]
            self.assertTrue(save_calls)
            saved_queue = save_calls[0][1]["queue"]
            task = next(t for t in saved_queue if t["id"] == "demo")
            self.assertEqual(task["branch"], "demo")
            self.assertEqual(task["worktree"], ".worktrees/demo")


class TestRunBatchBackend(unittest.TestCase):
    def test_run_batch_loads_queue_through_backend(self):
        """run_batch reads the active queue via backend.load()."""
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            queue_file = _write_queue(
                repo_root,
                [
                    {
                        "id": "demo",
                        "title": "Demo",
                        "plan_file": "docs/plans/demo-plan.md",
                        "blocked_by": [],
                        "state": "ready",
                    }
                ],
            )
            plan_file = os.path.join(repo_root, "docs", "plans", "demo-plan.md")
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

            task = {
                "id": "demo",
                "title": "Demo",
                "plan_file": "docs/plans/demo-plan.md",
                "blocked_by": [],
                "state": "ready",
            }
            backend = FakeBackend([task])
            backend.queue_file = queue_file
            backend.history_file = str(Path(queue_file).with_name("work-history.jsonl"))

            args = argparse.Namespace(
                queue_file=queue_file,
                plan_file=None,
                repo_root=repo_root,
                cli_bin="echo",
                isolation="standard",
                max_jobs=4,
            )

            with patch.dict(
                os.environ,
                {"AET_EXECUTION_MODE": "unattended", "AET_PROJECT_ID": "tests"},
                clear=True,
            ):
                with patch.object(
                    subprocess,
                    "run",
                    side_effect=lambda *a, **k: subprocess.CompletedProcess(
                        a[0] if a else [], 0, stdout="", stderr=""
                    ),
                ):
                    with patch.object(orchestrator.subprocess, "Popen") as mock_popen:
                        mock_proc = mock_popen.return_value
                        mock_proc.poll.return_value = 1
                        with patch.object(
                            orchestrator, "create_backend", return_value=backend
                        ):
                            exit_code = orchestrator.run_batch(args, _FAKE_ADAPTER)

            self.assertEqual(exit_code, 1)
            self.assertTrue(any(c[0] == "load" for c in backend.calls))

    def test_run_batch_saves_worktree_branch_metadata_through_backend(self):
        """run_batch persists worktree/branch metadata via backend.save()."""
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            queue_file = _write_queue(
                repo_root,
                [
                    {
                        "id": "demo",
                        "title": "Demo",
                        "plan_file": "docs/plans/demo-plan.md",
                        "blocked_by": [],
                        "state": "ready",
                    }
                ],
            )
            plan_file = os.path.join(repo_root, "docs", "plans", "demo-plan.md")
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

            task = {
                "id": "demo",
                "title": "Demo",
                "plan_file": "docs/plans/demo-plan.md",
                "blocked_by": [],
                "state": "ready",
            }
            backend = FakeBackend([task])
            backend.queue_file = queue_file
            backend.history_file = str(Path(queue_file).with_name("work-history.jsonl"))

            args = argparse.Namespace(
                queue_file=queue_file,
                plan_file=None,
                repo_root=repo_root,
                cli_bin="echo",
                isolation="standard",
                max_jobs=4,
            )

            with patch.dict(
                os.environ,
                {"AET_EXECUTION_MODE": "unattended", "AET_PROJECT_ID": "tests"},
                clear=True,
            ):
                with patch.object(
                    subprocess,
                    "run",
                    side_effect=lambda *a, **k: subprocess.CompletedProcess(
                        a[0] if a else [], 0, stdout="", stderr=""
                    ),
                ):
                    with patch.object(orchestrator.subprocess, "Popen") as mock_popen:
                        mock_proc = mock_popen.return_value
                        mock_proc.poll.return_value = 1
                        with patch.object(
                            orchestrator, "create_backend", return_value=backend
                        ):
                            exit_code = orchestrator.run_batch(args, _FAKE_ADAPTER)

            self.assertEqual(exit_code, 1)
            save_calls = [c for c in backend.calls if c[0] == "save"]
            self.assertTrue(save_calls)
            saved_queue = save_calls[0][1]["queue"]
            saved_task = next(t for t in saved_queue if t["id"] == "demo")
            self.assertEqual(saved_task["branch"], "demo")
            self.assertEqual(saved_task["worktree"], ".worktrees/demo")


class TestBackendFactoryPaths(unittest.TestCase):
    def test_backend_created_with_derived_history_path(self):
        """The orchestrator creates a backend using the queue file and derived history file."""
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            queue_file = _write_queue(repo_root, [])
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

            captured = {}

            def fake_create_backend(queue_file, history_file):
                captured["queue_file"] = queue_file
                captured["history_file"] = history_file
                backend = FakeBackend([])
                backend.queue_file = queue_file
                backend.history_file = history_file
                return backend

            args = _make_args(repo_root, plan_file)
            with patch.dict(os.environ, {"AET_EXECUTION_MODE": "unattended"}):
                with patch.object(orchestrator, "process_task", return_value=True):
                    with patch.object(
                        orchestrator, "create_backend", side_effect=fake_create_backend
                    ):
                        orchestrator.run_single(args, _FAKE_ADAPTER)

            self.assertEqual(captured["queue_file"], queue_file)
            self.assertEqual(
                captured["history_file"],
                str(Path(queue_file).with_name("work-history.jsonl")),
            )


if __name__ == "__main__":
    unittest.main()
