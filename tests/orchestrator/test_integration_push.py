"""Tests for integration-branch durability push in single-pr mode (R-20).

Covers ADR-045 decision 4: only the epic integration branch reaches origin,
and it is pushed after every successful integration so the last integrated tip
is always durable.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from aet.cli_adapter import CLIAdapter

_ORCHESTRATOR_BIN = Path(__file__).parents[2] / "src" / "aet" / "cli" / "orchestrator.py"
_orchestrator_loader = importlib.machinery.SourceFileLoader(
    "orchestrator", str(_ORCHESTRATOR_BIN)
)
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


def _create_integration_branch(repo_root: str, name: str = "epic-01") -> None:
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


def _write_plan(repo_root: str, task_id: str, blocked_by: list[str] | None = None) -> str:
    plan_file = os.path.join(repo_root, "docs", "plans", f"{task_id}.md")
    Path(plan_file).parent.mkdir(parents=True, exist_ok=True)
    frontmatter: dict[str, object] = {"id": task_id}
    if blocked_by:
        frontmatter["blocked_by"] = blocked_by
    Path(plan_file).write_text(
        f"---\n{yaml.safe_dump(frontmatter, sort_keys=False)}---\n\n# {task_id}\n\n_Stage: implemented_\n",
        encoding="utf-8",
    )
    return plan_file


def _add_commit_to_worktree(worktree_dir: str, filename: str, content: str) -> None:
    Path(worktree_dir, filename).write_text(content, encoding="utf-8")
    subprocess.run(["git", "-C", worktree_dir, "add", "."], check=True)
    subprocess.run(
        ["git", "-C", worktree_dir, "commit", "-q", "-m", f"add {filename}"],
        check=True,
    )


def _write_verdict(repo_root: str, task_id: str, kind: str) -> None:
    """Write a passing verdict for task_id to the canonical evidence path."""
    from aet import evidence as ev
    from aet import telemetry

    project_slug = telemetry.derive_project_slug(repo_root)
    base_record = {
        "task_id": task_id,
        "stage": "qa-complete" if kind == "qa" else kind,
        "skill": f"aet-{kind}",
        "verdict": "pass",
        "summary": f"fake {kind} passed",
        "generated_at": telemetry.iso_now(),
        "tree_hash": "",
    }
    if kind == "qa":
        record = {
            **base_record,
            "test_command": "make validate",
            "tests_total": 1,
            "tests_passed": 1,
            "tests_failed": 0,
        }
    elif kind in ("review", "cso"):
        record = {**base_record, "findings": []}
    elif kind == "sync-docs":
        record = {**base_record, "divergences": []}
    else:
        raise ValueError(f"unknown kind: {kind}")
    ev.write_verdict(task_id, kind, record, project_slug=project_slug)


def _remote_heads(repo_root: str) -> list[str]:
    result = subprocess.run(
        ["git", "-C", repo_root, "ls-remote", "--heads", "origin"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [line.split()[1].removeprefix("refs/heads/") for line in result.stdout.splitlines()]


def _integration_log(repo_root: str, integration_branch: str) -> list[str]:
    result = subprocess.run(
        ["git", "-C", repo_root, "log", f"origin/{integration_branch}", "--oneline"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


class TestIntegrationPush(unittest.TestCase):
    def test_origin_reflects_last_integrated_tip_after_each_task(self):
        """R-20: the integration branch tip on origin advances after every task."""
        self.maxDiff = None
        with tempfile.TemporaryDirectory() as repo_root, tempfile.TemporaryDirectory() as origin_root:
            _init_git_repo(repo_root, origin_root)

            Path(repo_root, ".agents").mkdir(parents=True, exist_ok=True)
            Path(repo_root, ".agents", "aet-config.json").write_text(
                json.dumps(
                    {
                        "trunk_branch": "main",
                        "integration_branch": "epic-01",
                        "integration_mode": "single-pr",
                    }
                ),
                encoding="utf-8",
            )

            plan_a = _write_plan(repo_root, "task-a")
            _write_plan(repo_root, "task-b", blocked_by=["task-a"])

            subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
            subprocess.run(
                ["git", "-C", repo_root, "commit", "-q", "-m", "add plans"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", repo_root, "update-ref", "refs/remotes/origin/main", "HEAD"],
                check=True,
            )
            _create_integration_branch(repo_root, "epic-01")

            env = os.environ.copy()
            env["AET_PROJECT_ID"] = "demo-project"
            env["AET_INTEGRATION_VALIDATE_CMD"] = "true"

            with patch.dict(os.environ, env, clear=True):
                # Task A
                worktree_a = orchestrator.create_worktree(
                    repo_root, "task-a", base_branch="origin/epic-01"
                )
                _add_commit_to_worktree(worktree_a, "task-a.txt", "task-a work")
                for kind in ("qa", "review", "cso", "sync-docs"):
                    _write_verdict(repo_root, "task-a", kind)

                with patch.object(orchestrator, "_validate_after_rebase", return_value=(True, "")):
                    result_a = orchestrator._integrate_single_pr_task(
                        repo_root=repo_root,
                        task_id="task-a",
                        integration_branch="epic-01",
                        worktree_dir=worktree_a,
                        plan_file=plan_a,
                    )
                self.assertTrue(result_a)

                # Only the integration branch should be on origin; no task branch.
                remote_heads = _remote_heads(repo_root)
                self.assertIn("epic-01", remote_heads)
                self.assertNotIn("task-a", remote_heads)
                self.assertNotIn("task-b", remote_heads)

                # Origin tip should now contain task-a.
                log_a = _integration_log(repo_root, "epic-01")
                self.assertTrue(
                    any("Integrate task-a" in line for line in log_a),
                    f"expected 'Integrate task-a' in origin/epic-01 log: {log_a}",
                )

                # Task B
                worktree_b = orchestrator.create_worktree(
                    repo_root, "task-b", base_branch="origin/epic-01"
                )
                _add_commit_to_worktree(worktree_b, "task-b.txt", "task-b work")
                for kind in ("qa", "review", "cso", "sync-docs"):
                    _write_verdict(repo_root, "task-b", kind)

                with patch.object(orchestrator, "_validate_after_rebase", return_value=(True, "")):
                    result_b = orchestrator._integrate_single_pr_task(
                        repo_root=repo_root,
                        task_id="task-b",
                        integration_branch="epic-01",
                        worktree_dir=worktree_b,
                    )
                self.assertTrue(result_b)

                remote_heads = _remote_heads(repo_root)
                self.assertIn("epic-01", remote_heads)
                self.assertNotIn("task-a", remote_heads)
                self.assertNotIn("task-b", remote_heads)

                # Origin tip should now contain task-b on top of task-a.
                log_b = _integration_log(repo_root, "epic-01")
                self.assertTrue(
                    any("Integrate task-b" in line for line in log_b),
                    f"expected 'Integrate task-b' in origin/epic-01 log: {log_b}",
                )


if __name__ == "__main__":
    unittest.main()
