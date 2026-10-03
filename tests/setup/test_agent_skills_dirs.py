"""Tests for agent skills directory detection and resolution in `aet setup skills`."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from aet.cli import setup as setup_mod


class TestAgentSkillsDirs(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)

    def test_detects_antigravity_gemini_skills_dir(self):
        gemini_skills = self.home / ".gemini" / "config" / "skills"
        gemini_skills.mkdir(parents=True)

        with patch.object(Path, "home", return_value=self.home):
            detected = setup_mod._agent_skills_dirs()

        self.assertIn(gemini_skills, detected)

    def test_resolve_target_dirs_named_agents(self):
        gemini_skills = self.home / ".gemini" / "config" / "skills"

        with patch.object(Path, "home", return_value=self.home):
            for alias in ("antigravity", "gemini", "agy"):
                dirs = setup_mod._resolve_target_dirs(skills_dir=None, agent=alias)
                self.assertEqual(dirs, [gemini_skills])


if __name__ == "__main__":
    unittest.main()
