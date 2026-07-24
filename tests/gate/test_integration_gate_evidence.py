"""Tests for gate evidence enforcement at single-pr integration time (R-22).

Covers:
- required-stage resolution is factored into a shared helper reused by hooks.py
  and the orchestrator;
- a task missing a required gate verdict is refused at integration;
- a skipped gate key is honoured;
- pr-per-task pre-push hook enforcement is unchanged.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from aet import evidence, telemetry
from aet.cli_adapter import CLIAdapter

_ORCHESTRATOR_BIN = Path(__file__).parents[2] / "src" / "aet" / "cli" / "orchestrator.py"
_orchestrator_loader = importlib.machinery.SourceFileLoader(
    "orchestrator", str(_ORCHESTRATOR_BIN)
)
_spec = importlib.util.spec_from_loader("orchestrator", _orchestrator_loader)
orchestrator = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(orchestrator)

_HOOKS_BIN = Path(__file__).parents[2] / "src" / "aet" / "cli" / "hooks.py"
_hooks_loader = importlib.machinery.SourceFileLoader("hooks", str(_HOOKS_BIN))
_spec_hooks = importlib.util.spec_from_loader("hooks", _hooks_loader)
hooks = importlib.util.module_from_spec(_spec_hooks)
_spec_hooks.loader.exec_module(hooks)

pytestmark = pytest.mark.xdist_group("orchestrator")

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


def _write_plan(
    repo_root: str,
    task_id: str,
    *,
    security_review: str | None = None,
    docs_sync: str | None = None,
) -> str:
    plan_file = os.path.join(repo_root, "docs", "plans", f"{task_id}.md")
    Path(plan_file).parent.mkdir(parents=True, exist_ok=True)
    frontmatter: dict[str, object] = {"id": task_id}
    if security_review is not None:
        frontmatter["security_review"] = security_review
    if docs_sync is not None:
        frontmatter["docs_sync"] = docs_sync
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
    """Write a schema-valid passing verdict for the given kind."""
    project_slug = telemetry.derive_project_slug(repo_root)
    base_record = {
        "task_id": task_id,
        "stage": "qa-complete" if kind == "qa" else kind,
        "skill": f"aet-{kind}",
        "verdict": "pass",
        "summary": "fake passed",
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
    elif kind in ("review", "cso", "sync-docs"):
        record = {**base_record, "findings": []}
        if kind == "sync-docs":
            record = {**base_record, "divergences": []}
    else:
        raise ValueError(f"unknown kind: {kind}")
    evidence.write_verdict(task_id, kind, record, project_slug=project_slug)


class TestSharedGateHelper(unittest.TestCase):
    """Direct tests for the factored gate helper in aet.gate."""

    def test_required_evidence_matches_software_workflow(self):
        """All evidence-bearing stages are required when gate keys are absent."""
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root, os.path.join(repo_root, "origin.git"))
            Path(repo_root, ".agents").mkdir(parents=True, exist_ok=True)
            _write_plan(repo_root, "task-a")
            subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
            subprocess.run(
                ["git", "-C", repo_root, "commit", "-q", "-m", "add plan"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", repo_root, "update-ref", "refs/remotes/origin/main", "HEAD"],
                check=True,
            )

            plan_fm = {"id": "task-a"}
            required = orchestrator.gate.required_evidence(repo_root, plan_fm)
            kinds = [kind for _stage, kind in required]
            self.assertIn("qa", kinds)
            self.assertIn("review", kinds)
            self.assertIn("cso", kinds)
            self.assertIn("sync-docs", kinds)

    def test_required_evidence_honours_skipped_security_review(self):
        """security_review: skipped removes the cso requirement."""
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root, os.path.join(repo_root, "origin.git"))
            Path(repo_root, ".agents").mkdir(parents=True, exist_ok=True)
            _write_plan(repo_root, "task-a", security_review="skipped")
            subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
            subprocess.run(
                ["git", "-C", repo_root, "commit", "-q", "-m", "add plan"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", repo_root, "update-ref", "refs/remotes/origin/main", "HEAD"],
                check=True,
            )

            plan_fm = {"id": "task-a", "security_review": "skipped"}
            required = orchestrator.gate.required_evidence(repo_root, plan_fm)
            kinds = [kind for _stage, kind in required]
            self.assertIn("qa", kinds)
            self.assertIn("review", kinds)
            self.assertIn("sync-docs", kinds)
            self.assertNotIn("cso", kinds)

    def test_verdict_status_false_when_missing(self):
        """verdict_status returns False with a path detail when the verdict is absent."""
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root, os.path.join(repo_root, "origin.git"))
            passed, detail = orchestrator.gate.verdict_status("task-a", "qa", repo_root)
            self.assertFalse(passed)
            self.assertIn("no verdict recorded", detail)

    def test_check_task_evidence_reports_all_failures(self):
        """check_task_evidence returns every missing required verdict."""
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root, os.path.join(repo_root, "origin.git"))
            Path(repo_root, ".agents").mkdir(parents=True, exist_ok=True)
            _write_plan(repo_root, "task-a")
            subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
            subprocess.run(
                ["git", "-C", repo_root, "commit", "-q", "-m", "add plan"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", repo_root, "update-ref", "refs/remotes/origin/main", "HEAD"],
                check=True,
            )

            plan_fm = {"id": "task-a"}
            ok, failures = orchestrator.gate.check_task_evidence("task-a", plan_fm, repo_root)
            self.assertFalse(ok)
            self.assertEqual(len(failures), 4)
            self.assertTrue(all("task-a" in f for f in failures))


class TestIntegrationGateEnforcement(unittest.TestCase):
    """The orchestrator refuses to integrate a task with missing gate evidence."""

    def test_missing_qa_verdict_refused_at_integration(self):
        """R-22: task without qa verdict is not squash-merged."""
        with tempfile.TemporaryDirectory() as repo_root, tempfile.TemporaryDirectory() as origin_root:
            _init_git_repo(repo_root, origin_root)
            Path(repo_root, ".agents").mkdir(parents=True, exist_ok=True)
            Path(repo_root, ".agents", "aet-work.json").write_text(
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
            subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
            subprocess.run(
                ["git", "-C", repo_root, "commit", "-q", "-m", "add plan"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", repo_root, "update-ref", "refs/remotes/origin/main", "HEAD"],
                check=True,
            )
            _create_integration_branch(repo_root, "epic-01")

            worktree_a = orchestrator.create_worktree(
                repo_root, "task-a", base_branch="origin/epic-01"
            )
            _add_commit_to_worktree(worktree_a, "task-a.txt", "task-a work")

            with patch.object(orchestrator, "_validate_after_rebase", return_value=(True, "")):
                with self.assertRaises(orchestrator.IntegrationFailureError) as ctx:
                    orchestrator._integrate_single_pr_task(
                        repo_root=repo_root,
                        task_id="task-a",
                        integration_branch="epic-01",
                        worktree_dir=worktree_a,
                        plan_file=plan_a,
                    )
            self.assertIn("qa", str(ctx.exception).lower())

            # No integration commit should have landed on origin/epic-01.
            remote_heads = subprocess.run(
                ["git", "-C", repo_root, "ls-remote", "--heads", "origin"],
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertIn("refs/heads/epic-01", remote_heads.stdout)
            log = subprocess.run(
                ["git", "-C", repo_root, "log", "origin/epic-01", "--oneline"],
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertNotIn("Integrate task-a", log.stdout)

    def test_skipped_security_review_honoured(self):
        """R-22: security_review: skipped removes the cso requirement at integration."""
        with tempfile.TemporaryDirectory() as repo_root, tempfile.TemporaryDirectory() as origin_root:
            _init_git_repo(repo_root, origin_root)
            Path(repo_root, ".agents").mkdir(parents=True, exist_ok=True)
            Path(repo_root, ".agents", "aet-work.json").write_text(
                json.dumps(
                    {
                        "trunk_branch": "main",
                        "integration_branch": "epic-01",
                        "integration_mode": "single-pr",
                    }
                ),
                encoding="utf-8",
            )
            plan_a = _write_plan(repo_root, "task-a", security_review="skipped")
            subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
            subprocess.run(
                ["git", "-C", repo_root, "commit", "-q", "-m", "add plan"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", repo_root, "update-ref", "refs/remotes/origin/main", "HEAD"],
                check=True,
            )
            _create_integration_branch(repo_root, "epic-01")

            worktree_a = orchestrator.create_worktree(
                repo_root, "task-a", base_branch="origin/epic-01"
            )
            _add_commit_to_worktree(worktree_a, "task-a.txt", "task-a work")

            # Provide qa, review, sync-docs verdicts but not cso.
            _write_verdict(repo_root, "task-a", "qa")
            _write_verdict(repo_root, "task-a", "review")
            _write_verdict(repo_root, "task-a", "sync-docs")

            with patch.object(orchestrator, "_validate_after_rebase", return_value=(True, "")):
                result = orchestrator._integrate_single_pr_task(
                    repo_root=repo_root,
                    task_id="task-a",
                    integration_branch="epic-01",
                    worktree_dir=worktree_a,
                    plan_file=plan_a,
                )
            self.assertTrue(result)


class TestPrePushHookUnchanged(unittest.TestCase):
    """The pre-push hook still enforces gate evidence in pr-per-task mode."""

    def test_hook_refuses_task_branch_missing_qa_verdict(self):
        """R-22: pr-per-task pre-push gate still refuses missing verdicts."""
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root, os.path.join(repo_root, "origin.git"))
            Path(repo_root, ".agents").mkdir(parents=True, exist_ok=True)
            _write_plan(repo_root, "task-a")
            subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
            subprocess.run(
                ["git", "-C", repo_root, "commit", "-q", "-m", "add plan"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", repo_root, "update-ref", "refs/remotes/origin/main", "HEAD"],
                check=True,
            )

            # Create a task branch with a commit.
            subprocess.run(
                ["git", "-C", repo_root, "checkout", "-q", "-b", "task-a"],
                check=True,
            )
            Path(repo_root, "task-a.txt").write_text("work", encoding="utf-8")
            subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
            subprocess.run(
                ["git", "-C", repo_root, "commit", "-q", "-m", "task-a work"],
                check=True,
            )

            refs = "refs/heads/task-a abc1234 refs/heads/task-a 0000000000000000000000000000000000000000\n"
            args = type("Args", (), {"repo": repo_root})()
            with patch.object(sys, "stdin", io.StringIO(refs)):
                rc = hooks.cmd_check(args)
            self.assertNotEqual(rc, 0)

    def test_hook_allows_task_branch_with_all_verdicts(self):
        """R-22: pr-per-task pre-push gate passes when all required verdicts exist."""
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root, os.path.join(repo_root, "origin.git"))
            Path(repo_root, ".agents").mkdir(parents=True, exist_ok=True)
            _write_plan(repo_root, "task-a")
            subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
            subprocess.run(
                ["git", "-C", repo_root, "commit", "-q", "-m", "add plan"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", repo_root, "update-ref", "refs/remotes/origin/main", "HEAD"],
                check=True,
            )

            for kind in ("qa", "review", "cso", "sync-docs"):
                _write_verdict(repo_root, "task-a", kind)

            refs = "refs/heads/task-a abc1234 refs/heads/task-a 0000000000000000000000000000000000000000\n"
            args = type("Args", (), {"repo": repo_root})()
            with patch.object(sys, "stdin", io.StringIO(refs)):
                rc = hooks.cmd_check(args)
            self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
