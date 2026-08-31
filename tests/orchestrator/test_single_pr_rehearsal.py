"""Rehearsal for single-pr mode with a real dependency install (R-12).

Runs a two-task epic unattended in ``single-pr`` mode, using a shadow-layer
config and a non-trunk integration branch. The healthy fixture performs a real
``npm ci`` install and executes the pinned dependency, proving the live-tip
sequencing and integration path used by the production configuration.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import pytest

from tests.orchestrator._helpers import write_queue

# Load the orchestrator script (no .py extension) as a module.
_ORCHESTRATOR_BIN = Path(__file__).parents[2] / "src" / "aet" / "cli" / "orchestrator.py"
_orchestrator_loader = importlib.machinery.SourceFileLoader(
    "orchestrator", str(_ORCHESTRATOR_BIN)
)
_spec = importlib.util.spec_from_loader("orchestrator", _orchestrator_loader)
orchestrator = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(orchestrator)

from aet.backends.factory import resolve_integration_mode_with_provenance  # noqa: E402

pytestmark = pytest.mark.xdist_group("process-group")

FIXTURES_DIR = Path(__file__).parents[1] / "fixtures" / "single-pr"
PROJECT_SLUG = "single-pr-rehearsal"

if shutil.which("npm") is None:
    pytest.skip("npm is not installed; single-pr rehearsal requires npm", allow_module_level=True)


def _init_git_repo(repo_root: str, origin_root: str) -> None:
    """Initialize a git repo with main and a bare origin remote."""
    subprocess.run(["git", "init", "--bare", "-q", origin_root], check=True)
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
    Path(repo_root, ".gitignore").write_text(".agents/aet-queue\n", encoding="utf-8")
    subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
    subprocess.run(
        ["git", "-C", repo_root, "commit", "-q", "-m", "initial"],
        check=True,
    )
    subprocess.run(["git", "-C", repo_root, "branch", "-M", "main"], check=True)
    subprocess.run(
        ["git", "-C", repo_root, "remote", "add", "origin", origin_root],
        check=True,
    )
    subprocess.run(
        ["git", "-C", repo_root, "push", "-q", "-u", "origin", "main"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", repo_root, "update-ref", "refs/remotes/origin/main", "HEAD"],
        check=True,
    )


def _create_integration_branch(repo_root: str, name: str = "epic-rehearsal") -> None:
    """Create and push an integration branch from the current HEAD."""
    subprocess.run(
        ["git", "-C", repo_root, "checkout", "-q", "-b", name],
        check=True,
    )
    subprocess.run(
        ["git", "-C", repo_root, "push", "-q", "-u", "origin", name],
        check=True,
    )
    subprocess.run(
        ["git", "-C", repo_root, "update-ref", f"refs/remotes/origin/{name}", "HEAD"],
        check=True,
    )
    subprocess.run(["git", "-C", repo_root, "checkout", "-q", "main"], check=True)


def _copy_fixtures(repo_root: str) -> Path:
    """Copy the single-pr fixture plans and npm package into the temp repo."""
    dest = Path(repo_root) / "tests" / "fixtures" / "single-pr"
    dest.mkdir(parents=True, exist_ok=True)
    for plan in FIXTURES_DIR.glob("*.md"):
        (dest / plan.name).write_text(plan.read_text(encoding="utf-8"), encoding="utf-8")
    npm_src = FIXTURES_DIR / "npm"
    npm_dest = dest / "npm"
    npm_dest.mkdir(parents=True, exist_ok=True)
    for f in npm_src.iterdir():
        if f.is_file():
            (npm_dest / f.name).write_bytes(f.read_bytes())
    return dest


def _write_rehearsal_workflow(repo_root: str) -> Path:
    """Write a single-skilled-stage workflow so the rehearsal stays focused."""
    workflow_path = Path(repo_root) / ".agents" / "workflows" / "rehearsal.json"
    workflow_path.parent.mkdir(parents=True, exist_ok=True)
    workflow_path.write_text(
        json.dumps(
            {
                "version": 1,
                "name": "rehearsal",
                "done_state": "implemented",
                "stages": [
                    {
                        "name": "plan-approved",
                        "skills": ["aet-tdd", "aet-implement"],
                        "evidence": None,
                        "gate_key": None,
                    },
                    {
                        "name": "implemented",
                        "skills": [],
                        "evidence": None,
                        "gate_key": None,
                    },
                ],
                "execution_policy": {"session_groups": [["plan-approved"]]},
                "routing": {
                    "default": {"harness": "claude", "model": None},
                    "by_stage": {},
                },
            }
        ),
        encoding="utf-8",
    )
    return workflow_path


def _write_validation_script(repo_root: str) -> Path:
    """Write a post-rebase validation script that re-runs the real install."""
    script = Path(repo_root) / ".agents" / "validate-rehearsal.sh"
    script.write_text(
        "#!/bin/bash\n"
        "set -euo pipefail\n"
        "cd \"$(git rev-parse --show-toplevel)/tests/fixtures/single-pr/npm\"\n"
        "npm ci\n"
        "node index.js\n",
        encoding="utf-8",
    )
    script.chmod(0o755)
    return script


def _write_fake_claude(repo_root: str) -> Path:
    """Create a fake claude CLI that drives the real npm fixture behavior."""
    bin_dir = Path(repo_root) / "bin"
    bin_dir.mkdir(exist_ok=True)
    fake_cli = bin_dir / "claude"
    fake_cli.write_text(
        '#!/usr/bin/env python3\n'
        'import os\n'
        'import subprocess\n'
        'import sys\n'
        '\n'
        'fixture_dir = "tests/fixtures/single-pr/npm"\n'
        'task_id = os.environ.get("AET_TASK_ID", "task")\n'
        '\n'
        'subprocess.run(["npm", "ci"], cwd=fixture_dir, check=True)\n'
        'subprocess.run(["node", "index.js"], cwd=fixture_dir, check=True)\n'
        'subprocess.run(\n'
        '    ["git", "add", f"{fixture_dir}/marker.txt"], check=True\n'
        ')\n'
        'subprocess.run(\n'
        '    ["git", "commit", "-q", "-m", f"rehearsal: {task_id}"], check=True\n'
        ')\n'
        'print(\n'
        '    \'[{"type": "result", "usage": \'\n'
        '    \'{"input_tokens": 10, "output_tokens": 5}, \'\n'
        '    \'"total_cost_usd": 0.001}]\'\n'
        ')\n'
        'sys.exit(0)\n',
        encoding="utf-8",
    )
    fake_cli.chmod(0o755)
    return fake_cli


def _write_shadow_config(home_dir: str, slug: str) -> Path:
    """Write the shadow-layer config under the patched HOME directory."""
    config_dir = Path(home_dir) / ".aet" / slug
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "trunk_branch": "main",
                "integration_branch": "epic-rehearsal",
                "integration_mode": "single-pr",
            }
        ),
        encoding="utf-8",
    )
    return config_path


def _write_queue(repo_root: str) -> str:
    """Seed the single-pr rehearsal queue into the git-refs backend."""
    return write_queue(
        repo_root,
        [
            {
                "id": "first-task",
                "title": "First fixture task",
                "plan_file": "tests/fixtures/single-pr/first-task.md",
                "blocked_by": [],
                "blocks": ["second-task"],
                "state": "ready",
            },
            {
                "id": "second-task",
                "title": "Second fixture task",
                "plan_file": "tests/fixtures/single-pr/second-task.md",
                "blocked_by": ["first-task"],
                "pending_blockers": 1,
                "state": "blocked",
            },
        ],
    )


def _commit_repo_state(repo_root: str) -> None:
    """Commit fixtures, workflow, fake CLI, and validation script.

    The queue file is gitignored and left untracked so that branch checkouts
    in the temp repo do not revert its live state.
    """
    subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
    subprocess.run(
        ["git", "-C", repo_root, "commit", "-q", "-m", "add fixtures and queue"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", repo_root, "update-ref", "refs/remotes/origin/main", "HEAD"],
        check=True,
    )


def _remote_heads(repo_root: str) -> set[str]:
    result = subprocess.run(
        ["git", "-C", repo_root, "ls-remote", "--heads", "origin"],
        capture_output=True,
        text=True,
        check=True,
    )
    return {line.split()[1].removeprefix("refs/heads/") for line in result.stdout.splitlines()}


def _integration_log(repo_root: str, branch: str = "epic-rehearsal") -> list[str]:
    result = subprocess.run(
        ["git", "-C", repo_root, "log", f"origin/{branch}", "--format=%s"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


class TestSinglePrRehearsal(unittest.TestCase):
    """End-to-end rehearsal over a two-task single-pr epic with a real install."""

    run_out: str
    repo_root: str
    queue_file: str

    @classmethod
    def setUpClass(cls):
        """Run the one rehearsal the whole class asserts against."""
        cls.repo_root, cls.queue_file, args, adapter = cls._setup_repo()
        _rc, cls.run_out = cls._run_batch(args, adapter, timeout=120)

    @staticmethod
    def _run_batch(args, adapter, timeout: float = 300):
        """Run run_batch in a thread; return (rc, stdout)."""
        result = {"rc": None, "out": ""}
        orchestrator._shutdown_requested = False
        buf = io.StringIO()

        def target():
            with contextlib.redirect_stdout(buf):
                result["rc"] = orchestrator.run_batch(args, adapter)
            result["out"] = buf.getvalue()

        thread = threading.Thread(target=target)
        thread.start()
        thread.join(timeout=timeout)
        if thread.is_alive():
            orchestrator._shutdown_requested = True
            thread.join(timeout=5)
            print("=== run_batch output before timeout ===")
            print(buf.getvalue())
            raise AssertionError("run_batch did not finish within timeout")
        return result["rc"], result["out"]

    @classmethod
    def _setup_repo(cls):
        """Create a temp repo with fixtures, fake CLI, shadow config, and queue."""
        repo_root = tempfile.mkdtemp(prefix="single-pr-rehearsal-")
        origin_root = tempfile.mkdtemp(prefix="single-pr-origin-")
        cls.addClassCleanup(lambda: subprocess.run(["rm", "-rf", repo_root, origin_root]))

        _init_git_repo(repo_root, origin_root)
        _copy_fixtures(repo_root)
        _write_rehearsal_workflow(repo_root)
        _write_validation_script(repo_root)
        fake_cli = _write_fake_claude(repo_root)
        _commit_repo_state(repo_root)
        queue_file = _write_queue(repo_root)
        _create_integration_branch(repo_root, "epic-rehearsal")

        # Patch HOME so the shadow-layer config resolves under a temp directory.
        home_dir = tempfile.mkdtemp(prefix="single-pr-home-")
        cls.addClassCleanup(lambda: subprocess.run(["rm", "-rf", home_dir]))
        _write_shadow_config(home_dir, PROJECT_SLUG)

        new_path = f"{fake_cli.parent}{os.pathsep}{os.environ.get('PATH', '')}"
        env = {
            "HOME": home_dir,
            "PATH": new_path,
            "AET_PROJECT_ID": PROJECT_SLUG,
            "AET_INTEGRATION_VALIDATE_CMD": ".agents/validate-rehearsal.sh",
        }
        # Add to the environment rather than replacing it. ``clear=True`` here
        # discarded the isolation ``_isolate_class_scoped_setup`` establishes,
        # so this rehearsal wrote its telemetry and ledger events into the
        # developer's real stores. The variables this rehearsal must not
        # inherit are removed by name instead.
        for leaked in ("AET_TASK_ID", "AET_RUN_ID", "AET_REPO_ROOT"):
            os.environ.pop(leaked, None)
        cls.enterClassContext(patch.dict(os.environ, env))

        adapter = orchestrator.resolve_cli_adapter("claude")
        args = argparse.Namespace(
            queue_file=queue_file,
            plan_file=None,
            repo_root=repo_root,
            cli_bin="claude",
            isolation="minimal",
            max_jobs=1,
            task_timeout=300,
            heartbeat_interval=999,
            on_failure="triage",
        )
        return repo_root, queue_file, args, adapter

    def _settled_tasks(self) -> dict[str, dict]:
        """Return sealed task records, indexed by id.

        The rehearsal runs in shadow posture — its config resolves from the
        user-scope layer, and resolution is external-first, so no in-tree
        config can make ``project`` the effective source. Shadow posture keeps
        AET artifacts out of the working tree, so ``work-history.jsonl`` is
        never written; the durable settled record is the per-task tombstone
        blob at ``refs/aet/sealed/<id>``.
        """
        refs = subprocess.run(
            [
                "git", "-C", self.repo_root, "for-each-ref",
                "--format=%(refname)", "refs/aet/sealed/",
            ],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.split()
        tasks: dict[str, dict] = {}
        for ref in refs:
            blob = subprocess.run(
                ["git", "-C", self.repo_root, "cat-file", "blob", ref],
                capture_output=True,
                text=True,
                check=True,
            ).stdout
            record = json.loads(blob)
            tasks[record["id"]] = record
        return tasks

    def test_batch_succeeds(self):
        """The rehearsal shift exits cleanly."""
        self.assertIn("Orchestrator finished", self.run_out)

    def test_both_tasks_reach_merged(self):
        """Both tasks are sealed to the settled history as merged."""
        by_id = self._settled_tasks()
        self.assertEqual(by_id["first-task"]["state"], "merged")
        self.assertEqual(by_id["second-task"]["state"], "merged")
        self.assertIn("merge_commit", by_id["first-task"])
        self.assertIn("merge_commit", by_id["second-task"])

    def test_only_integration_branch_pushed(self):
        """No per-task branch reaches origin; only main and the epic branch."""
        heads = _remote_heads(self.repo_root)
        self.assertEqual(heads, {"main", "epic-rehearsal"})

    def test_integration_log_contains_both_commits_in_order(self):
        """origin/epic-rehearsal has both squash-merge commits in dependency order."""
        log = _integration_log(self.repo_root, "epic-rehearsal")
        self.assertIn("Integrate first-task", log)
        self.assertIn("Integrate second-task", log)
        # ``git log`` lists newest first, so the second (later) commit appears
        # before the first (earlier) commit.
        self.assertLess(
            log.index("Integrate second-task"),
            log.index("Integrate first-task"),
        )

    def test_second_marker_includes_first_task_output(self):
        """The second task's committed marker proves it started from the live tip."""
        result = subprocess.run(
            [
                "git",
                "-C",
                self.repo_root,
                "show",
                "origin/epic-rehearsal:tests/fixtures/single-pr/npm/marker.txt",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        marker = result.stdout
        self.assertIn("first-task: is-number(7)=true", marker)
        self.assertIn("second-task: is-number(7)=true", marker)

    def test_resolve_integration_mode_reports_shadow_layer(self):
        """The shadow-layer config (user) supplies the integration mode."""
        mode, provenance = resolve_integration_mode_with_provenance()
        self.assertEqual(mode, "single-pr")
        self.assertEqual(provenance, "config (user)")


if __name__ == "__main__":
    unittest.main()
