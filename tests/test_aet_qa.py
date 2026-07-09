"""Tests for aet-qa skill instructions."""

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).parent.parent
SKILL_MD = REPO_ROOT / "aet-qa" / "SKILL.md"


class TestAetQaImpactScopedDefaults(unittest.TestCase):
    """Regression tests for impact-scoped test defaults in aet-qa."""

    def setUp(self):
        self.content = SKILL_MD.read_text(encoding="utf-8")

    def test_skill_defaults_to_impact_scoped_tests(self):
        self.assertIn(
            "Default to impact-scoped tests",
            self.content,
            "SKILL.md should default to impact-scoped tests",
        )

    def test_skill_uses_git_diff_name_only(self):
        self.assertIn(
            "git diff --name-only <pr-base>..HEAD",
            self.content,
            "SKILL.md should identify changed files with git diff",
        )

    def test_skill_defines_full_suite_fallback(self):
        self.assertIn(
            "Full-suite fallback",
            self.content,
            "SKILL.md should define a full-suite fallback",
        )

    def test_full_suite_fallback_conditions_match_prd(self):
        for condition in (
            "test harness",
            "config",
            "shared fixtures",
            "dependency lockfiles",
            "files imported by many tests",
        ):
            self.assertIn(
                condition,
                self.content,
                f"Full-suite fallback should mention '{condition}'",
            )


if __name__ == "__main__":
    unittest.main()
