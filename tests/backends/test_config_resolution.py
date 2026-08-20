"""Tests for non-invasive external config resolution."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).parents[2]
SCRIPT = REPO_ROOT / "src" / "aet" / "cli" / "configure_backend.py"


from aet.backends.factory import (  # noqa: E402
    LegacyTaskBackendError,
    create_backend,
)
from aet.backends.git_refs_backend import GitRefsBackend  # noqa: E402


class TestConfigResolution(unittest.TestCase):
    """Behavior-driven tests for external-first config precedence."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name) / "project"
        self.project.mkdir()
        self.home = Path(self.tmp.name) / "home"
        self.home.mkdir()
        # GitRefsBackend requires the queue path to live inside a git repo.
        subprocess.run(
            ["git", "init", "-q", str(self.project)],
            check=True,
            capture_output=True,
        )

    def tearDown(self):
        self.tmp.cleanup()

    def _write_in_tree(self, config):
        path = self.project / ".agents" / "aet-config.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(config), encoding="utf-8")

    def _write_external(self, slug, config):
        path = self.home / ".aet" / slug / "config.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(config), encoding="utf-8")

    def _patch_home(self):
        return patch.dict(
            os.environ,
            {"HOME": str(self.home)},
            clear=True,
        )

    def test_default_when_no_config_present(self):
        with self._patch_home():
            backend = create_backend(
                config_path=str(self.project / ".agents" / "aet-config.json"),
                queue_file=str(self.project / ".agents" / "aet-queue"),
                history_file=str(self.project / ".agents" / "work-history.jsonl"),
            )
        self.assertIsInstance(backend, GitRefsBackend)

    def test_in_tree_config_resolves_unchanged(self):
        self._write_in_tree({"integration_mode": "single-pr"})
        with self._patch_home():
            backend = create_backend(
                config_path=str(self.project / ".agents" / "aet-config.json"),
                queue_file=str(self.project / ".agents" / "aet-queue"),
                history_file=str(self.project / ".agents" / "work-history.jsonl"),
            )
        self.assertIsInstance(backend, GitRefsBackend)

    def test_external_config_resolves_under_home_aet_slug(self):
        with patch.dict(
            os.environ,
            {"HOME": str(self.home), "AET_PROJECT_ID": "myproject/main"},
            clear=True,
        ):
            self._write_external("myproject/main", {"integration_mode": "single-pr"})
            self._write_in_tree({"integration_mode": "pr-per-task"})
            backend = create_backend(
                config_path=str(self.project / ".agents" / "aet-config.json"),
                queue_file=str(self.project / ".agents" / "aet-queue"),
                history_file=str(self.project / ".agents" / "work-history.jsonl"),
            )
        self.assertIsInstance(backend, GitRefsBackend)

    def test_precedence_env_over_external_over_in_tree(self):
        env_config = self.home / "env-config.json"
        env_config.write_text(
            json.dumps({"integration_mode": "pr-per-task"}), encoding="utf-8"
        )

        with patch.dict(
            os.environ,
            {
                "HOME": str(self.home),
                "AET_PROJECT_ID": "myproject/main",
                "AET_WORK_CONFIG": str(env_config),
            },
            clear=True,
        ):
            self._write_external("myproject/main", {"integration_mode": "single-pr"})
            self._write_in_tree({"integration_mode": "single-pr"})
            backend = create_backend(
                config_path=str(self.project / ".agents" / "aet-config.json"),
                queue_file=str(self.project / ".agents" / "aet-queue"),
                history_file=str(self.project / ".agents" / "work-history.jsonl"),
            )
        self.assertIsInstance(backend, GitRefsBackend)

    def test_task_backend_key_fails_with_migration_message(self):
        self._write_in_tree({"task_backend": "git-refs"})
        with self._patch_home():
            with self.assertRaises(LegacyTaskBackendError) as ctx:
                create_backend(
                    config_path=str(self.project / ".agents" / "aet-config.json"),
                    queue_file=str(self.project / ".agents" / "aet-queue"),
                    history_file=str(self.project / ".agents" / "work-history.jsonl"),
                )
        self.assertIn("migration", str(ctx.exception).lower())

    def test_noninvasive_setup_leaves_tracked_tree_free_of_aet_config(self):
        env = os.environ.copy()
        env["HOME"] = str(self.home)
        env["AET_PROJECT_ID"] = "noninvasive-project"

        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--integration-mode",
                "single-pr",
                "--non-interactive",
                "--scope",
                "user",
            ],
            cwd=self.project,
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

        in_tree = self.project / ".agents" / "aet-config.json"
        self.assertFalse(in_tree.exists(), "non-invasive setup must not write in-tree config")

        external = self.home / ".aet" / "noninvasive-project" / "config.json"
        self.assertTrue(external.exists(), "external config must be written")
        config = json.loads(external.read_text(encoding="utf-8"))
        self.assertEqual(config["integration_mode"], "single-pr")
        self.assertNotIn("task_backend", config)

        self.assertIn("resolution order", result.stderr.lower())

    def test_configure_rejects_removed_task_backend_flag(self):
        env = os.environ.copy()
        env["HOME"] = str(self.home)

        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--task-backend",
                "git-refs",
                "--non-interactive",
            ],
            cwd=self.project,
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 2, result.stderr)


if __name__ == "__main__":
    unittest.main()
