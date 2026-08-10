"""Unit tests for squash-merge diff fallback (t2r-02)."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_AET_STATE_PY = Path(__file__).parents[2] / "src" / "aet" / "cli" / "aet_state.py"
_spec = importlib.util.spec_from_loader(
    "aet_state_squash",
    importlib.machinery.SourceFileLoader("aet_state_squash", str(_AET_STATE_PY)),
)
aet_state = importlib.util.module_from_spec(_spec)
sys.modules["aet_state_squash"] = aet_state
_spec.loader.exec_module(aet_state)


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
    _git(path, "add", ".")
    _git(path, "commit", "-q", "-m", "initial")
    _git(path, "remote", "add", "origin", str(path))
    _git(path, "push", "-u", "origin", "main", check=False)
    return path


class TestResolveByDiff(unittest.TestCase):
    """Behavior-driven tests for the diff-based squash merge fallback."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.repo = _init_repo(Path(self.tmpdir.name) / "repo")
        self.cwd = os.getcwd()
        self.addCleanup(os.chdir, self.cwd)
        os.chdir(self.repo)

    def _branch(self, name: str, filename: str, content: str) -> None:
        _git(self.repo, "checkout", "-q", "-b", name)
        (self.repo / filename).write_text(content, encoding="utf-8")
        _git(self.repo, "add", filename)
        _git(self.repo, "commit", "-q", "-m", f"feat({name}): implement")

    def _squash_commit(self, branch: str, message: str) -> str:
        _git(self.repo, "checkout", "-q", "main")
        _git(self.repo, "merge", "--squash", branch)
        _git(self.repo, "add", ".")
        _git(self.repo, "commit", "-q", "-m", message)
        _git(self.repo, "push", "origin", "main", check=False)
        return _git(self.repo, "rev-parse", "HEAD").stdout.strip()

    def test_exact_match_returns_exact_kind(self):
        """An unchanged squash commit matches exactly."""
        self._branch("feat", "feat.txt", "feature\n")
        sha = self._squash_commit("feat", "feat: implement")
        _git(self.repo, "checkout", "-q", "feat")

        result, kind = aet_state.resolve_by_diff("feat", cwd=self.repo, trunk_branch="main")

        self.assertEqual(result, sha)
        self.assertEqual(kind, "exact")

    def test_drift_match_accepted_within_threshold(self):
        """A squash commit amended by one line is accepted as a drift match."""
        self._branch("feat", "feat.txt", "line one\nline two\nline three\n")
        _git(self.repo, "checkout", "-q", "main")
        _git(self.repo, "merge", "--squash", "feat")
        (self.repo / "feat.txt").write_text(
            "line one\nline two amended\nline three\n", encoding="utf-8"
        )
        _git(self.repo, "add", "feat.txt")
        _git(self.repo, "commit", "-q", "-m", "feat: implement")
        _git(self.repo, "push", "origin", "main", check=False)
        sha = _git(self.repo, "rev-parse", "HEAD").stdout.strip()
        _git(self.repo, "checkout", "-q", "feat")

        result, kind = aet_state.resolve_by_diff("feat", cwd=self.repo, trunk_branch="main")

        self.assertEqual(result, sha)
        self.assertEqual(kind, "drift")

    def test_large_drift_rejected(self):
        """A squash commit amended by more than 20 changed lines is rejected."""
        original_lines = [f"line {i}\n" for i in range(40)]
        amended_lines = [f"line {i}\n" for i in range(25)] + [
            f"amended {i}\n" for i in range(20)
        ]
        self._branch("feat", "feat.txt", "".join(original_lines))
        _git(self.repo, "checkout", "-q", "main")
        _git(self.repo, "merge", "--squash", "feat")
        (self.repo / "feat.txt").write_text("".join(amended_lines), encoding="utf-8")
        _git(self.repo, "add", "feat.txt")
        _git(self.repo, "commit", "-q", "-m", "feat: implement")
        _git(self.repo, "push", "origin", "main", check=False)
        _git(self.repo, "checkout", "-q", "feat")

        result, kind = aet_state.resolve_by_diff("feat", cwd=self.repo, trunk_branch="main")

        self.assertIsNone(result)
        self.assertIsNone(kind)

    def test_exact_match_preferred_over_drift(self):
        """When both exact and drift candidates exist, exact wins."""
        self._branch("feat", "feat.txt", "feature\n")
        exact_sha = self._squash_commit("feat", "feat: implement exact")
        # Create a second commit on main with a drifted version of the same diff.
        (self.repo / "feat.txt").write_text("feature amended\n", encoding="utf-8")
        _git(self.repo, "add", "feat.txt")
        _git(self.repo, "commit", "-q", "-m", "feat: implement drift")
        _git(self.repo, "push", "origin", "main", check=False)
        _git(self.repo, "checkout", "-q", "feat")

        result, kind = aet_state.resolve_by_diff("feat", cwd=self.repo, trunk_branch="main")

        self.assertEqual(result, exact_sha)
        self.assertEqual(kind, "exact")

    def test_multiple_drift_candidates_are_ambiguous(self):
        """More than one drift candidate within the window is ambiguous."""
        self._branch("feat", "feat.txt", "feature\n")
        _git(self.repo, "checkout", "-q", "main")
        _git(self.repo, "merge", "--squash", "feat")
        # First drift candidate.
        (self.repo / "feat.txt").write_text("feature drift-a\n", encoding="utf-8")
        _git(self.repo, "add", "feat.txt")
        _git(self.repo, "commit", "-q", "-m", "feat: drift a")
        # Second drift candidate.
        (self.repo / "feat.txt").write_text("feature drift-b\n", encoding="utf-8")
        _git(self.repo, "add", "feat.txt")
        _git(self.repo, "commit", "-q", "-m", "feat: drift b")
        _git(self.repo, "push", "origin", "main", check=False)
        _git(self.repo, "checkout", "-q", "feat")

        result, kind = aet_state.resolve_by_diff("feat", cwd=self.repo, trunk_branch="main")

        self.assertIsNone(result)
        self.assertEqual(kind, "ambiguous")

    def test_empty_branch_diff_is_ambiguous(self):
        """A branch whose diff is empty cannot be matched unambiguously."""
        _git(self.repo, "checkout", "-q", "-b", "feat")
        _git(self.repo, "commit", "-q", "--allow-empty", "-m", "empty commit")

        result, kind = aet_state.resolve_by_diff("feat", cwd=self.repo, trunk_branch="main")

        self.assertIsNone(result)
        self.assertEqual(kind, "ambiguous")

    def test_search_window_capped_at_max_commits(self):
        """A match beyond max_commits is not considered."""
        self._branch("feat", "feat.txt", "feature\n")
        # Create 10 noise commits before the squash and 10 after so the squash
        # sits at position 11 from HEAD: inside the default window but outside
        # a window of 10.
        _git(self.repo, "checkout", "-q", "main")
        for i in range(10):
            (self.repo / f"noise-before-{i}.txt").write_text(f"noise {i}\n", encoding="utf-8")
            _git(self.repo, "add", f"noise-before-{i}.txt")
            _git(self.repo, "commit", "-q", "-m", f"noise before {i}")
        _git(self.repo, "push", "origin", "main", check=False)
        sha = self._squash_commit("feat", "feat: implement")
        for i in range(10):
            # Make each noise file large enough that it does not accidentally
            # qualify as a drift match for the one-line feature diff.
            content = "\n".join(f"noise after {i} line {j}" for j in range(30)) + "\n"
            (self.repo / f"noise-after-{i}.txt").write_text(content, encoding="utf-8")
            _git(self.repo, "add", f"noise-after-{i}.txt")
            _git(self.repo, "commit", "-q", "-m", f"noise after {i}")
        _git(self.repo, "push", "origin", "main", check=False)
        _git(self.repo, "checkout", "-q", "feat")

        result, kind = aet_state.resolve_by_diff(
            "feat", cwd=self.repo, trunk_branch="main", max_commits=20
        )

        self.assertEqual(result, sha)
        self.assertEqual(kind, "exact")

        # With a window of 10 the commit is out of reach.
        result, kind = aet_state.resolve_by_diff(
            "feat", cwd=self.repo, trunk_branch="main", max_commits=10
        )
        self.assertIsNone(result)
        self.assertIsNone(kind)


class TestResolveMergeCommit(unittest.TestCase):
    """Integration of the resolution ladder with real git history."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.repo = _init_repo(Path(self.tmpdir.name) / "repo")
        self.cwd = os.getcwd()
        self.addCleanup(os.chdir, self.cwd)
        os.chdir(self.repo)

    def _branch(self, name: str, filename: str, content: str) -> None:
        _git(self.repo, "checkout", "-q", "-b", name)
        (self.repo / filename).write_text(content, encoding="utf-8")
        _git(self.repo, "add", filename)
        _git(self.repo, "commit", "-q", "-m", f"feat({name}): implement")

    def test_regular_merge_reports_ancestry(self):
        """A branch merged with --no-ff resolves as regular/ancestry."""
        self._branch("feat", "feat.txt", "feature\n")
        tip = _git(self.repo, "rev-parse", "HEAD").stdout.strip()
        _git(self.repo, "checkout", "-q", "main")
        _git(self.repo, "merge", "-q", "--no-ff", "feat", "-m", "Merge feat")
        _git(self.repo, "push", "origin", "main", check=False)

        merge_commit, strategy, kind = aet_state.resolve_merge_commit(
            "feat", cwd=self.repo, trunk_branch="main"
        )

        self.assertEqual(merge_commit, tip)
        self.assertEqual(strategy, "regular")
        self.assertEqual(kind, "ancestry")

    def test_squash_merge_reports_exact_kind(self):
        """A clean squash merge resolves as squash/exact."""
        self._branch("feat", "feat.txt", "feature\n")
        _git(self.repo, "checkout", "-q", "main")
        _git(self.repo, "merge", "--squash", "feat")
        _git(self.repo, "add", ".")
        _git(self.repo, "commit", "-q", "-m", "feat: implement")
        _git(self.repo, "push", "origin", "main", check=False)
        sha = _git(self.repo, "rev-parse", "HEAD").stdout.strip()
        _git(self.repo, "checkout", "-q", "feat")

        merge_commit, strategy, kind = aet_state.resolve_merge_commit(
            "feat", cwd=self.repo, trunk_branch="main"
        )

        self.assertEqual(merge_commit, sha)
        self.assertEqual(strategy, "squash")
        self.assertEqual(kind, "exact")

    def test_unmerged_branch_reports_no_match(self):
        """A branch that never merged returns no match."""
        self._branch("feat", "feat.txt", "feature\n")

        merge_commit, strategy, kind = aet_state.resolve_merge_commit(
            "feat", cwd=self.repo, trunk_branch="main"
        )

        self.assertIsNone(merge_commit)
        self.assertIsNone(strategy)
        self.assertIsNone(kind)


if __name__ == "__main__":
    unittest.main()
