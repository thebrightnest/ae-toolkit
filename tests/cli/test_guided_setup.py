"""Tests for cfg-04: `aet configure --guided` two-question setup flow."""

from __future__ import annotations

import io
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


class TestGuidedSetup(unittest.TestCase):
    """Behavior-driven tests for the guided `aet configure --guided` flow."""

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

    def _run(self, argv: list[str], input_text: str | None = None) -> int:
        env = {"HOME": str(self.home), "AET_REPO_ROOT": str(self.project)}
        with patch.dict(os.environ, env, clear=True):
            if input_text is not None:
                # Simulate interactive input by patching sys.stdin.
                with patch("sys.stdin", io.StringIO(input_text)):
                    return configure_main(["--guided", *argv])
            return configure_main(["--guided", *argv])

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

    def test_team_choice_writes_in_tree_config(self):
        """Answering team + pr-per-task writes .agents/aet-config.json."""
        rc = self._run([], input_text="team\npr-per-task\n")
        self.assertEqual(rc, 0)
        config = self._read_project_config()
        self.assertIsNotNone(config)
        self.assertEqual(config.get("integration_mode"), "pr-per-task")
        self.assertIsNone(self._read_user_config())

    def test_shadow_choice_writes_external_config_only(self):
        """Answering shadow + single-pr writes only ~/.aet/{slug}/config.json."""
        rc = self._run([], input_text="shadow\nsingle-pr\n")
        self.assertEqual(rc, 0)
        config = self._read_user_config()
        self.assertIsNotNone(config)
        self.assertEqual(config.get("integration_mode"), "single-pr")
        self.assertIsNone(self._read_project_config())

    def test_existing_config_requires_confirmation(self):
        """An existing config is left unchanged when the user declines overwrite."""
        agents = self.project / ".agents"
        agents.mkdir()
        existing = agents / NEW_CONFIG_NAME
        existing.write_text(
            json.dumps({"integration_mode": "single-pr"}),
            encoding="utf-8",
        )

        rc = self._run([], input_text="team\npr-per-task\nno\n")
        self.assertEqual(rc, 0)
        config = self._read_project_config()
        self.assertEqual(config["integration_mode"], "single-pr")

    def test_non_interactive_flags_skip_prompts(self):
        """Providing --scope and --integration-mode skips all prompts."""
        rc = self._run(["--scope", "team", "--integration-mode", "single-pr"])
        self.assertEqual(rc, 0)
        config = self._read_project_config()
        self.assertIsNotNone(config)
        self.assertEqual(config["integration_mode"], "single-pr")


if __name__ == "__main__":
    unittest.main()
