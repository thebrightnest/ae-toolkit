"""Tests for the ``aet plans lint`` corpus classifier stage."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]
from aet import plans_lint  # noqa: E402


def make_plan(path: Path, plan_id: str | None = None, status: str | None = None) -> None:
    """Write a minimal plan file using the frontmatter contract."""
    stem = plan_id or path.stem
    lines = ["---", f"id: {stem}", "size: S"]
    if status is not None:
        lines.append(f"status: {status}")
    lines.extend(
        [
            "---",
            "",
            f"# Plan {stem}",
            "",
            "## Context",
            "",
            "PRD: docs/prds/default-prd.md",
            "",
            "## Task List",
            "",
            "1. Do something (traces: R-1).",
            "",
            "---",
            "",
            "*Stage: plan-approved*",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class TestCorpusLint(unittest.TestCase):
    """Direct tests of ``plans_lint.lint_corpus``."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.plans_dir = self.root / "docs" / "plans"
        self.plans_dir.mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_clean_corpus_passes(self):
        """Statusless and terminal plans classify as settled; live plans do not."""
        make_plan(self.plans_dir / "legacy.md")
        make_plan(self.plans_dir / "merged.md", status="merged")
        make_plan(self.plans_dir / "abandoned.md", status="abandoned")
        make_plan(self.plans_dir / "queued.md", status="queued")
        make_plan(self.plans_dir / "draft.md", status="draft")

        violations = plans_lint.lint_corpus(self.plans_dir)

        self.assertEqual(violations, [])

    def test_invalid_status_fails(self):
        """An unrecognized status value is reported per offending plan."""
        make_plan(self.plans_dir / "bad.md", status="unknown")

        violations = plans_lint.lint_corpus(self.plans_dir)

        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0][0].name, "bad.md")
        self.assertIn("unknown", violations[0][1])

    def test_empty_corpus_passes(self):
        """An empty plans directory produces no violations."""
        violations = plans_lint.lint_corpus(self.plans_dir)

        self.assertEqual(violations, [])

    def test_missing_plans_dir_passes(self):
        """A missing plans directory produces no violations."""
        missing = self.root / "docs" / "plans"
        violations = plans_lint.lint_corpus(missing)

        self.assertEqual(violations, [])


class TestPlansLintCli(unittest.TestCase):
    """``aet plans lint`` reaches the new binary through the dispatcher."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.bin_dir = self.root / "bin"
        self.bin_dir.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def _run_aet(self, cwd: Path, *args: str) -> subprocess.CompletedProcess:
        env = {**os.environ, "AET_BIN_DIR": str(self.bin_dir)}
        cmd = [sys.executable, str(REPO_ROOT / "src" / "aet" / "cli" / "main.py"), *args]
        return subprocess.run(
            cmd,
            cwd=str(cwd),
            env=env,
            capture_output=True,
            text=True,
        )

    def test_plans_lint_routed_through_aet_dispatcher(self):
        """``aet plans lint`` runs the corpus classifier and exits 0."""
        repo = self.root / "repo"
        plans_dir = repo / "docs" / "plans"
        plans_dir.mkdir(parents=True)
        subprocess.run(["git", "init", "-q"], cwd=str(repo), check=True)
        make_plan(plans_dir / "legacy.md")
        make_plan(plans_dir / "merged.md", status="merged")

        result = self._run_aet(repo, "plans", "lint")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("all 2 plans classified correctly", result.stdout)

    def test_plans_lint_reports_invalid_status_file(self):
        """``aet plans lint`` names the plan file with the invalid status."""
        repo = self.root / "repo"
        plans_dir = repo / "docs" / "plans"
        plans_dir.mkdir(parents=True)
        subprocess.run(["git", "init", "-q"], cwd=str(repo), check=True)
        make_plan(plans_dir / "legacy.md")
        make_plan(plans_dir / "bad.md", status="unknown")

        result = self._run_aet(repo, "plans", "lint")

        self.assertEqual(result.returncode, 1)
        self.assertIn("bad.md", result.stderr)
        self.assertIn("unknown", result.stderr)


if __name__ == "__main__":
    unittest.main()
