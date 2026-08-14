"""Tests for the `aet configure` task-backend configuration helper."""

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
    """Behavior-driven tests for `aet configure` task-backend writes."""

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

    def test_json_backend_creates_config(self):
        result = self.run_script(
            ["--task-backend", "json", "--non-interactive", "--scope", "project"]
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        config = self.read_config()
        self.assertEqual(config["task_backend"], "json")
        # json is the documented opt-out; the NOTE explains when it applies.
        self.assertIn("non-git", result.stderr.lower())

    def test_no_backend_flag_writes_git_refs_default(self):
        result = self.run_script(["--non-interactive", "--scope", "project"])
        self.assertEqual(result.returncode, 0, result.stderr)
        config = self.read_config()
        self.assertEqual(config["task_backend"], "git-refs")

    def test_interactive_empty_input_writes_git_refs_default(self):
        result = self.run_script(["--scope", "project"], input_text="\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        config = self.read_config()
        self.assertEqual(config["task_backend"], "git-refs")

    def test_git_refs_backend_creates_config_without_prototype_framing(self):
        result = self.run_script(
            ["--task-backend", "git-refs", "--non-interactive", "--scope", "project"]
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        config = self.read_config()
        self.assertEqual(config["task_backend"], "git-refs")
        # git-refs is local-only; no github mirror is configured.
        self.assertNotIn("github", config)
        # git-refs is the default written backend, so the selection path must
        # not carry the stale prototype/opt-in framing.
        stderr = result.stderr.lower()
        self.assertNotIn("prototype", stderr)
        self.assertNotIn("opt-in", stderr)
        self.assertNotIn("not recommended", stderr)

    def test_factory_no_config_fallback_remains_json(self):
        # Guards the rejected factory-level flip: aet-setup writes git-refs by
        # default, but the no-config factory fallback must stay JsonBackend.
        # The temp project basename can collide with a real ~/.aet/{slug}/
        # config, so HOME must be isolated to guarantee the fallback path.
        from unittest.mock import patch

        from aet.backends.factory import create_backend
        from aet.backends.json_backend import JsonBackend

        with patch.dict("os.environ", {"HOME": str(self.home)}):
            backend = create_backend(
                config_path=str(self.project / "missing.json"),
                queue_file=str(self.project / "work-queue.json"),
                history_file=str(self.project / "work-history.jsonl"),
            )
        self.assertIsInstance(backend, JsonBackend)

    def test_github_backend_is_rejected(self):
        # GitHub Issues is a projection, not a storage backend.
        result = self.run_script(
            ["--task-backend", "github", "--non-interactive", "--scope", "project"]
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("projections", result.stderr.lower())
        # No config should be written when the backend is invalid.
        self.assertFalse((self.project / ".agents" / "aet-config.json").exists())

    def test_both_backend_is_rejected(self):
        result = self.run_script(
            ["--task-backend", "both", "--non-interactive", "--scope", "project"]
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("projections", result.stderr.lower())

    def test_invalid_backend_fails(self):
        result = self.run_script(
            ["--task-backend", "gitlab", "--non-interactive", "--scope", "project"]
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("json", result.stderr)
        self.assertIn("git-refs", result.stderr)
        self.assertNotIn("github", result.stderr)

    def test_forward_only_switch_warns_and_does_not_migrate(self):
        agents = self.project / ".agents"
        agents.mkdir()
        existing = {
            "task_backend": "json",
        }
        (agents / "aet-config.json").write_text(json.dumps(existing))
        result = self.run_script(
            ["--task-backend", "git-refs", "--non-interactive", "--scope", "project"]
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("forward-only", result.stderr.lower())
        config = self.read_config()
        self.assertEqual(config["task_backend"], "git-refs")
        self.assertIn("switch_warning", config)


if __name__ == "__main__":
    unittest.main()
