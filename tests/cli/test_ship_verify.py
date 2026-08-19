"""Tests for `aet ship verify` (t2r-02)."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from aet.backends.git_refs_backend import GitRefsBackend

_SHIP_PY = Path(__file__).parents[2] / "src" / "aet" / "cli" / "ship.py"
_spec = importlib.util.spec_from_loader(
    "aet_ship_verify",
    importlib.machinery.SourceFileLoader("aet_ship_verify", str(_SHIP_PY)),
)
ship = importlib.util.module_from_spec(_spec)
sys.modules["aet_ship_verify"] = ship
_spec.loader.exec_module(ship)


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=check,
    )


def _init_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-q")
    _git(path, "config", "user.email", "test@example.com")
    _git(path, "config", "user.name", "Test User")
    (path / "base.txt").write_text("base\n", encoding="utf-8")
    (path / ".gitignore").write_text(".agents/\ndocs/plans/\n", encoding="utf-8")
    _git(path, "add", ".")
    _git(path, "commit", "-q", "-m", "initial")
    _git(path, "remote", "add", "origin", str(path))
    _git(path, "push", "-u", "origin", "main", check=False)
    return path


def _write_queue(repo: Path, task_id: str, branch: str, plan_path: Path) -> Path:
    queue_path = repo / ".agents" / "aet-queue"
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    backend = GitRefsBackend(
        queue_file=str(queue_path),
        history_file=str(repo / ".agents" / "work-history.jsonl"),
    )
    backend.save(
        [
            {
                "id": task_id,
                "state": "awaiting_merge",
                "stage": "qa-complete",
                "branch": branch,
                "plan_file": str(plan_path),
            }
        ]
    )
    return queue_path


def _write_plan(repo: Path, task_id: str) -> Path:
    plan_dir = repo / "docs" / "plans"
    plan_dir.mkdir(parents=True, exist_ok=True)
    plan_path = plan_dir / f"{task_id}.md"
    plan_path.write_text(
        f"---\n"
        f"id: {task_id}\n"
        f"size: M\n"
        f"---\n\n"
        f"# Plan {task_id}\n\n"
        f"---\n\n"
        f"*Stage: awaiting_merge*\n",
        encoding="utf-8",
    )
    return plan_path


class TestShipVerify(unittest.TestCase):
    """Behavior-driven tests for `aet ship verify`."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.repo = _init_repo(Path(self.tmpdir.name) / "repo")
        self.plan_path = _write_plan(self.repo, "t1")
        self.queue_path = _write_queue(self.repo, "t1", "t1", self.plan_path)
        self.cwd = os.getcwd()
        self.addCleanup(os.chdir, self.cwd)
        os.chdir(self.repo)

    def _branch(self, name: str, filename: str, content: str) -> None:
        _git(self.repo, "checkout", "-q", "-b", name)
        (self.repo / filename).write_text(content, encoding="utf-8")
        _git(self.repo, "add", filename)
        _git(self.repo, "commit", "-q", "-m", f"feat({name}): implement")

    def _squash_merge(self, branch: str, message: str) -> str:
        _git(self.repo, "checkout", "-q", "main")
        _git(self.repo, "merge", "--squash", branch)
        _git(self.repo, "add", ".")
        _git(self.repo, "commit", "-q", "-m", message)
        _git(self.repo, "push", "origin", "main", check=False)
        return _git(self.repo, "rev-parse", "HEAD").stdout.strip()

    def _run_verify(self, argv: list[str]) -> tuple[int, str, str]:
        """Run `ship.main(argv)` with gh patched to fail, capturing output."""
        with patch.object(ship.aet_state, "run_gh", return_value=(1, "", "")):
            with patch.object(sys, "argv", argv):
                stdout_capture = StringIO()
                stderr_capture = StringIO()
                with patch.object(sys, "stdout", stdout_capture):
                    with patch.object(sys, "stderr", stderr_capture):
                        rc = ship.main()
                return rc, stdout_capture.getvalue(), stderr_capture.getvalue()

    def test_verify_squash_merged_branch_reports_squash_and_exact_kind(self):
        """A squash-merged branch resolves with strategy squash and match kind exact."""
        self._branch("t1", "feat.txt", "feature\n")
        sha = self._squash_merge("t1", "feat: implement")

        rc, out, err = self._run_verify(
            ["ship", "verify", "t1", "--squash-fallback"]
        )

        self.assertEqual(rc, 0)
        self.assertIn(sha, out)
        self.assertIn("squash", out)
        self.assertIn("exact", out)

    def test_verify_squash_merged_branch_reports_squash_and_drift_kind(self):
        """An amended squash merge resolves as squash/drift."""
        self._branch("t1", "feat.txt", "line one\nline two\nline three\n")
        _git(self.repo, "checkout", "-q", "main")
        _git(self.repo, "merge", "--squash", "t1")
        (self.repo / "feat.txt").write_text(
            "line one\nline two amended\nline three\n", encoding="utf-8"
        )
        _git(self.repo, "add", "feat.txt")
        _git(self.repo, "commit", "-q", "-m", "feat: implement")
        _git(self.repo, "push", "origin", "main", check=False)
        sha = _git(self.repo, "rev-parse", "HEAD").stdout.strip()

        rc, out, err = self._run_verify(
            ["ship", "verify", "t1", "--squash-fallback"]
        )

        self.assertEqual(rc, 0)
        self.assertIn(sha, out)
        self.assertIn("squash", out)
        self.assertIn("drift", out)

    def test_verify_unmerged_branch_exits_no_match(self):
        """A branch that has not merged exits EXIT_VERIFY_NO_MATCH."""
        self._branch("t1", "feat.txt", "feature\n")

        rc, out, err = self._run_verify(["ship", "verify", "t1", "--squash-fallback"])

        self.assertEqual(rc, ship.EXIT_VERIFY_NO_MATCH)

    def test_verify_empty_branch_diff_exits_ambiguous(self):
        """A branch with an empty diff exits EXIT_VERIFY_AMBIGUOUS."""
        _git(self.repo, "checkout", "-q", "-b", "t1")
        _git(self.repo, "commit", "-q", "--allow-empty", "-m", "empty commit")

        rc, out, err = self._run_verify(["ship", "verify", "t1", "--squash-fallback"])

        self.assertEqual(rc, ship.EXIT_VERIFY_AMBIGUOUS)

    def test_verify_does_not_mutate_queue_ledger_or_footer(self):
        """Verification is read-only: queue, ledger, and plan footer are untouched."""
        self._branch("t1", "feat.txt", "feature\n")
        self._squash_merge("t1", "feat: implement")

        original_queue = GitRefsBackend(
            queue_file=str(self.queue_path),
            history_file=str(self.repo / ".agents" / "work-history.jsonl"),
        ).load()["queue"]
        original_plan = self.plan_path.read_text(encoding="utf-8")
        ledger_path = self.repo / ".agents" / "ledger.jsonl"

        self._run_verify(["ship", "verify", "t1", "--squash-fallback"])

        final_queue = GitRefsBackend(
            queue_file=str(self.queue_path),
            history_file=str(self.repo / ".agents" / "work-history.jsonl"),
        ).load()["queue"]
        self.assertEqual(final_queue, original_queue)
        self.assertEqual(self.plan_path.read_text(encoding="utf-8"), original_plan)
        self.assertFalse(ledger_path.exists())

    def test_verify_accepts_plan_path(self):
        """`aet ship verify <plan>` derives the task id from the plan."""
        self._branch("t1", "feat.txt", "feature\n")
        sha = self._squash_merge("t1", "feat: implement")

        rc, out, err = self._run_verify(
            ["ship", "verify", str(self.plan_path), "--squash-fallback"]
        )

        self.assertEqual(rc, 0)
        self.assertIn(sha, out)


class TestShipVerifySinglePr(unittest.TestCase):
    """R-17: ship verify resolves the target branch from the task's PRD."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.repo = Path(self.tmpdir.name) / "repo"
        self.repo.mkdir(parents=True, exist_ok=True)
        self.cwd = os.getcwd()
        self.addCleanup(os.chdir, self.cwd)
        os.chdir(self.repo)

        self._git("init", "-q")
        self._git("config", "user.email", "test@example.com")
        self._git("config", "user.name", "Test User")
        (self.repo / "base.txt").write_text("base\n", encoding="utf-8")
        (self.repo / ".gitignore").write_text(
            ".agents/\ndocs/plans/\n", encoding="utf-8"
        )
        self._git("add", ".")
        self._git("commit", "-q", "-m", "initial")

        config = self.repo / ".agents" / "aet-config.json"
        config.parent.mkdir(parents=True, exist_ok=True)
        config.write_text(
            json.dumps({"trunk_branch": "main", "integration_mode": "single-pr"}),
            encoding="utf-8",
        )
        self._git("remote", "add", "origin", str(self.repo))
        self._git("push", "-u", "origin", "main", check=False)

        self.plan_path = self._write_plan("t1")
        self.queue_path = self._write_queue("t1", "t1", self.plan_path)

    def _git(self, *args: str, check: bool = True) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", "-C", str(self.repo), *args],
            capture_output=True,
            text=True,
            check=check,
        )

    def _write_plan(self, task_id: str) -> Path:
        prd = self.repo / "docs" / "prds" / "alpha-prd.md"
        prd.parent.mkdir(parents=True, exist_ok=True)
        prd.write_text("# Alpha\n\nRequirement: R-17\n", encoding="utf-8")
        plan_path = self.repo / "docs" / "plans" / f"{task_id}.md"
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        plan_path.write_text(
            f"---\n"
            f"id: {task_id}\n"
            f"size: M\n"
            f"---\n\n"
            f"# Plan {task_id}\n\n"
            f"- PRD: `docs/prds/alpha-prd.md`\n\n"
            f"---\n\n"
            f"*Stage: awaiting_merge*\n",
            encoding="utf-8",
        )
        self._git("add", ".")
        self._git("commit", "-q", "-m", "add plan")
        self._git("push", "origin", "main", check=False)
        return plan_path

    def _write_queue(self, task_id: str, branch: str, plan_path: Path) -> Path:
        queue_path = self.repo / ".agents" / "aet-queue"
        queue_path.parent.mkdir(parents=True, exist_ok=True)
        GitRefsBackend(
            queue_file=str(queue_path),
            history_file=str(self.repo / ".agents" / "work-history.jsonl"),
        ).save(
            [
                {
                    "id": task_id,
                    "state": "awaiting_merge",
                    "stage": "qa-complete",
                    "branch": branch,
                    "plan_file": str(plan_path),
                }
            ]
        )
        return queue_path

    def _branch(self, name: str, filename: str, content: str) -> None:
        self._git("checkout", "-q", "-b", name)
        (self.repo / filename).write_text(content, encoding="utf-8")
        self._git("add", filename)
        self._git("commit", "-q", "-m", f"feat({name})")

    def _squash_merge_to_alpha(self, branch: str, message: str) -> str:
        self._git("checkout", "-q", "alpha-prd")
        self._git("merge", "--squash", branch)
        self._git("add", ".")
        self._git("commit", "-q", "-m", message)
        self._git("push", "origin", "alpha-prd", check=False)
        return self._git("rev-parse", "HEAD").stdout.strip()

    def _run_verify(self, argv: list[str]) -> tuple[int, str, str]:
        with patch.object(ship.aet_state, "run_gh", return_value=(1, "", "")):
            with patch.object(sys, "argv", argv):
                stdout_capture = StringIO()
                stderr_capture = StringIO()
                with patch.object(sys, "stdout", stdout_capture):
                    with patch.object(sys, "stderr", stderr_capture):
                        rc = ship.main()
                return rc, stdout_capture.getvalue(), stderr_capture.getvalue()

    def test_verify_resolves_prd_derived_target_branch(self):
        """ship verify checks origin/<prd-stem> when no --target-branch is given."""
        self._git("checkout", "-q", "-b", "alpha-prd")
        self._git("push", "-u", "origin", "alpha-prd", check=False)
        self._git("checkout", "-q", "main")
        self._branch("t1", "feat.txt", "feature\n")
        sha = self._squash_merge_to_alpha("t1", "feat: implement")

        rc, out, err = self._run_verify(["ship", "verify", "t1", "--squash-fallback"])

        self.assertEqual(rc, 0)
        self.assertIn(sha, out)


if __name__ == "__main__":
    unittest.main()
