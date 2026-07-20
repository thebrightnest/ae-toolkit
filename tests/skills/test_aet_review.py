"""Tests for aet-review skill instructions."""

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]
SKILL_MD = REPO_ROOT / "aet-review" / "SKILL.md"


class TestAetReviewNoiseFilter(unittest.TestCase):
    """Regression tests for review scope and noise filter in aet-review."""

    def setUp(self):
        self.content = SKILL_MD.read_text(encoding="utf-8")

    def test_skill_scopes_diff_to_pr_base(self):
        self.assertIn(
            "git diff <base>..HEAD",
            self.content,
            "SKILL.md should scope the review diff to the PR base",
        )

    def test_skill_ignores_project_level_noise_files(self):
        for noise_file in (
            ".gitignore",
            "AGENTS.md",
            "docs/CONVENTIONS.md",
        ):
            self.assertIn(
                noise_file,
                self.content,
                f"Noise filter should mention '{noise_file}'",
            )

    def test_noise_files_in_scope_only_when_explicitly_modified(self):
        self.assertIn(
            "explicitly modifies them",
            self.content,
            "Noise files should be in-scope only when explicitly modified",
        )


if __name__ == "__main__":
    unittest.main()
