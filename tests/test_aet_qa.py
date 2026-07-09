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


class TestAetQaStageFailureTriage(unittest.TestCase):
    """Regression tests for stage-failure triage checklist in aet-qa."""

    def setUp(self):
        self.content = SKILL_MD.read_text(encoding="utf-8")

    def test_skill_includes_stage_failure_triage_heading(self):
        self.assertIn(
            "Stage-failure triage",
            self.content,
            "SKILL.md should include a stage-failure triage checklist",
        )

    def test_triage_includes_required_evidence_fields(self):
        for field in (
            "command",
            "output",
            "files touched",
            "last successful stage",
            "environment variables",
            "reproduces outside",
        ):
            self.assertIn(
                field,
                self.content.lower(),
                f"Triage checklist should mention '{field}'",
            )

    def test_triage_report_goes_to_qa_report(self):
        self.assertIn(
            "QA report",
            self.content,
            "Triage evidence should be appended to the QA report",
        )


if __name__ == "__main__":
    unittest.main()
