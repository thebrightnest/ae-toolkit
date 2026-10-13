"""Tests for aet.integrate (unified integrate path).

Covers:
- Clean integrate: rebase, validate, squash commit on target, push, merged
- Failing pre_integration_check: stages conflict in awaiting_merge, lock never acquired
- Rebase conflict: stages conflict in awaiting_merge
- Release guard refusal: stages guard_refused in awaiting_merge
- Monolithic commit refusal: stages guard_refused in awaiting_merge
"""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pytest

from aet import integration_lock, validation
from aet.backends import create_backend
from aet.integrate import integrate
from aet.worktree import create_worktree

pytestmark = pytest.mark.xdist_group("git-repo")


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
    subprocess.run(["git", "-C", repo_root, "checkout", "-q", "-b", name], check=True)
    subprocess.run(["git", "-C", repo_root, "push", "-q", "-u", "origin", name], check=True)
    subprocess.run(
        ["git", "-C", repo_root, "update-ref", f"refs/remotes/origin/{name}", "HEAD"],
        check=True,
    )
    subprocess.run(["git", "-C", repo_root, "checkout", "-q", "main"], check=True)


def _setup_repo_and_backend(repo_root: str, origin_root: str):
    _init_git_repo(repo_root, origin_root)
    agents_dir = Path(repo_root, ".agents")
    agents_dir.mkdir(parents=True, exist_ok=True)
    (agents_dir / "aet-config.json").write_text(
        json.dumps(
            {
                "trunk_branch": "main",
                "integration_branch": "epic-01",
                "integration_mode": "single-pr",
            }
        ),
        encoding="utf-8",
    )
    queue_file = str(agents_dir / "aet-queue")
    history_file = str(agents_dir / "work-history.jsonl")
    backend = create_backend(
        config_path=str(agents_dir / "aet-config.json"),
        queue_file=queue_file,
        history_file=history_file,
    )
    _create_integration_branch(repo_root, "epic-01")
    return backend, queue_file


def _add_commit(worktree_dir: str, filename: str, content: str, msg: str = "work") -> None:
    p = Path(worktree_dir, filename)
    p.write_text(content, encoding="utf-8")
    subprocess.run(["git", "-C", worktree_dir, "add", filename], check=True)
    subprocess.run(["git", "-C", worktree_dir, "commit", "-q", "-m", msg], check=True)


class TestIntegrate(unittest.TestCase):
    def test_clean_integrate_produces_squash_commit_and_merged_status(self):
        with tempfile.TemporaryDirectory() as repo_root, tempfile.TemporaryDirectory() as origin_root:
            backend, queue_file = _setup_repo_and_backend(repo_root, origin_root)
            task_id = "task-clean"
            backend.save([{"id": task_id, "state": "in_progress", "branch": task_id}])

            wt = create_worktree(repo_root, task_id, base_branch="origin/epic-01")
            _add_commit(wt, "feature.txt", "feature content", "feat: add feature")

            skip_check = validation.CheckResult("SKIP", None, True, "")
            with patch("aet.validation.pre_integration_check", return_value=skip_check), \
                 patch("aet.gate.check_task_evidence", return_value=(True, [])):
                res = integrate(
                    repo_root=repo_root,
                    task=task_id,
                    worktree_dir=wt,
                    backend=backend,
                    integration_branch="epic-01",
                )

            self.assertEqual(res.status, "staged")
            self.assertTrue(res.ok)
            self.assertIsNotNone(res.detail)

            from aet.train import flush
            flush_res = flush(repo_root=repo_root, branch="epic-01", backend=backend)
            self.assertTrue(flush_res.ok)

            # Check that target branch has the squash commit
            log = subprocess.run(
                ["git", "-C", repo_root, "log", "origin/epic-01", "--oneline"],
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertIn(f"Integrate {task_id}", log.stdout)

            # Check queue record transitioned to merged
            task_rec = backend.read_sealed(task_id)
            if task_rec is None:
                data = backend.load()
                task_rec = next((t for t in data.get("queue", []) if t["id"] == task_id), None)
                if task_rec is None:
                    task_rec = next((t for t in data.get("history", []) if t["id"] == task_id), None)
            self.assertIsNotNone(task_rec)
            self.assertEqual(task_rec["state"], "merged")
            self.assertEqual(task_rec["merge_commit"], res.detail)

    def test_pre_integration_check_failure_stages_conflict_without_lock(self):
        with tempfile.TemporaryDirectory() as repo_root, tempfile.TemporaryDirectory() as origin_root:
            backend, queue_file = _setup_repo_and_backend(repo_root, origin_root)
            task_id = "task-precheck-fail"
            backend.save([{"id": task_id, "state": "in_progress", "branch": task_id}])

            wt = create_worktree(repo_root, task_id, base_branch="origin/epic-01")
            _add_commit(wt, "feature.txt", "broken code", "feat: broken")

            lock_acquired = False
            orig_lock = integration_lock.integration_lock

            def tracking_lock(r):
                nonlocal lock_acquired
                lock_acquired = True
                return orig_lock(r)

            fail_check = validation.CheckResult("RUN", ["make", "validate"], False, "syntax error")
            with patch("aet.validation.pre_integration_check", return_value=fail_check), \
                 patch("aet.integrate.integration_lock", side_effect=tracking_lock):
                res = integrate(
                    repo_root=repo_root,
                    task=task_id,
                    worktree_dir=wt,
                    backend=backend,
                    integration_branch="epic-01",
                )

            self.assertEqual(res.status, "staged_conflict")
            self.assertFalse(res.ok)
            self.assertFalse(lock_acquired, "Lock should NOT be acquired when pre_integration_check fails")

            data = backend.load()
            task_rec = next(t for t in data["queue"] if t["id"] == task_id)
            self.assertEqual(task_rec["state"], "awaiting_merge")
            self.assertEqual(task_rec["conflict_diagnostics"]["reason"], "validation_failure")
            self.assertIn("syntax error", task_rec["conflict_diagnostics"]["stderr_tail"])

    def test_rebase_conflict_stages_conflict(self):
        with tempfile.TemporaryDirectory() as repo_root, tempfile.TemporaryDirectory() as origin_root:
            backend, queue_file = _setup_repo_and_backend(repo_root, origin_root)
            task_id = "task-rebase-conflict"
            backend.save([{"id": task_id, "state": "in_progress", "branch": task_id}])

            # Base commit
            wt = create_worktree(repo_root, task_id, base_branch="origin/epic-01")
            _add_commit(wt, "conflict.txt", "task content", "task commit")

            # Advance epic-01 with conflicting change
            subprocess.run(["git", "-C", repo_root, "checkout", "epic-01"], check=True)
            Path(repo_root, "conflict.txt").write_text("epic content", encoding="utf-8")
            subprocess.run(["git", "-C", repo_root, "add", "conflict.txt"], check=True)
            subprocess.run(["git", "-C", repo_root, "commit", "-m", "advance epic"], check=True)
            subprocess.run(["git", "-C", repo_root, "push", "origin", "epic-01"], check=True)
            subprocess.run(["git", "-C", repo_root, "checkout", "main"], check=True)

            skip_check = validation.CheckResult("SKIP", None, True, "")
            with patch("aet.validation.pre_integration_check", return_value=skip_check):
                res = integrate(
                    repo_root=repo_root,
                    task=task_id,
                    worktree_dir=wt,
                    backend=backend,
                    integration_branch="epic-01",
                )

            self.assertEqual(res.status, "staged_conflict")
            self.assertFalse(res.ok)

            data = backend.load()
            task_rec = next(t for t in data["queue"] if t["id"] == task_id)
            self.assertEqual(task_rec["state"], "awaiting_merge")
            self.assertEqual(task_rec["conflict_diagnostics"]["reason"], "rebase_conflict")
            self.assertIn("conflict.txt", task_rec["conflict_diagnostics"]["conflicting_files"])

    def test_release_guard_refusal_stages_guard_refused(self):
        with tempfile.TemporaryDirectory() as repo_root, tempfile.TemporaryDirectory() as origin_root:
            backend, queue_file = _setup_repo_and_backend(repo_root, origin_root)
            task_id = "task-release-guard"
            backend.save([{"id": task_id, "state": "in_progress", "branch": task_id}])

            wt = create_worktree(repo_root, task_id, base_branch="origin/epic-01")
            _add_commit(wt, "VERSION", "1.2.3", "chore(release): bump version")

            skip_check = validation.CheckResult("SKIP", None, True, "")
            with patch("aet.validation.pre_integration_check", return_value=skip_check):
                res = integrate(
                    repo_root=repo_root,
                    task=task_id,
                    worktree_dir=wt,
                    backend=backend,
                    integration_branch="epic-01",
                )

            self.assertEqual(res.status, "guard_refused")
            self.assertFalse(res.ok)

            data = backend.load()
            task_rec = next(t for t in data["queue"] if t["id"] == task_id)
            self.assertEqual(task_rec["state"], "awaiting_merge")
            self.assertEqual(task_rec["conflict_diagnostics"]["reason"], "guard_refused")
            self.assertIn("Release guard", task_rec["conflict_diagnostics"]["stderr_tail"])

    def test_monolithic_commit_refusal_stages_guard_refused(self):
        with tempfile.TemporaryDirectory() as repo_root, tempfile.TemporaryDirectory() as origin_root:
            backend, queue_file = _setup_repo_and_backend(repo_root, origin_root)
            task_id = "task-monolithic"
            task_spec = {
                "tasks": ["- [ ] Task 1", "- [ ] Task 2"],
            }
            backend.save([{"id": task_id, "state": "in_progress", "branch": task_id, "spec": task_spec}])

            wt = create_worktree(repo_root, task_id, base_branch="origin/epic-01")
            _add_commit(wt, "all_work.txt", "everything", "one commit doing all")

            skip_check = validation.CheckResult("SKIP", None, True, "")
            with patch("aet.validation.pre_integration_check", return_value=skip_check):
                res = integrate(
                    repo_root=repo_root,
                    task=task_id,
                    worktree_dir=wt,
                    backend=backend,
                    integration_branch="epic-01",
                )

            self.assertEqual(res.status, "guard_refused")
            self.assertFalse(res.ok)

            data = backend.load()
            task_rec = next(t for t in data["queue"] if t["id"] == task_id)
            self.assertEqual(task_rec["state"], "awaiting_merge")
            self.assertEqual(task_rec["conflict_diagnostics"]["reason"], "guard_refused")
            self.assertIn("Monolithic commit detected", task_rec["conflict_diagnostics"]["stderr_tail"])
