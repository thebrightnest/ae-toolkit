"""`aet setup verify` must name a skill link that points at another checkout.

A stale skill link fails silently: the skill loads, so nothing errors, and the
session follows instructions from whichever checkout the link was made against.
Two retros' fixes never reached a session that way, and the only visible symptom
was a session behaving as though the fix did not exist.
"""

from __future__ import annotations

import io
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from aet.cli import setup as setup_mod


def _repo_with_skills(root: Path, names: list[str]) -> Path:
    """Create a repo whose ``skills/`` holds each named skill."""
    skills = root / "skills"
    for name in names:
        d = skills / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(f"# {name}\n", encoding="utf-8")
    return skills


class TestSkillLinkDrift(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.skills = _repo_with_skills(self.repo, ["aet-plan", "aet-ship"])
        self.other = self.root / "other-checkout"
        _repo_with_skills(self.other, ["aet-plan", "aet-ship"])
        self.target = self.root / "agent-skills"
        self.target.mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def _run(self) -> str:
        err = io.StringIO()
        with patch.object(setup_mod, "_repo_root", return_value=self.repo), \
             patch.object(setup_mod, "_agent_skills_dirs", return_value=[self.target]):
            with redirect_stderr(err), redirect_stdout(io.StringIO()):
                setup_mod._report_skill_link_drift()
        return err.getvalue()

    def test_a_link_into_another_checkout_is_named(self):
        """The bug: this drift was silent, and `verify` never looked."""
        (self.target / "aet-plan").symlink_to(self.other / "skills" / "aet-plan")
        (self.target / "aet-ship").symlink_to(self.skills / "aet-ship")

        err = self._run()

        self.assertIn("aet-plan", err)
        self.assertIn("do not point at", err)
        self.assertIn("aet setup skills", err)
        self.assertNotIn("aet-ship ->", err)

    def test_correct_links_are_not_reported_as_drift(self):
        for name in ("aet-plan", "aet-ship"):
            (self.target / name).symlink_to(self.skills / name)

        self.assertNotIn("do not point at", self._run())

    def test_a_broken_link_is_reported_not_crashed_on(self):
        (self.target / "aet-plan").symlink_to(self.root / "gone" / "aet-plan")

        err = self._run()

        self.assertIn("aet-plan", err)
        self.assertIn("do not point at", err)

    def test_an_absent_link_is_not_drift(self):
        """A skill that was never linked is a different condition."""
        self.assertNotIn("do not point at", self._run())

    def test_a_non_symlink_directory_is_not_reported_as_drift(self):
        (self.target / "aet-plan").mkdir()

        self.assertNotIn("do not point at", self._run())


if __name__ == "__main__":
    sys.exit(unittest.main())
