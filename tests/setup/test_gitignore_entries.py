"""Tests for `aet setup bootstrap` gitignore entries."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path

import aet.worktree
from tests.cli._helpers import run_typer

aet_setup = importlib.import_module("aet.cli.setup")


class TestSetupBootstrapCli(unittest.TestCase):
    """CLI tests for the bootstrap command."""

    def test_bootstrap_command_writes_entries_to_cwd(self):
        with tempfile.TemporaryDirectory() as repo_root:
            result = run_typer(aet_setup.app, ["bootstrap"], cwd=repo_root)
            self.assertEqual(result.exit_code, 0, result.stderr)
            gitignore = Path(repo_root) / ".gitignore"
            lines = gitignore.read_text(encoding="utf-8").splitlines()
            self.assertIn(".agents/runs/", lines)
            self.assertIn(".worktrees/", lines)

    def test_bootstrap_command_respects_path_option(self):
        with tempfile.TemporaryDirectory() as repo_root:
            result = run_typer(
                aet_setup.app, ["bootstrap", "--path", repo_root], env=os.environ.copy()
            )
            self.assertEqual(result.exit_code, 0, result.stderr)
            self.assertTrue((Path(repo_root) / ".gitignore").exists())


class TestWriteAetGitignoreEntries(unittest.TestCase):
    """Unit tests for the idempotent gitignore writer."""

    def test_writes_every_constant_entry(self):
        ignored_paths = aet.worktree.AET_IGNORED_PATHS
        with tempfile.TemporaryDirectory() as repo_root:
            added = aet_setup.write_aet_gitignore_entries(repo_root)
            self.assertEqual(set(added), set(ignored_paths))
            gitignore = Path(repo_root) / ".gitignore"
            lines = gitignore.read_text(encoding="utf-8").splitlines()
            for entry in ignored_paths:
                self.assertIn(entry, lines)

    def test_second_run_adds_no_duplicates(self):
        ignored_paths = aet.worktree.AET_IGNORED_PATHS
        with tempfile.TemporaryDirectory() as repo_root:
            aet_setup.write_aet_gitignore_entries(repo_root)
            added = aet_setup.write_aet_gitignore_entries(repo_root)
            self.assertEqual(added, [])
            gitignore = Path(repo_root) / ".gitignore"
            lines = gitignore.read_text(encoding="utf-8").splitlines()
            for entry in ignored_paths:
                self.assertEqual(lines.count(entry), 1)

    def test_unrelated_existing_lines_are_untouched(self):
        with tempfile.TemporaryDirectory() as repo_root:
            gitignore = Path(repo_root) / ".gitignore"
            gitignore.write_text("node_modules/\n.env\n", encoding="utf-8")
            aet_setup.write_aet_gitignore_entries(repo_root)
            lines = gitignore.read_text(encoding="utf-8").splitlines()
            self.assertIn("node_modules/", lines)
            self.assertIn(".env", lines)
            self.assertEqual(lines.index("node_modules/"), 0)
            self.assertEqual(lines.index(".env"), 1)


if __name__ == "__main__":
    unittest.main()
