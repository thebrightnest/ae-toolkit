"""Tests for working-tree fingerprinting and validation freshness.

A passing verdict stamps the tree it attests to (``tree_hash``); a later stage
asks :func:`evidence.validation_freshness` whether the tree has moved since,
and skips, lint-onlys, or re-runs accordingly.
"""

from __future__ import annotations

import contextlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from aet import evidence, verifier

_EVIDENCE_ENV_VARS = (
    "AET_EVIDENCE_PATH",
    "AET_EVIDENCE_PATH_QA",
    "AET_EVIDENCE_PATH_REVIEW",
    "AET_EVIDENCE_PATH_CSO",
    "AET_EVIDENCE_PATH_SYNC_DOCS",
    "AET_REPORTS_DIR",
    "AET_REPO_ROOT",
)


@contextlib.contextmanager
def _clean_evidence_env():
    """Drop env overrides so verdict paths resolve from explicit args only."""
    with patch.dict(os.environ, {}, clear=False):
        for var in _EVIDENCE_ENV_VARS:
            os.environ.pop(var, None)
        yield


def _init_repo(path: str) -> None:
    subprocess.run(["git", "init", "-q", path], check=True)
    subprocess.run(["git", "-C", path, "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", path, "config", "user.name", "t"], check=True)


def _commit_all(path: str, msg: str = "c") -> None:
    subprocess.run(["git", "-C", path, "add", "-A"], check=True)
    subprocess.run(["git", "-C", path, "commit", "-q", "-m", msg], check=True)


def _write(repo: str, rel: str, text: str) -> None:
    target = Path(repo) / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


class TestWorkingTreeHash(unittest.TestCase):
    def test_hash_is_nonempty_and_stable(self):
        with tempfile.TemporaryDirectory() as repo:
            _init_repo(repo)
            _write(repo, "src.py", "x = 1\n")
            _commit_all(repo)
            h1 = verifier.working_tree_hash(repo)
            self.assertTrue(h1)
            self.assertEqual(h1, verifier.working_tree_hash(repo))

    def test_hash_changes_with_content(self):
        with tempfile.TemporaryDirectory() as repo:
            _init_repo(repo)
            _write(repo, "src.py", "x = 1\n")
            _commit_all(repo)
            before = verifier.working_tree_hash(repo)
            _write(repo, "src.py", "x = 2\n")
            self.assertNotEqual(before, verifier.working_tree_hash(repo))

    def test_hash_reflects_uncommitted_new_file(self):
        with tempfile.TemporaryDirectory() as repo:
            _init_repo(repo)
            _write(repo, "src.py", "x = 1\n")
            _commit_all(repo)
            committed = verifier.working_tree_hash(repo)
            _write(repo, "extra.py", "y = 2\n")  # untracked, not committed
            self.assertNotEqual(committed, verifier.working_tree_hash(repo))

    def test_non_git_dir_returns_empty(self):
        with tempfile.TemporaryDirectory() as plain:
            self.assertEqual(verifier.working_tree_hash(plain), "")

    def test_missing_dir_returns_empty(self):
        self.assertEqual(verifier.working_tree_hash("/no/such/dir"), "")


class TestChangedPaths(unittest.TestCase):
    def test_lists_the_changed_path(self):
        with tempfile.TemporaryDirectory() as repo:
            _init_repo(repo)
            _write(repo, "src.py", "x = 1\n")
            _commit_all(repo)
            base = verifier.working_tree_hash(repo)
            _write(repo, "docs/notes.md", "hi\n")
            head = verifier.working_tree_hash(repo)
            self.assertEqual(verifier.changed_paths(repo, base, head), ["docs/notes.md"])

    def test_bad_tree_id_returns_none(self):
        with tempfile.TemporaryDirectory() as repo:
            _init_repo(repo)
            _write(repo, "src.py", "x = 1\n")
            _commit_all(repo)
            head = verifier.working_tree_hash(repo)
            self.assertIsNone(verifier.changed_paths(repo, "0" * 40, head))

    def test_empty_hash_returns_none(self):
        self.assertIsNone(verifier.changed_paths("/tmp", "", "abc"))


class TestDefaultIsCodePath(unittest.TestCase):
    def test_docs_and_markdown_are_not_code(self):
        self.assertFalse(evidence.default_is_code_path("docs/plans/x.md"))
        self.assertFalse(evidence.default_is_code_path("README.md"))
        self.assertFalse(evidence.default_is_code_path(".agents/learnings.jsonl"))

    def test_source_and_config_are_code(self):
        self.assertTrue(evidence.default_is_code_path("src/aet/evidence.py"))
        self.assertTrue(evidence.default_is_code_path("tests/test_x.py"))
        self.assertTrue(evidence.default_is_code_path("Makefile"))


class TestValidationFreshness(unittest.TestCase):
    def _repo_and_reports(self, stack: contextlib.ExitStack):
        repo = stack.enter_context(tempfile.TemporaryDirectory())
        reports = stack.enter_context(tempfile.TemporaryDirectory())
        _init_repo(repo)
        _write(repo, "src.py", "x = 1\n")
        _commit_all(repo)
        return repo, reports

    def _write_passing_qa(self, repo: str, reports: str):
        return evidence.write_verdict(
            task_id="demo",
            kind="qa",
            record={
                "task_id": "demo",
                "stage": "qa-complete",
                "skill": "aet-qa",
                "verdict": "pass",
                "summary": "green",
                "generated_at": "2026-07-13T00:00:00Z",
                "test_command": "make validate",
                "tests_total": 1,
                "tests_passed": 1,
                "tests_failed": 0,
            },
            project_slug="demo/project",
            reports_root=reports,
            worktree_dir=repo,
        )

    def _freshness(self, repo: str, reports: str):
        return evidence.validation_freshness(
            "demo", "qa", worktree_dir=repo,
            project_slug="demo/project", reports_root=reports,
        )

    def test_no_prior_verdict_runs(self):
        with contextlib.ExitStack() as stack, _clean_evidence_env():
            repo, reports = self._repo_and_reports(stack)
            result = self._freshness(repo, reports)
            self.assertEqual(result.decision, evidence.RUN)

    def test_unchanged_tree_skips(self):
        with contextlib.ExitStack() as stack, _clean_evidence_env():
            repo, reports = self._repo_and_reports(stack)
            self._write_passing_qa(repo, reports)
            result = self._freshness(repo, reports)
            self.assertEqual(result.decision, evidence.SKIP)
            self.assertEqual(result.prior_hash, result.current_hash)

    def test_docs_only_change_is_lint_only(self):
        with contextlib.ExitStack() as stack, _clean_evidence_env():
            repo, reports = self._repo_and_reports(stack)
            self._write_passing_qa(repo, reports)
            _write(repo, "docs/plans/demo.md", "*Stage: reviewed*\n")
            result = self._freshness(repo, reports)
            self.assertEqual(result.decision, evidence.LINT_ONLY)
            self.assertIn("docs/plans/demo.md", result.changed_paths)

    def test_code_change_runs(self):
        with contextlib.ExitStack() as stack, _clean_evidence_env():
            repo, reports = self._repo_and_reports(stack)
            self._write_passing_qa(repo, reports)
            _write(repo, "src.py", "x = 2\n")
            result = self._freshness(repo, reports)
            self.assertEqual(result.decision, evidence.RUN)
            self.assertIn("src.py", result.changed_paths)

    def test_mixed_change_runs(self):
        # Docs churn alongside a code edit must not downgrade to lint-only.
        with contextlib.ExitStack() as stack, _clean_evidence_env():
            repo, reports = self._repo_and_reports(stack)
            self._write_passing_qa(repo, reports)
            _write(repo, "docs/plans/demo.md", "footer\n")
            _write(repo, "src.py", "x = 3\n")
            result = self._freshness(repo, reports)
            self.assertEqual(result.decision, evidence.RUN)

    def test_prior_fail_runs(self):
        with contextlib.ExitStack() as stack, _clean_evidence_env():
            repo, reports = self._repo_and_reports(stack)
            evidence.write_verdict(
                task_id="demo",
                kind="qa",
                record={
                    "task_id": "demo",
                    "stage": "qa-complete",
                    "skill": "aet-qa",
                    "verdict": "fail",
                    "summary": "red",
                    "generated_at": "2026-07-13T00:00:00Z",
                    "test_command": "make validate",
                    "tests_total": 1,
                    "tests_passed": 0,
                    "tests_failed": 1,
                },
                project_slug="demo/project",
                reports_root=reports,
                worktree_dir=repo,
            )
            self.assertEqual(self._freshness(repo, reports).decision, evidence.RUN)

    def test_prior_pass_without_tree_hash_runs(self):
        # A verdict predating the tree_hash field can't vouch for any tree.
        with contextlib.ExitStack() as stack, _clean_evidence_env():
            repo, reports = self._repo_and_reports(stack)
            path = evidence.evidence_path(
                task_id="demo", kind="qa",
                project_slug="demo/project", reports_root=reports,
            )
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"verdict": "pass"}), encoding="utf-8")
            self.assertEqual(self._freshness(repo, reports).decision, evidence.RUN)


if __name__ == "__main__":
    unittest.main()
