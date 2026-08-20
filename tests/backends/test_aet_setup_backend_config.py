"""Tests for the `aet configure` config writer after backend removal."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]
SCRIPT = REPO_ROOT / "src" / "aet" / "cli" / "configure_backend.py"


class TestConfigureTaskBackend(unittest.TestCase):
    """Behavior-driven tests for `aet configure` after task_backend removal."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name) / "project"
        self.project.mkdir()
        self.home = Path(self.tmp.name) / "home"
        self.home.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def run_script(self, args=None, env=None, cwd=None, input_text=None):
        """Run the configure helper and return CompletedProcess."""
        cmd = [sys.executable, str(SCRIPT)]
        if args:
            cmd.extend(args)
        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)
        return subprocess.run(
            cmd,
            cwd=cwd or self.project,
            env=merged_env,
            capture_output=True,
            text=True,
            input=input_text,
        )

    def read_config(self):
        """Read the generated .agents/aet-config.json."""
        path = self.project / ".agents" / "aet-config.json"
        self.assertTrue(path.exists(), f"Expected config file: {path}")
        return json.loads(path.read_text())

    def test_help_prints_usage(self):
        result = self.run_script(["--help"])
        self.assertEqual(result.returncode, 0)
        self.assertIn("Configure the AET project config", result.stdout)

    def test_no_backend_flag_writes_integration_mode(self):
        result = self.run_script(
            ["--integration-mode", "single-pr", "--non-interactive", "--scope", "project"]
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        config = self.read_config()
        self.assertEqual(config["integration_mode"], "single-pr")
        self.assertNotIn("task_backend", config)

    def test_removed_task_backend_flag_is_rejected(self):
        result = self.run_script(
            ["--task-backend", "git-refs", "--non-interactive", "--scope", "project"]
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no such option", result.stderr.lower())
        self.assertFalse((self.project / ".agents" / "aet-config.json").exists())

    def test_existing_task_backend_key_is_stripped_on_write(self):
        agents = self.project / ".agents"
        agents.mkdir()
        existing = {"task_backend": "git-refs", "integration_mode": "pr-per-task"}
        (agents / "aet-config.json").write_text(json.dumps(existing))
        result = self.run_script(
            ["--trunk-branch", "main", "--non-interactive", "--scope", "project"]
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        config = self.read_config()
        self.assertNotIn("task_backend", config)
        self.assertEqual(config["trunk_branch"], "main")
        self.assertEqual(config["integration_mode"], "pr-per-task")


if __name__ == "__main__":
    unittest.main()
