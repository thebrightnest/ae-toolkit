"""Tests for integration_mode config resolution and fail-closed validation."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from aet.backends.factory import (
    IntegrationModeError,
    resolve_integration_mode,
)


class TestIntegrationModeResolution(unittest.TestCase):
    """Behavior-driven tests for external-first integration_mode resolution."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name) / "project"
        self.project.mkdir()
        self.home = Path(self.tmp.name) / "home"
        self.home.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def _write_in_tree(self, value: str | None):
        path = self.project / ".agents" / "aet-work.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        config: dict = {}
        if value is not None:
            config["integration_mode"] = value
        path.write_text(json.dumps(config), encoding="utf-8")

    def _write_external(self, slug: str, value: str | None):
        path = self.home / ".aet" / slug / "config.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        config: dict = {}
        if value is not None:
            config["integration_mode"] = value
        path.write_text(json.dumps(config), encoding="utf-8")

    def _write_env_config(self, value: str | None) -> Path:
        path = Path(self.tmp.name) / "env-config.json"
        config: dict = {}
        if value is not None:
            config["integration_mode"] = value
        path.write_text(json.dumps(config), encoding="utf-8")
        return path

    def test_default_is_pr_per_task_when_no_config_present(self):
        with patch.dict(os.environ, {"HOME": str(self.home)}, clear=False):
            mode = resolve_integration_mode(
                config_path=str(self.project / ".agents" / "aet-work.json")
            )
        self.assertEqual(mode, "pr-per-task")

    def test_in_tree_pr_per_task_resolves(self):
        self._write_in_tree("pr-per-task")
        with patch.dict(os.environ, {"HOME": str(self.home)}, clear=False):
            mode = resolve_integration_mode(
                config_path=str(self.project / ".agents" / "aet-work.json")
            )
        self.assertEqual(mode, "pr-per-task")

    def test_in_tree_single_pr_resolves(self):
        self._write_in_tree("single-pr")
        with patch.dict(os.environ, {"HOME": str(self.home)}, clear=False):
            mode = resolve_integration_mode(
                config_path=str(self.project / ".agents" / "aet-work.json")
            )
        self.assertEqual(mode, "single-pr")

    def test_unrecognized_value_fails_closed_naming_key_and_legal_values(self):
        self._write_in_tree("typo-mode")
        with patch.dict(os.environ, {"HOME": str(self.home)}, clear=False):
            with self.assertRaises(IntegrationModeError) as ctx:
                resolve_integration_mode(
                    config_path=str(self.project / ".agents" / "aet-work.json")
                )
        msg = str(ctx.exception)
        self.assertIn("integration_mode", msg)
        self.assertIn("typo-mode", msg)
        self.assertIn("pr-per-task", msg)
        self.assertIn("single-pr", msg)

    def test_external_config_beats_in_tree(self):
        with patch.dict(
            os.environ,
            {"HOME": str(self.home), "AET_PROJECT_ID": "myproject/main"},
            clear=False,
        ):
            self._write_external("myproject/main", "single-pr")
            self._write_in_tree("pr-per-task")
            mode = resolve_integration_mode(
                config_path=str(self.project / ".agents" / "aet-work.json")
            )
        self.assertEqual(mode, "single-pr")

    def test_env_config_beats_external_and_in_tree(self):
        env_config = self._write_env_config("pr-per-task")
        with patch.dict(
            os.environ,
            {
                "HOME": str(self.home),
                "AET_PROJECT_ID": "myproject/main",
                "AET_WORK_CONFIG": str(env_config),
            },
            clear=False,
        ):
            self._write_external("myproject/main", "single-pr")
            self._write_in_tree("single-pr")
            mode = resolve_integration_mode(
                config_path=str(self.project / ".agents" / "aet-work.json")
            )
        self.assertEqual(mode, "pr-per-task")

    def test_unrecognized_value_in_external_config_fails_closed(self):
        with patch.dict(
            os.environ,
            {"HOME": str(self.home), "AET_PROJECT_ID": "myproject/main"},
            clear=False,
        ):
            self._write_external("myproject/main", "bad-mode")
            with self.assertRaises(IntegrationModeError):
                resolve_integration_mode(
                    config_path=str(self.project / ".agents" / "aet-work.json")
                )

    def test_unrecognized_value_in_env_config_fails_closed(self):
        env_config = self._write_env_config("unknown")
        with patch.dict(
            os.environ,
            {"HOME": str(self.home), "AET_WORK_CONFIG": str(env_config)},
            clear=False,
        ):
            with self.assertRaises(IntegrationModeError):
                resolve_integration_mode(
                    config_path=str(self.project / ".agents" / "aet-work.json")
                )


if __name__ == "__main__":
    unittest.main()
