"""Tests for configuration honesty: unknown keys and contradictory combinations."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from aet.backends.factory import (
    ConfigContradictionError,
    UnknownConfigKeyError,
    resolve_config,
)


class TestConfigHonesty(unittest.TestCase):
    """AET config rejects silent misconfigurations."""

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

    def _write_in_tree(self, config: dict) -> None:
        path = self.project / ".agents" / "aet-config.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(config), encoding="utf-8")

    def _write_external(self, config: dict) -> None:
        slug = "test-project"
        path = self.home / ".aet" / slug / "config.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(config), encoding="utf-8")

    def _patch_home(self):
        return patch.dict(
            os.environ,
            {"HOME": str(self.home), "AET_PROJECT_ID": "test-project"},
            clear=True,
        )

    def test_unknown_key_rejected_naming_legal_keys(self):
        """A single unknown key fails and names every legal key."""
        self._write_in_tree({"integration_mode": "single-pr", "projecton": "github"})

        with self._patch_home():
            with self.assertRaises(UnknownConfigKeyError) as ctx:
                resolve_config(".agents/aet-config.json")

        msg = str(ctx.exception).lower()
        self.assertIn("unknown", msg)
        self.assertIn("projecton", msg)
        for key in ("trunk_branch", "integration_branch", "integration_mode", "projections"):
            self.assertIn(key, msg)

    def test_misspelled_projections_rejected(self):
        """The common typo `projection` is rejected, naming `projections`."""
        self._write_in_tree({"projection": [{"type": "github", "repo": "foo/bar"}]})

        with self._patch_home():
            with self.assertRaises(UnknownConfigKeyError) as ctx:
                resolve_config(".agents/aet-config.json")

        self.assertIn("projection", str(ctx.exception))
        self.assertIn("projections", str(ctx.exception))

    def test_projections_in_external_config_rejected(self):
        """Projections require shared posture; external config is shadow."""
        self._write_external({"projections": [{"type": "github", "repo": "foo/bar"}]})

        with self._patch_home():
            with self.assertRaises(ConfigContradictionError) as ctx:
                resolve_config(".agents/aet-config.json")

        msg = str(ctx.exception)
        self.assertIn("projections", msg)
        self.assertIn("shadow", msg.lower())
        self.assertIn("project", msg.lower())

    def test_projections_in_env_config_rejected(self):
        """Projections in the env-override config are also shadow."""
        env_config = self.home / "env-config.json"
        env_config.write_text(
            json.dumps({"projections": [{"type": "github", "repo": "foo/bar"}]}),
            encoding="utf-8",
        )

        with patch.dict(
            os.environ,
            {"HOME": str(self.home), "AET_WORK_CONFIG": str(env_config)},
            clear=True,
        ):
            with self.assertRaises(ConfigContradictionError) as ctx:
                resolve_config(".agents/aet-config.json")

        self.assertIn("projections", str(ctx.exception))

    def test_projections_in_project_config_allowed(self):
        """Projections in the in-tree team config are shared posture and OK."""
        self._write_in_tree(
            {"integration_mode": "single-pr", "projections": [{"type": "github", "repo": "foo/bar"}]}
        )

        with self._patch_home():
            config = resolve_config(".agents/aet-config.json")

        self.assertEqual(config["integration_mode"], "single-pr")
        self.assertEqual(len(config["projections"]), 1)

    def test_multiple_unknown_keys_sorted(self):
        """Multiple unknown keys are listed in sorted order."""
        self._write_in_tree({"zebra": 1, "apple": 2})

        with self._patch_home():
            with self.assertRaises(UnknownConfigKeyError) as ctx:
                resolve_config(".agents/aet-config.json")

        msg = str(ctx.exception)
        self.assertIn("apple", msg)
        self.assertIn("zebra", msg)
        # Sorted order should list apple before zebra.
        self.assertLess(msg.index("apple"), msg.index("zebra"))


if __name__ == "__main__":
    unittest.main()
