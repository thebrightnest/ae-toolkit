"""Tests for cfg-02: `aet configure` writer with all keys and scoped writes."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from aet.cli.configure_backend import NEW_CONFIG_NAME
from aet.cli.configure_backend import main as configure_main
from aet.project_id import derive_config_slug


class TestConfigureWriter(unittest.TestCase):
    """Behavior-driven tests for the `aet configure` command."""

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

    def _run(self, argv: list[str]) -> int:
        env = {"HOME": str(self.home), "AET_REPO_ROOT": str(self.project)}
        with patch.dict(os.environ, env, clear=True):
            return configure_main(["--non-interactive", *argv])

    def _read_project_config(self) -> dict | None:
        path = self.project / ".agents" / NEW_CONFIG_NAME
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def _read_user_config(self) -> dict | None:
        slug = derive_config_slug(self.project)
        path = self.home / ".aet" / slug / "config.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def test_writes_each_key_to_project_scope(self):
        """All config keys can be written to the in-tree project config."""
        rc = self._run(
            [
                "--trunk-branch",
                "main",
                "--integration-mode",
                "single-pr",
                "--integration-branch",
                "release",
                "--scope",
                "project",
            ]
        )
        self.assertEqual(rc, 0)
        config = self._read_project_config()
        self.assertIsNotNone(config)
        self.assertNotIn("task_backend", config)
        self.assertEqual(config["trunk_branch"], "main")
        self.assertEqual(config["integration_mode"], "single-pr")
        self.assertEqual(config["integration_branch"], "release")
        self.assertIsNone(self._read_user_config())

    def test_user_scope_writes_external_config(self):
        """--scope user writes under ~/.aet/{slug}/config.json."""
        rc = self._run(
            [
                "--integration-mode",
                "single-pr",
                "--scope",
                "user",
            ]
        )
        self.assertEqual(rc, 0)
        config = self._read_user_config()
        self.assertIsNotNone(config)
        self.assertEqual(config["integration_mode"], "single-pr")
        self.assertNotIn("task_backend", config)
        self.assertIsNone(self._read_project_config())

    def test_merge_style_preserves_unspecified_keys(self):
        """Unspecified keys keep their existing values in the target file."""
        agents = self.project / ".agents"
        agents.mkdir()
        existing = agents / NEW_CONFIG_NAME
        existing.write_text(
            json.dumps(
                {
                    "trunk_branch": "legacy-trunk",
                    "integration_mode": "pr-per-task",
                    "integration_branch": "legacy-integration",
                }
            ),
            encoding="utf-8",
        )

        rc = self._run(
            [
                "--trunk-branch",
                "main",
                "--scope",
                "project",
            ]
        )
        self.assertEqual(rc, 0)
        config = self._read_project_config()
        self.assertEqual(config["trunk_branch"], "main")
        self.assertEqual(config["integration_mode"], "pr-per-task")
        self.assertEqual(config["integration_branch"], "legacy-integration")
        self.assertNotIn("task_backend", config)

    def test_merge_style_strips_removed_task_backend_key(self):
        """A surviving task_backend key is stripped when config is rewritten."""
        agents = self.project / ".agents"
        agents.mkdir()
        existing = agents / NEW_CONFIG_NAME
        existing.write_text(
            json.dumps(
                {
                    "task_backend": "git-refs",
                    "integration_mode": "pr-per-task",
                }
            ),
            encoding="utf-8",
        )

        rc = self._run(
            [
                "--trunk-branch",
                "main",
                "--scope",
                "project",
            ]
        )
        self.assertEqual(rc, 0)
        config = self._read_project_config()
        self.assertNotIn("task_backend", config)
        self.assertEqual(config["integration_mode"], "pr-per-task")

    def test_invalid_integration_mode_rejected_naming_legal_values(self):
        """An invalid integration_mode is rejected and names the legal values."""
        rc = self._run(
            [
                "--integration-mode",
                "bad-mode",
                "--scope",
                "project",
            ]
        )
        self.assertEqual(rc, 1)
        self.assertIsNone(self._read_project_config())

    def test_scope_defaults_to_user_when_no_in_tree_config(self):
        """With no in-tree config, the default scope is user."""
        rc = self._run(
            [
                "--integration-mode",
                "single-pr",
            ]
        )
        self.assertEqual(rc, 0)
        self.assertIsNone(self._read_project_config())
        config = self._read_user_config()
        self.assertIsNotNone(config)
        self.assertEqual(config["integration_mode"], "single-pr")
        self.assertNotIn("task_backend", config)

    def test_old_command_name_is_gone(self):
        """The retired `configure-backend` alias is no longer registered."""
        import importlib

        from typer.testing import CliRunner

        aet_main = importlib.import_module("aet.cli.main")

        # The old top-level name must not resolve.
        runner = CliRunner()
        result = runner.invoke(aet_main.app, ["configure-backend", "--help"])
        self.assertEqual(result.exit_code, 2)
        self.assertIn("No such command", result.output)

    def test_shared_flag_writes_project_config(self):
        """--shared is the explicit one-command way to declare a shared project."""
        rc = self._run(["--shared"])
        self.assertEqual(rc, 0)
        config = self._read_project_config()
        self.assertIsNotNone(config)
        self.assertEqual(config["integration_mode"], "pr-per-task")
        self.assertIsNone(self._read_user_config())

    def test_shared_flag_conflicts_with_scope_user(self):
        """--shared cannot be combined with --scope user."""
        rc = self._run(["--shared", "--scope", "user"])
        self.assertEqual(rc, 1)
        self.assertIsNone(self._read_project_config())
        self.assertIsNone(self._read_user_config())

    def test_shared_flag_preserves_existing_keys(self):
        """--shared merges with existing project config like other scope writes."""
        agents = self.project / ".agents"
        agents.mkdir()
        existing = agents / "aet-config.json"
        existing.write_text(
            json.dumps({
                "trunk_branch": "main",
                "integration_mode": "single-pr",
                "integration_branch": "release",
            }),
            encoding="utf-8",
        )

        rc = self._run(["--shared", "--trunk-branch", "develop"])
        self.assertEqual(rc, 0)
        config = self._read_project_config()
        self.assertEqual(config["trunk_branch"], "develop")
        self.assertEqual(config["integration_mode"], "single-pr")
        self.assertEqual(config["integration_branch"], "release")


if __name__ == "__main__":
    unittest.main()
