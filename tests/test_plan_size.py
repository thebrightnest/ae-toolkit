"""Tests for aet.plan_size delivered diff measurement."""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from aet.plan_size import PLANNING_ARTIFACT_PATHS, delivered_size


def _init_repo(repo_root: str) -> None:
    """Initialize a git repo with a clean main branch."""
    subprocess.run(["git", "init", "-q", repo_root], check=True)
    subprocess.run(
        ["git", "-C", repo_root, "config", "user.email", "test@example.com"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", repo_root, "config", "user.name", "Test User"],
        check=True,
    )
    Path(repo_root, "README.md").write_text("# test\n", encoding="utf-8")
    subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
    subprocess.run(
        ["git", "-C", repo_root, "commit", "-q", "-m", "initial"],
        check=True,
    )
    subprocess.run(["git", "-C", repo_root, "branch", "-M", "main"], check=True)


def _commit(repo_root: str, path: str, content: str, message: str) -> None:
    """Write ``content`` to ``path`` and commit it."""
    target = Path(repo_root, path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    subprocess.run(["git", "-C", repo_root, "add", path], check=True)
    subprocess.run(
        ["git", "-C", repo_root, "commit", "-q", "-m", message],
        check=True,
    )


class TestDeliveredSize(unittest.TestCase):
    def test_regular_merge_first_parent_is_trunk(self):
        """For a regular merge, ^1 is the trunk side and ^2 is the branch."""
        with tempfile.TemporaryDirectory() as repo_root:
            _init_repo(repo_root)
            _commit(repo_root, "src/feature.py", "line1\nline2\n", "add feature")
            subprocess.run(
                ["git", "-C", repo_root, "checkout", "-b", "feature"],
                check=True,
                capture_output=True,
            )
            _commit(repo_root, "src/feature.py", "line1\nline2\nline3\n", "extend feature")
            _commit(repo_root, "docs/feature.md", "a\nb\n", "add doc")
            subprocess.run(
                ["git", "-C", repo_root, "checkout", "main"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", repo_root, "merge", "--no-ff", "-m", "merge feature", "feature"],
                check=True,
                capture_output=True,
            )

            merge_commit = subprocess.run(
                ["git", "-C", repo_root, "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()

            result = delivered_size(repo_root, merge_commit)

            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["reason"], None)
            # The merge commit itself is one line; branch contributed 1 code line + 2 doc lines.
            self.assertEqual(result["total"], 3)
            self.assertEqual(result["headline"], 1)

    def test_squash_merge_first_parent_range(self):
        """A squash merge yields a single-parent commit; its range is the squashed diff."""
        with tempfile.TemporaryDirectory() as repo_root:
            _init_repo(repo_root)
            subprocess.run(
                ["git", "-C", repo_root, "checkout", "-b", "feature"],
                check=True,
                capture_output=True,
            )
            _commit(repo_root, "src/a.py", "one\ntwo\nthree\n", "code")
            _commit(repo_root, "docs/a.md", "x\ny\n", "doc")
            subprocess.run(
                ["git", "-C", repo_root, "checkout", "main"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", repo_root, "merge", "--squash", "feature"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", repo_root, "commit", "-q", "-m", "squash feature"],
                check=True,
                capture_output=True,
            )

            merge_commit = subprocess.run(
                ["git", "-C", repo_root, "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()

            result = delivered_size(repo_root, merge_commit)

            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["total"], 5)
            self.assertEqual(result["headline"], 3)

    def test_exclusion_split_ignores_planning_artifacts(self):
        """Headline excludes the planning-artifact directories."""
        with tempfile.TemporaryDirectory() as repo_root:
            _init_repo(repo_root)
            subprocess.run(
                ["git", "-C", repo_root, "checkout", "-b", "feature"],
                check=True,
                capture_output=True,
            )
            _commit(repo_root, "src/code.py", "a\nb\n", "code")
            _commit(repo_root, "docs/doc.md", "c\nd\ne\n", "doc")
            _commit(repo_root, ".agents/notes.md", "f\n", "agent note")
            _commit(repo_root, "content/note.md", "g\nh\n", "content")
            _commit(repo_root, "reports/retro.md", "i\n", "report")
            subprocess.run(
                ["git", "-C", repo_root, "checkout", "main"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", repo_root, "merge", "--squash", "feature"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", repo_root, "commit", "-q", "-m", "squash"],
                check=True,
                capture_output=True,
            )

            merge_commit = subprocess.run(
                ["git", "-C", repo_root, "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()

            result = delivered_size(repo_root, merge_commit)

            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["total"], 9)
            self.assertEqual(result["headline"], 2)

    def test_missing_merge_commit(self):
        """A missing merge_commit records a failure reason instead of raising."""
        with tempfile.TemporaryDirectory() as repo_root:
            _init_repo(repo_root)
            result = delivered_size(repo_root, None)
            self.assertEqual(result["status"], "failed")
            self.assertIn("merge_commit", result["reason"].lower())
            self.assertIsNone(result["headline"])
            self.assertIsNone(result["total"])

    def test_root_commit_has_no_first_parent(self):
        """A root commit cannot be measured because it has no ^1."""
        with tempfile.TemporaryDirectory() as repo_root:
            _init_repo(repo_root)
            root = subprocess.run(
                ["git", "-C", repo_root, "rev-list", "--max-parents=0", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            result = delivered_size(repo_root, root)
            self.assertEqual(result["status"], "failed")
            self.assertIn("first parent", result["reason"].lower())

    def test_invalid_commit_records_git_failure(self):
        """An invalid sha records the git failure reason."""
        with tempfile.TemporaryDirectory() as repo_root:
            _init_repo(repo_root)
            result = delivered_size(repo_root, "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef")
            self.assertEqual(result["status"], "failed")
            self.assertIn("first parent", result["reason"].lower())

    def test_binary_file_counts_as_zero_lines(self):
        """Binary files appear as '-' in numstat and are counted as zero lines."""
        with tempfile.TemporaryDirectory() as repo_root:
            _init_repo(repo_root)
            subprocess.run(
                ["git", "-C", repo_root, "checkout", "-b", "feature"],
                check=True,
                capture_output=True,
            )
            _commit(repo_root, "src/code.py", "a\nb\n", "code")
            binary = Path(repo_root, "assets/blob.bin")
            binary.parent.mkdir(parents=True, exist_ok=True)
            binary.write_bytes(b"\x00\x01\x02\x03")
            subprocess.run(["git", "-C", repo_root, "add", "assets/blob.bin"], check=True)
            subprocess.run(
                ["git", "-C", repo_root, "commit", "-q", "-m", "add binary"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", repo_root, "checkout", "main"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", repo_root, "merge", "--squash", "feature"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", repo_root, "commit", "-q", "-m", "squash"],
                check=True,
                capture_output=True,
            )

            merge_commit = subprocess.run(
                ["git", "-C", repo_root, "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()

            result = delivered_size(repo_root, merge_commit)

            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["total"], 2)
            self.assertEqual(result["headline"], 2)


class TestPlanningArtifactPaths(unittest.TestCase):
    def test_exclusion_set_is_documented(self):
        """The exclusion constant matches the PRD's planning-artifact directories."""
        self.assertEqual(
            set(PLANNING_ARTIFACT_PATHS),
            {"docs/", ".agents/", "content/", "reports/"},
        )


if __name__ == "__main__":
    unittest.main()
