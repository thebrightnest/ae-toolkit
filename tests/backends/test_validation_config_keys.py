"""Tests for validation command config keys and resolution (R-1)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from aet.backends.factory import (
    LEGAL_CONFIG_KEYS,
    resolve_validation_commands,
)


class TestValidationConfigKeys(unittest.TestCase):
    def test_legal_config_keys_include_validation_keys(self):
        """validate_command and lint_command are legal config keys."""
        self.assertIn("validate_command", LEGAL_CONFIG_KEYS)
        self.assertIn("lint_command", LEGAL_CONFIG_KEYS)

    def test_default_validation_commands(self):
        """Without config, resolve_validation_commands returns default make validate."""
        with tempfile.TemporaryDirectory() as tmpdir:
            validate_cmd, lint_cmd = resolve_validation_commands(repo_root=tmpdir)
            self.assertEqual(validate_cmd, ["make", "validate"])
            self.assertIsNone(lint_cmd)

    def test_project_scope_configured_commands(self):
        """Project config provides validate_command and lint_command."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agents_dir = Path(tmpdir) / ".agents"
            agents_dir.mkdir(parents=True)
            config_file = agents_dir / "aet-config.json"
            config_file.write_text(
                json.dumps(
                    {
                        "validate_command": "pytest -q -m 'not slow'",
                        "lint_command": "ruff check src",
                    }
                )
            )
            validate_cmd, lint_cmd = resolve_validation_commands(repo_root=tmpdir)
            self.assertEqual(validate_cmd, ["pytest", "-q", "-m", "not slow"])
            self.assertEqual(lint_cmd, ["ruff", "check", "src"])

    def test_user_scope_shadow_layer_resolution(self):
        """User scope config (~/.aet/<slug>/config.json) takes precedence over project."""
        from aet import user_paths
        from aet.project_id import derive_config_slug

        with tempfile.TemporaryDirectory() as tmpdir:
            slug = derive_config_slug(tmpdir)
            user_config_file = user_paths.user_config_path(slug)
            user_config_file.parent.mkdir(parents=True, exist_ok=True)
            try:
                user_config_file.write_text(
                    json.dumps({"validate_command": "pytest tests/unit"})
                )
                validate_cmd, lint_cmd = resolve_validation_commands(repo_root=tmpdir)
                self.assertEqual(validate_cmd, ["pytest", "tests/unit"])
                self.assertIsNone(lint_cmd)
            finally:
                if user_config_file.exists():
                    user_config_file.unlink()

    def test_configure_writes_validation_keys_project_scope(self):
        """aet configure --validate-command and --lint-command writes to project config."""
        from typer.testing import CliRunner

        from aet.cli.configure_backend import app

        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            import os
            cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                result = runner.invoke(
                    app,
                    [
                        "--validate-command",
                        "pytest -v",
                        "--lint-command",
                        "ruff check",
                        "--scope",
                        "project",
                    ],
                )
                self.assertEqual(result.exit_code, 0)
                config_path = Path(tmpdir) / ".agents" / "aet-config.json"
                self.assertTrue(config_path.exists())
                data = json.loads(config_path.read_text(encoding="utf-8"))
                self.assertEqual(data.get("validate_command"), "pytest -v")
                self.assertEqual(data.get("lint_command"), "ruff check")
            finally:
                os.chdir(cwd)

    def test_configure_rejects_empty_validation_command(self):
        """aet configure rejects empty or whitespace-only validate_command."""
        from typer.testing import CliRunner

        from aet.cli.configure_backend import app

        runner = CliRunner()
        result = runner.invoke(app, ["--validate-command", "   "])
        self.assertNotEqual(result.exit_code, 0)

    def test_configure_rejects_unparseable_shlex_command(self):
        """aet configure rejects unparseable shlex validate_command."""
        from typer.testing import CliRunner

        from aet.cli.configure_backend import app

        runner = CliRunner()
        result = runner.invoke(app, ["--validate-command", 'pytest "unclosed quote'])
        self.assertNotEqual(result.exit_code, 0)
