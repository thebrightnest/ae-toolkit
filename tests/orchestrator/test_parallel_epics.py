"""One `aet run` drives tasks from two PRDs into two integration branches."""

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

_PROBE_HOOK = "\n".join(
    [
        "import json, pathlib, subprocess, time",
        "probe = {}",
        "probe['feat_b_on_origin'] = subprocess.run(",
        "    ['git', '-C', repo_root, 'ls-remote', 'origin', 'feat/b'],",
        "    capture_output=True, text=True, check=True,",
        ").stdout.strip()",
        "probe['has_feat_a_seed'] = subprocess.run(",
        "    ['git', '-C', wt, 'merge-base', '--is-ancestor', 'SEED', 'HEAD'],",
        ").returncode == 0",
        "hooks = pathlib.Path(repo_root, '.agents', 'hooks')",
        "(hooks / (name + '.started')).touch()",
        "peer = 'task-b' if name == 'task-a' else 'task-a'",
        "deadline = time.time() + 30",
        "while not (hooks / (peer + '.started')).exists() and time.time() < deadline:",
        "    time.sleep(0.05)",
        "probe['saw_peer'] = (hooks / (peer + '.started')).exists()",
        "pathlib.Path(repo_root, '.agents', 'hooks', name + '.json').write_text(json.dumps(probe))",
    ]
)


def _git(repo_root: str, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", repo_root, *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def _lock_holds(log_path: str) -> list[tuple[float, float]]:
    holds: list[tuple[float, float]] = []
    opened: dict[int, float] = {}
    for line in Path(log_path).read_text(encoding="utf-8").splitlines():
        event = json.loads(line)
        if event["event"] == "acquired":
            opened[event["pid"]] = event["time"]
        elif event["event"] == "releasing":
            holds.append((opened.pop(event["pid"]), event["time"]))
    return holds


class TestParallelEpics(unittest.TestCase):
    def test_two_prds_run_concurrently_into_their_own_branches(self):
        """R-3, R-4, R-8, R-10: per-task bases, local epic creation, serialized integration."""
        with (
            tempfile.TemporaryDirectory() as repo_root,
            tempfile.TemporaryDirectory() as origin_root,
            tempfile.TemporaryDirectory() as scratch,
        ):
            plans = init_epic_repo(
                repo_root, origin_root, {"task-a": "a-prd", "task-b": "b-prd"}
            )
            _git(repo_root, "checkout", "-q", "-b", "feat/a")
            Path(repo_root, "a-seed.txt").write_text("seed", encoding="utf-8")
            _git(repo_root, "add", "a-seed.txt")
            _git(repo_root, "commit", "-q", "-m", "feat/a seed")
            seed = _git(repo_root, "rev-parse", "HEAD")
            _git(repo_root, "push", "-q", "-u", "origin", "feat/a")
            _git(repo_root, "checkout", "-q", "main")

            hooks = Path(repo_root, ".agents", "hooks")
            hooks.mkdir(parents=True, exist_ok=True)
            for task_id in ("task-a", "task-b"):
                (hooks / f"{task_id}.py").write_text(
                    _PROBE_HOOK.replace("SEED", seed), encoding="utf-8"
                )

            queue_file = write_queue(
                repo_root,
                [
                    {"id": "task-a", "state": "ready", "plan_file": plans["task-a"]},
                    {"id": "task-b", "state": "ready", "plan_file": plans["task-b"]},
                ],
            )
            bin_dir, adapter = install_fake_agent(scratch)
            lock_log = os.path.join(scratch, "lock.log")
            args = argparse.Namespace(
                queue_file=queue_file,
                repo_root=repo_root,
                base=None,
                isolation="standard",
                max_jobs=2,
                task_timeout=600,
                heartbeat_interval=60,
                on_failure="continue",
                run_id="run-parallel-epics",
            )

            out = io.StringIO()
            env = {
                "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
                "AET_INTEGRATION_LOCK_LOG": lock_log,
            }
            with unittest.mock.patch.dict(os.environ, env), contextlib.redirect_stdout(out):
                exit_code = orchestrator.run_batch(args, adapter)

            output = out.getvalue()
            self.assertEqual(exit_code, 0, output)
            self.assertIn("feat/a (prd)", output)
            self.assertIn("feat/b (prd)", output)
            self.assertEqual(load_queue(queue_file), [], output)

            probe_a = json.loads((hooks / "task-a.json").read_text(encoding="utf-8"))
            probe_b = json.loads((hooks / "task-b.json").read_text(encoding="utf-8"))
            self.assertTrue(probe_a["saw_peer"], output)
            self.assertTrue(probe_b["saw_peer"], output)
            self.assertTrue(probe_a["has_feat_a_seed"])
            self.assertFalse(probe_b["has_feat_a_seed"])
            self.assertEqual(probe_b["feat_b_on_origin"], "")

            log_a = _git(repo_root, "log", "origin/feat/a", "--format=%s")
            log_b = _git(repo_root, "log", "origin/feat/b", "--format=%s")
            self.assertIn("Integrate task-a", log_a)
            self.assertNotIn("Integrate task-b", log_a)
            self.assertIn("Integrate task-b", log_b)
            self.assertNotIn("feat/a seed", log_b)

            holds = sorted(_lock_holds(lock_log))
            self.assertGreaterEqual(len(holds), 2, holds)
            for earlier, later in zip(holds, holds[1:]):
                self.assertLessEqual(earlier[1], later[0], holds)


if __name__ == "__main__":
    unittest.main()
