"""Tests for verifier module."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "aet-work" / "lib"))

import subprocess
import tempfile
import unittest
from unittest import mock

from verifier import read_plan_stage, verify_stage_advancement


class TestVerifier(unittest.TestCase):
    def test_read_plan_stage(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Plan\n\n*Stage: implemented*\n")
            path = f.name

        stage = read_plan_stage(path)
        self.assertEqual(stage, "implemented")

    def test_read_plan_stage_missing(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Plan\n")
            path = f.name

        stage = read_plan_stage(path)
        self.assertIsNone(stage)

    def test_read_plan_stage_no_file(self):
        self.assertIsNone(read_plan_stage("/nonexistent/path.md"))

    def test_read_plan_stage_prefers_footer_over_body_mentions(self):
        """Body text may mention other stages; only the footer stage counts."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(
                "# Plan\n\n"
                "1. Set `other-plan.md` footer to *Stage: superseded*.\n\n"
                "---\n\n"
                "_Stage: plan-approved_\n"
            )
            path = f.name

        stage = read_plan_stage(path)
        self.assertEqual(stage, "plan-approved")


class TestVerifyStageAdvancement(unittest.TestCase):
    def _init_git_repo(self, repo_root: str) -> None:
        import subprocess

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

    def _commit_on_feature_branch(self, repo_root: str) -> None:
        """Create a feature branch with one commit ahead of main."""
        subprocess.run(
            ["git", "-C", repo_root, "checkout", "-q", "-b", "feature"],
            check=True,
        )
        Path(repo_root, "change.txt").write_text("x", encoding="utf-8")
        subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
        subprocess.run(
            ["git", "-C", repo_root, "commit", "-q", "-m", "change"],
            check=True,
        )

    def test_verify_stage_advancement_uses_recorded_stage(self):
        """Verification checks the recorded stage, not the plan footer."""
        with tempfile.TemporaryDirectory() as repo_root:
            self._init_git_repo(repo_root)
            self._commit_on_feature_branch(repo_root)

            ok, msg = verify_stage_advancement("implemented", repo_root, "implemented")

            self.assertTrue(ok, msg)

    def test_verify_stage_advancement_fails_when_recorded_stage_mismatches(self):
        """Verification fails when the recorded stage did not advance."""
        with tempfile.TemporaryDirectory() as repo_root:
            self._init_git_repo(repo_root)
            self._commit_on_feature_branch(repo_root)

            ok, msg = verify_stage_advancement("plan-approved", repo_root, "implemented")

            self.assertFalse(ok)
            self.assertIn("did not advance", msg)

    def test_verify_stage_advancement_requires_commits(self):
        """Verification fails when the branch has no commits."""
        with tempfile.TemporaryDirectory() as repo_root:
            self._init_git_repo(repo_root)

            ok, msg = verify_stage_advancement("implemented", repo_root, "implemented")

            self.assertFalse(ok)
            self.assertIn("0 commits", msg)

    def test_verify_stage_advancement_does_not_retry(self):
        """A mismatched stage fails immediately without sleeping or retrying."""
        with tempfile.TemporaryDirectory() as repo_root:
            self._init_git_repo(repo_root)
            self._commit_on_feature_branch(repo_root)

            with mock.patch("verifier.time", create=True) as mock_time:
                ok, msg = verify_stage_advancement(
                    "plan-approved", repo_root, "implemented"
                )

            self.assertFalse(ok)
            self.assertIn("did not advance", msg)
            mock_time.sleep.assert_not_called()

    def test_verify_stage_advancement_has_no_retries_parameter(self):
        """The retry knob is gone; the signature is a single comparison + commit check."""
        import inspect

        params = inspect.signature(verify_stage_advancement).parameters
        self.assertNotIn("retries", params)


if __name__ == "__main__":
    unittest.main()
