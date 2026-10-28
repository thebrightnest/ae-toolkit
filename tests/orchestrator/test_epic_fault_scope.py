"""A fault on one task or epic skips only that scope (R-6, R-7, R-9)."""

from __future__ import annotations

import argparse
import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
import subprocess
import tempfile
import unittest
import unittest.mock
from pathlib import Path

import pytest

from tests.orchestrator._helpers import init_epic_repo, install_fake_agent, load_queue, write_queue

_ORCHESTRATOR_BIN = Path(__file__).parents[2] / "src" / "aet" / "cli" / "orchestrator.py"
_orchestrator_loader = importlib.machinery.SourceFileLoader("orchestrator", str(_ORCHESTRATOR_BIN))
_spec = importlib.util.spec_from_loader("orchestrator", _orchestrator_loader)
orchestrator = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(orchestrator)

pytestmark = pytest.mark.xdist_group("git-repo")


def _git(repo_root: str, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", repo_root, *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def _run(repo_root: str, queue_file: str, scratch: str, run_id: str) -> tuple[int, str]:
    bin_dir, adapter = install_fake_agent(scratch)
    args = argparse.Namespace(
        queue_file=queue_file,
        repo_root=repo_root,
        base=None,
        isolation="standard",
        max_jobs=1,
        task_timeout=600,
        heartbeat_interval=60,
        on_failure="continue",
        run_id=run_id,
    )
    out = io.StringIO()
    env = {"PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}
    with unittest.mock.patch.dict(os.environ, env), contextlib.redirect_stdout(out):
        exit_code = orchestrator.run_batch(args, adapter)
    return exit_code, out.getvalue()


def _last_run(output: str) -> dict:
    run_dir = output.rsplit("Telemetry: ", 1)[1].splitlines()[0].strip()
    return json.loads(Path(run_dir, "last-run.json").read_text(encoding="utf-8"))


class TestEpicFaultScope(unittest.TestCase):
    def test_stamp_mismatch_skips_only_that_task(self):
        """R-6, R-9: a stale stamp skips its task; the other task completes."""
        with (
            tempfile.TemporaryDirectory() as repo_root,
            tempfile.TemporaryDirectory() as origin_root,
            tempfile.TemporaryDirectory() as scratch,
        ):
            plans = init_epic_repo(
                repo_root, origin_root, {"task-old": "new-prd", "task-b": "b-prd"}
            )
            queue_file = write_queue(
                repo_root,
                [
                    {
                        "id": "task-old",
                        "state": "ready",
                        "plan_file": plans["task-old"],
                        "integration_branch": "feat/old",
                    },
                    {"id": "task-b", "state": "ready", "plan_file": plans["task-b"]},
                ],
            )

            exit_code, output = _run(repo_root, queue_file, scratch, "run-stamp-skip")

            states = {t["id"]: t["state"] for t in load_queue(queue_file)}
            self.assertEqual(exit_code, 1, output)
            self.assertEqual(states.get("task-old"), "ready", output)
            self.assertNotIn("task-b", states, output)
            self.assertIn("Integrate task-b", _git(repo_root, "log", "origin/feat/b", "--format=%s"))
            summary = output.split("🏁 Orchestrator finished.")[1]
            self.assertIn("Skipped:   1", summary)
            self.assertIn("task-old: epic mismatch", summary)
            self.assertIn("feat/old", summary)
            self.assertIn("feat/new", summary)
            self.assertIn("Failed:    0", summary)
            record = _last_run(output)
            self.assertEqual(record["exit_code"], 1)
            self.assertIn("task-old", record["skipped"])
            self.assertIn("remedy", record["skipped"]["task-old"])

    def test_cross_epic_dependency_is_not_spawned(self):
        """R-7: a feat/b task blocked by a task integrated into feat/a is skipped."""
        with (
            tempfile.TemporaryDirectory() as repo_root,
            tempfile.TemporaryDirectory() as origin_root,
            tempfile.TemporaryDirectory() as scratch,
        ):
            plans = init_epic_repo(
                repo_root, origin_root, {"task-a": "a-prd", "task-b": "b-prd"}
            )
            queue_file = write_queue(
                repo_root,
                [
                    {
                        "id": "task-a",
                        "state": "ready",
                        "plan_file": plans["task-a"],
                        "blocks": ["task-b"],
                    },
                    {
                        "id": "task-b",
                        "state": "blocked",
                        "plan_file": plans["task-b"],
                        "blocked_by": ["task-a"],
                        "pending_blockers": 1,
                    },
                ],
            )

            exit_code, output = _run(repo_root, queue_file, scratch, "run-cross-epic")

            states = {t["id"]: t["state"] for t in load_queue(queue_file)}
            self.assertEqual(exit_code, 1, output)
            self.assertNotIn("task-a", states, output)
            self.assertEqual(states.get("task-b"), "ready", output)
            self.assertNotIn("Spawned task-b", output)
            self.assertFalse(Path(repo_root, ".worktrees", "task-b").exists())
            summary = output.split("🏁 Orchestrator finished.")[1]
            self.assertIn("task-b: cross-epic dependency", summary)
            self.assertIn("feat/a", summary)
            self.assertIn("feat/b", summary)

    def test_blocker_on_same_epic_or_on_trunk_is_not_cross_epic(self):
        """R-7: a shared branch, a blocker merged to trunk, or an unknown blocker is no skip."""
        with (
            tempfile.TemporaryDirectory() as repo_root,
            tempfile.TemporaryDirectory() as origin_root,
        ):
            plans = init_epic_repo(
                repo_root, origin_root, {"task-a": "a-prd", "task-b": "b-prd"}
            )
            backend = orchestrator._make_backend(write_queue(repo_root, []))
            dependent = {"id": "task-b", "plan_file": plans["task-b"], "blocked_by": ["task-a"]}
            blocker = {"id": "task-a", "plan_file": plans["task-a"]}

            def check(blocker_record: dict, task_branch: str = "feat/b"):
                return orchestrator.cross_epic_blocker(
                    repo_root, {}, dependent, task_branch, "main", [blocker_record], backend
                )

            self.assertEqual(check(blocker), ("task-a", "feat/a"))
            self.assertIsNone(check(blocker, task_branch="origin/feat/a"))
            on_trunk = {**blocker, "merge_commit": _git(repo_root, "rev-parse", "HEAD")}
            self.assertIsNone(check(on_trunk))
            self.assertIsNone(
                orchestrator.cross_epic_blocker(
                    repo_root, {}, dependent, "feat/b", "main", [], backend
                )
            )


if __name__ == "__main__":
    unittest.main()
