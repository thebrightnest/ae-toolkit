"""Tests for aet-setup example files."""

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
EXAMPLES_DIR = REPO_ROOT / "aet-setup" / "examples"


class TestWorktreeShipHygieneExample(unittest.TestCase):
    """Regression tests for the worktree-ship-hygiene example template."""

    def setUp(self):
        self.example = EXAMPLES_DIR / "worktree-ship-hygiene.md.example"
        self.agents_example = EXAMPLES_DIR / "AGENTS.md.example"

    def test_example_file_exists(self):
        self.assertTrue(
            self.example.exists(),
            f"Expected example file to exist: {self.example}",
        )

    def test_example_contains_aet_work_run_checklist(self):
        content = self.example.read_text()
        self.assertIn("Before `aet-work run`", content)

    def test_example_contains_aet_ship_checklist(self):
        content = self.example.read_text()
        self.assertIn("Before `aet-ship`", content)

    def test_example_contains_red_flags(self):
        content = self.example.read_text()
        self.assertIn("Red flags", content)
        self.assertIn(">50 changed files", content)
        self.assertIn("unrelated docs", content)
        self.assertIn("queue file changes", content)

    def test_example_referenced_from_agents_template(self):
        content = self.agents_example.read_text()
        self.assertIn("worktree-ship-hygiene", content)


if __name__ == "__main__":
    unittest.main()
