"""Tests for cfg-01: config resolution overhaul.

Covers R-1 (rename + fail-closed), R-2 (root-anchored in-tree resolution),
R-3 (worktree-independent external slug), and the ``aet configure --migrate``
remedy.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from aet.backends.factory import (
    DEFAULT_CONFIG_PATH,
    LegacyConfigError,
    resolve_config,
)
from aet.cli.configure_backend import (
    LEGACY_CONFIG_NAME,
    NEW_CONFIG_NAME,
    _migrate_config,
)


class TestLegacyFailClosed(unittest.TestCase):
    """R-1: legacy file present without new file fails closed naming migrate."""

    def setUp(self):
        self._cwd = os.getcwd()
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name) / "project"
        self.project.mkdir()
        self.home = Path(self.tmp.name) / "home"
        self.home.mkdir()
        subprocess.run(["git", "init", "-q", str(self.project)], check=True, capture_output=True)
        subprocess.run(
            ["git", "-C", str(self.project), "config", "user.email", "test@example.com"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(self.project), "config", "user.name", "Test User"],
            check=True,
            capture_output=True,
        )
        os.chdir(self.project)

    def tearDown(self):
        os.chdir(self._cwd)
        self.tmp.cleanup()

    def test_legacy_file_only_fails_closed_naming_migrate(self):
        agents = self.project / ".agents"
        agents.mkdir()
        (agents / "aet-work.json").write_text(
            json.dumps({"integration_mode": "single-pr"}), encoding="utf-8"
        )

        env = {"HOME": str(self.home), "AET_REPO_ROOT": str(self.project)}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(LegacyConfigError) as ctx:
                resolve_config(DEFAULT_CONFIG_PATH)

        msg = str(ctx.exception)
        self.assertIn("aet configure --migrate", msg)
        self.assertIn("aet-work.json", msg)
        self.assertIn("aet-config.json", msg)


class TestRootAnchoredResolution(unittest.TestCase):
    """R-2: in-tree config resolves from repo root, not cwd."""

    def setUp(self):
        self._cwd = os.getcwd()
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name) / "project"
        self.project.mkdir()
        self.home = Path(self.tmp.name) / "home"
        self.home.mkdir()
        subprocess.run(["git", "init", "-q", str(self.project)], check=True, capture_output=True)
        subprocess.run(
            ["git", "-C", str(self.project), "config", "user.email", "test@example.com"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(self.project), "config", "user.name", "Test User"],
            check=True,
            capture_output=True,
        )

    def tearDown(self):
        os.chdir(self._cwd)
        self.tmp.cleanup()

    def test_new_file_resolves_from_subdirectory(self):
        agents = self.project / ".agents"
        agents.mkdir()
        (agents / "aet-config.json").write_text(
            json.dumps({"integration_mode": "single-pr"}), encoding="utf-8"
        )

        subdir = self.project / "src" / "nested"
        subdir.mkdir(parents=True)
        os.chdir(subdir)

        env = {"HOME": str(self.home), "AET_REPO_ROOT": str(self.project)}
        with patch.dict(os.environ, env, clear=True):
            config = resolve_config(DEFAULT_CONFIG_PATH)

        self.assertEqual(config["integration_mode"], "single-pr")


class TestWorktreeIndependentExternalSlug(unittest.TestCase):
    """R-3: external config uses main-worktree identity from linked worktree."""

    def setUp(self):
        self._cwd = os.getcwd()
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / "home"
        self.home.mkdir()

    def tearDown(self):
        os.chdir(self._cwd)
        self.tmp.cleanup()

    def test_external_config_resolves_from_linked_worktree(self):
        repo_root = Path(self.tmp.name) / "repo"
        repo_root.mkdir()
        subprocess.run(["git", "init", "-q", str(repo_root)], check=True, capture_output=True)
        subprocess.run(
            ["git", "-C", str(repo_root), "config", "user.email", "test@example.com"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(repo_root), "config", "user.name", "Test User"],
            check=True,
            capture_output=True,
        )
        (repo_root / "README.md").write_text("# test", encoding="utf-8")
        subprocess.run(["git", "-C", str(repo_root), "add", "."], check=True, capture_output=True)
        subprocess.run(
            ["git", "-C", str(repo_root), "commit", "-q", "-m", "initial"],
            check=True,
            capture_output=True,
        )

        # Add a linked worktree.
        worktree_dir = Path(self.tmp.name) / "linked"
        subprocess.run(
            ["git", "-C", str(repo_root), "worktree", "add", str(worktree_dir), "-b", "feature"],
            check=True,
            capture_output=True,
        )

        # External config under the main-worktree identity.
        external = self.home / ".aet" / "repo" / "main" / "config.json"
        external.parent.mkdir(parents=True)
        external.write_text(json.dumps({"integration_mode": "single-pr"}), encoding="utf-8")

        os.chdir(worktree_dir)
        env = {"HOME": str(self.home), "AET_REPO_ROOT": str(worktree_dir)}
        with patch.dict(os.environ, env, clear=True):
            # Run from inside the linked worktree.
            config = resolve_config(DEFAULT_CONFIG_PATH)

        self.assertEqual(config["integration_mode"], "single-pr")


class TestMigrateCommand(unittest.TestCase):
    """``aet configure --migrate`` renames legacy config safely."""

    def setUp(self):
        self._cwd = os.getcwd()
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name) / "project"
        self.project.mkdir()
        subprocess.run(["git", "init", "-q", str(self.project)], check=True, capture_output=True)
        subprocess.run(
            ["git", "-C", str(self.project), "config", "user.email", "test@example.com"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(self.project), "config", "user.name", "Test User"],
            check=True,
            capture_output=True,
        )
        os.chdir(self.project)

    def tearDown(self):
        os.chdir(self._cwd)
        self.tmp.cleanup()

    def test_migrate_renames_and_strips_removed_key(self):
        agents = self.project / ".agents"
        agents.mkdir()
        legacy = agents / LEGACY_CONFIG_NAME
        new_file = agents / NEW_CONFIG_NAME
        legacy.write_text(
            json.dumps({"task_backend": "git-refs", "integration_mode": "single-pr"}),
            encoding="utf-8",
        )

        with patch.dict(os.environ, {"AET_REPO_ROOT": str(self.project)}, clear=True):
            rc = _migrate_config(self.project)
        self.assertEqual(rc, 0)
        self.assertFalse(legacy.exists())
        self.assertTrue(new_file.exists())
        config = json.loads(new_file.read_text(encoding="utf-8"))
        self.assertNotIn("task_backend", config)
        self.assertEqual(config["integration_mode"], "single-pr")

    def test_migrate_refuses_overwrite_of_existing_new_file(self):
        agents = self.project / ".agents"
        agents.mkdir()
        legacy = agents / LEGACY_CONFIG_NAME
        new_file = agents / NEW_CONFIG_NAME
        legacy.write_text(json.dumps({"task_backend": "git-refs"}), encoding="utf-8")
        new_file.write_text(json.dumps({"integration_mode": "pr-per-task"}), encoding="utf-8")

        with patch.dict(os.environ, {"AET_REPO_ROOT": str(self.project)}, clear=True):
            with self.assertRaises(SystemExit) as ctx:
                _migrate_config(self.project)
        self.assertEqual(ctx.exception.code, 1)
        self.assertTrue(legacy.exists())
        self.assertTrue(new_file.exists())


if __name__ == "__main__":
    unittest.main()
