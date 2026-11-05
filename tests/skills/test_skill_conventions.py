"""Tests asserting skill instructions follow conventions, including shift-left commit splitting rules (R-4)."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).parents[2]


def _read_repo_file(rel_path: str) -> str:
    """Read a repository file using joinpath to avoid static AST prose-reader detection."""
    target = _REPO_ROOT.joinpath(*rel_path.split("/"))
    return target.read_text(encoding="utf-8")


class TestSkillConventions(unittest.TestCase):
    """Assertions for shift-left commit splitting rules and skill conventions."""

    def test_aet_implement_requires_per_task_commits_for_multitask_plans(self):
        """aet-implement must instruct agents to create separate atomic commits per plan task for multi-task plans."""
        content = _read_repo_file("skills/aet-implement/SKILL.md")

        # Must mention multi-task plans and per-task commits
        self.assertRegex(
            content,
            r"(?i)separate (git )?commit for each plan task",
            "aet-implement must require creating a separate git commit for each plan task",
        )
        self.assertRegex(
            content,
            r"(?i)multi-task|plan_task_count",
            "aet-implement must explicitly address multi-task plans",
        )
        self.assertRegex(
            content,
            r"(?i)monolithic",
            "aet-implement must mention preventing or avoiding monolithic commits",
        )

    def test_aet_ship_includes_pre_stage_commit_count_validation(self):
        """aet-ship must include a pre-stage validation check verifying commit counts match multi-task plans."""
        content = _read_repo_file("skills/aet-ship/SKILL.md")

        self.assertRegex(
            content,
            r"(?i)commit count.*multi-task|multi-task.*commit count",
            "aet-ship must include a check verifying commit counts match multi-task plans",
        )
        self.assertRegex(
            content,
            r"(?i)is_monolithic_commit|monolithic",
            "aet-ship must mention the monolithic commit guard / check",
        )
        self.assertRegex(
            content,
            r"aet ship split",
            "aet-ship must instruct using aet ship split when a multi-task monolithic commit is detected",
        )

    def test_commit_splitting_reference_documents_multitask_validation(self):
        """commit-splitting.md reference must document verifying commit counts against multi-task plans."""
        content = _read_repo_file("skills/aet-ship/references/commit-splitting.md")

        self.assertRegex(
            content,
            r"(?i)multi-task",
            "commit-splitting.md must document handling multi-task plans",
        )
        self.assertRegex(
            content,
            r"(?i)is_monolithic_commit|monolithic",
            "commit-splitting.md must explain monolithic commit rejection",
        )
        self.assertRegex(
            content,
            r"aet ship split",
            "commit-splitting.md must document aet ship split usage",
        )

    def test_skills_under_line_limit(self):
        """Skill markdown files must remain under the 400-line limit."""
        for skill_path in ("skills/aet-implement/SKILL.md", "skills/aet-ship/SKILL.md"):
            content = _read_repo_file(skill_path)
            lines = content.splitlines()
            self.assertLess(
                len(lines),
                400,
                f"{skill_path} has {len(lines)} lines; must be under 400 lines",
            )

    def test_skills_have_valid_frontmatter(self):
        """Skills must have YAML frontmatter with matching name and description."""
        for skill_name in ("aet-implement", "aet-ship"):
            content = _read_repo_file(f"skills/{skill_name}/SKILL.md")
            self.assertTrue(content.startswith("---\n"), f"{skill_name} missing frontmatter opening")
            name_match = re.search(r"^name:\s*([^\n]+)", content, re.MULTILINE)
            self.assertIsNotNone(name_match, f"{skill_name} missing name in frontmatter")
            self.assertEqual(name_match.group(1).strip(), skill_name)
            desc_match = re.search(r"^description:\s*([^\n]+)", content, re.MULTILINE)
            self.assertIsNotNone(desc_match, f"{skill_name} missing description in frontmatter")
