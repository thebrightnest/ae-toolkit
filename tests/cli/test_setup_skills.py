"""Tests for `aet setup skills` skill symlinking command."""

from __future__ import annotations

import importlib
import tempfile
import unittest
from pathlib import Path

from tests.cli._helpers import run_typer

aet = importlib.import_module("aet.cli.main")


class SetupSkillsTestCase(unittest.TestCase):
    """Shared temp dirs + CLI invocation helpers."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.skills_dir = Path(self.tmp.name) / "skills"
        self.repo_root = Path(aet.__file__).resolve().parent.parent.parent.parent

    def _run_setup_skills(self, *args, env=None):
        """Run `aet setup skills <args>` through the Typer app; returns Result.

        Forces ``AET_REPO_ROOT`` to the test repo root so tests are not
        coupled to whatever the orchestrator (or shell) happens to have set.
        """
        env = dict(env or {})
        env.setdefault("AET_REPO_ROOT", str(self.repo_root))
        return run_typer(aet.app, ["setup", "skills", *args], env=env)

    def _first_repo_skill(self):
        """Return an arbitrary skill directory from the repo."""
        return next(
            p
            for p in (self.repo_root / "skills").iterdir()
            if p.is_dir() and (p / "SKILL.md").is_file()
        )


class TestSetupSkillsFreshLink(SetupSkillsTestCase):
    """`aet setup skills` links every repo skill into the target directory."""

    def test_creates_symlinks_for_all_skills(self):
        result = self._run_setup_skills("--skills-dir", str(self.skills_dir))
        self.assertEqual(result.exit_code, 0, result.stderr)

        repo_skills = [p for p in (self.repo_root / "skills").iterdir() if p.is_dir() and (p / "SKILL.md").is_file()]
        self.assertGreater(len(repo_skills), 0)
        for skill in repo_skills:
            link = self.skills_dir / skill.name
            self.assertTrue(link.is_symlink(), f"{link} is not a symlink")
            self.assertEqual(link.resolve(), skill.resolve())

    def test_dry_run_lists_without_writing(self):
        result = self._run_setup_skills("--dry-run", "--skills-dir", str(self.skills_dir))
        self.assertEqual(result.exit_code, 0, result.stderr)

        self.assertFalse(self.skills_dir.exists())
        repo_skills = [p for p in (self.repo_root / "skills").iterdir() if p.is_dir() and (p / "SKILL.md").is_file()]
        for skill in repo_skills:
            self.assertIn("would link", result.stdout)
            self.assertIn(skill.name, result.stdout)

    def test_second_run_is_noop(self):
        self._run_setup_skills("--skills-dir", str(self.skills_dir))
        result = self._run_setup_skills("--skills-dir", str(self.skills_dir))
        self.assertEqual(result.exit_code, 0, result.stderr)

        repo_skills = [p for p in (self.repo_root / "skills").iterdir() if p.is_dir() and (p / "SKILL.md").is_file()]
        for skill in repo_skills:
            self.assertIn("already linked", result.stdout)
            link = self.skills_dir / skill.name
            self.assertTrue(link.is_symlink())


class TestSetupSkillsCollisions(SetupSkillsTestCase):
    """Non-symlink collisions are skipped unless --force is used."""

    def test_collision_skipped_without_force(self):
        self.skills_dir.mkdir(parents=True)
        first_skill = self._first_repo_skill()
        collision = self.skills_dir / first_skill.name
        collision.write_text("foreign", encoding="utf-8")

        result = self._run_setup_skills("--skills-dir", str(self.skills_dir))
        self.assertEqual(result.exit_code, 0, result.stderr)
        self.assertFalse(collision.is_symlink())
        self.assertEqual(collision.read_text(encoding="utf-8"), "foreign")
        self.assertIn("exists but is not a symlink", result.stdout)

    def test_force_replaces_collision_with_symlink(self):
        self.skills_dir.mkdir(parents=True)
        first_skill = self._first_repo_skill()
        collision = self.skills_dir / first_skill.name
        collision.write_text("foreign", encoding="utf-8")

        result = self._run_setup_skills("--skills-dir", str(self.skills_dir), "--force")
        self.assertEqual(result.exit_code, 0, result.stderr)
        self.assertTrue(collision.is_symlink())
        self.assertEqual(collision.resolve(), first_skill.resolve())
        self.assertIn("replaced with symlink", result.stdout)


class TestSetupSkillsAgentMapping(SetupSkillsTestCase):
    """``--agent`` maps to the correct agent skills directory."""

    def test_agent_generic_uses_dot_agents(self):
        fake_home = Path(self.tmp.name) / "home"
        fake_home.mkdir()
        result = self._run_setup_skills(
            "--agent", "generic",
            env={"HOME": str(fake_home)},
        )
        self.assertEqual(result.exit_code, 0, result.stderr)
        self.assertTrue((fake_home / ".agents" / "skills").is_dir())

    def test_unknown_agent_exits_with_error(self):
        result = self._run_setup_skills("--agent", "nosuchagent")
        self.assertEqual(result.exit_code, 1)
        self.assertIn("unknown agent", result.stderr)


class TestSetupSkillsAutoDetect(SetupSkillsTestCase):
    """Auto-detection installs to every existing agent skills directory."""

    def test_installs_to_all_detected_directories(self):
        fake_home = Path(self.tmp.name) / "home"
        agent_dirs = [
            fake_home / ".claude" / "skills",
            fake_home / ".cursor" / "skills",
        ]
        for d in agent_dirs:
            d.mkdir(parents=True)

        result = self._run_setup_skills(env={"HOME": str(fake_home)})
        self.assertEqual(result.exit_code, 0, result.stderr)

        repo_skills = [p for p in (self.repo_root / "skills").iterdir() if p.is_dir() and (p / "SKILL.md").is_file()]
        for agent_dir in agent_dirs:
            for skill in repo_skills:
                link = agent_dir / skill.name
                self.assertTrue(link.is_symlink(), f"{link} is not a symlink")
                self.assertEqual(link.resolve(), skill.resolve())


class TestSetupSkillsRepoRootEnv(SetupSkillsTestCase):
    """``AET_REPO_ROOT`` overrides filesystem inference."""

    def test_aet_repo_root_overrides_inferred_root(self):
        other_root = Path(self.tmp.name) / "other-repo"
        fake_skill = other_root / "skills" / "fake-skill"
        fake_skill.mkdir(parents=True)
        (fake_skill / "SKILL.md").write_text("---\n", encoding="utf-8")

        result = self._run_setup_skills(
            "--skills-dir", str(self.skills_dir),
            env={"AET_REPO_ROOT": str(other_root)},
        )
        self.assertEqual(result.exit_code, 0, result.stderr)
        link = self.skills_dir / "fake-skill"
        self.assertTrue(link.is_symlink(), f"{link} is not a symlink")
        self.assertEqual(link.resolve(), fake_skill.resolve())


class TestSetupSkillsHelp(SetupSkillsTestCase):
    """``--help`` prints usage."""

    def test_help_prints_usage(self):
        result = self._run_setup_skills("--help")
        self.assertEqual(result.exit_code, 0, result.stderr)
        self.assertIn("Symlink AE Toolkit skills", result.stdout)
        self.assertIn("--skills-dir", result.stdout)
        self.assertIn("--agent", result.stdout)
        self.assertIn("--dry-run", result.stdout)
        self.assertIn("--force", result.stdout)


if __name__ == "__main__":
    unittest.main()
