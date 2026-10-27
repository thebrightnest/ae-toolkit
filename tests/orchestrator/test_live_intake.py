"""A task added while a batch runs is spawned by the same batch (R-10)."""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from aet.backends.git_refs_backend import GitRefsBackend
from tests.orchestrator._helpers import history_path
from tests.orchestrator.test_orchestrator import (
    _FAKE_ADAPTER,
    _BatchRepoMixin,
    _InstantProc,
    orchestrator,
)


class TestLiveIntake(unittest.TestCase, _BatchRepoMixin):
    def test_spawn_pass_spawns_task_added_mid_run(self):
        with tempfile.TemporaryDirectory() as repo_root, tempfile.TemporaryDirectory() as archive_dir:
            alpha = {
                "id": "alpha",
                "title": "alpha",
                "plan_file": "docs/plans/alpha.md",
                "blocked_by": [],
                "state": "ready",
            }
            queue_file = self._init_batch_repo(repo_root, [alpha])
            beta_plan = Path(repo_root, "docs", "plans", "beta.md")
            beta_plan.write_text("---\nid: beta\n---\n\n# beta\n\n_Stage: plan-approved_\n", encoding="utf-8")
            subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
            subprocess.run(["git", "-C", repo_root, "commit", "-q", "-m", "add beta plan"], check=True)
            subprocess.run(
                ["git", "-C", repo_root, "update-ref", "refs/remotes/origin/main", "HEAD"],
                check=True,
            )
            args = self._make_args(repo_root, queue_file, max_jobs=1)

            spawned: list[str] = []

            def add_beta() -> None:
                intake = GitRefsBackend(queue_file=queue_file, history_file=history_path(queue_file))
                queue = intake.load()["queue"]
                queue.append({**alpha, "id": "beta", "title": "beta", "plan_file": "docs/plans/beta.md"})
                intake.save(queue)

            def fake_popen(*a, **kw):
                task_id = kw.get("env", {}).get("AET_TASK_ID")
                spawned.append(task_id)
                if task_id == "alpha":
                    add_beta()
                return _InstantProc()

            env = {"AET_TELEMETRY_ARCHIVE_DIR": archive_dir, "AET_PROJECT_ID": "demo/project"}
            with patch.dict(os.environ, env, clear=False):
                os.environ.pop("AET_RUN_ID", None)
                with self._patch_child_spawn(side_effect=fake_popen):
                    with patch.object(orchestrator, "verify_branch_has_commits", return_value=(True, "")):
                        rc, out, timed_out = self._run_batch(args, _FAKE_ADAPTER, timeout=120)

            self.assertFalse(timed_out, "run_batch timed out")
            self.assertEqual(rc, 0, out)
            self.assertEqual(spawned, ["alpha", "beta"])


if __name__ == "__main__":
    unittest.main()
