"""Tests for non-invasive external config resolution."""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).parent.parent
SCRIPT = REPO_ROOT / "aet-setup" / "bin" / "configure-task-backend"


from aet.backends.factory import create_backend  # noqa: E402
from aet.backends.git_refs_backend import GitRefsBackend  # noqa: E402
from aet.backends.json_backend import JsonBackend  # noqa: E402


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
        path = self.project / ".agents" / "aet-work.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(config), encoding="utf-8")

    def _write_external(self, slug, config):
        path = self.home / ".aet" / slug / "config.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(config), encoding="utf-8")

    def test_default_when_no_config_present(self):
        with patch.dict(os.environ, {"HOME": str(self.home)}, clear=False):
            backend = create_backend(
                config_path=str(self.project / ".agents" / "aet-work.json"),
                queue_file=str(self.project / "work-queue.json"),
                history_file=str(self.project / "work-history.jsonl"),
            )
        self.assertIsInstance(backend, JsonBackend)

    def test_in_tree_config_resolves_unchanged(self):
        self._write_in_tree({"task_backend": "git-refs"})
        with patch.dict(os.environ, {"HOME": str(self.home)}, clear=False):
            backend = create_backend(
                config_path=str(self.project / ".agents" / "aet-work.json"),
                queue_file=str(self.project / "work-queue.json"),
                history_file=str(self.project / "work-history.jsonl"),
            )
        self.assertIsInstance(backend, GitRefsBackend)

    def test_external_config_resolves_under_home_aet_slug(self):
        with patch.dict(
            os.environ,
            {"HOME": str(self.home), "AET_PROJECT_ID": "myproject/main"},
            clear=False,
        ):
            self._write_external("myproject/main", {"task_backend": "git-refs"})
            self._write_in_tree({"task_backend": "json"})
            backend = create_backend(
                config_path=str(self.project / ".agents" / "aet-work.json"),
                queue_file=str(self.project / "work-queue.json"),
                history_file=str(self.project / "work-history.jsonl"),
            )
        self.assertIsInstance(backend, GitRefsBackend)

    def test_precedence_env_over_external_over_in_tree(self):
        env_config = self.home / "env-config.json"
        env_config.write_text(json.dumps({"task_backend": "json"}), encoding="utf-8")

        with patch.dict(
            os.environ,
            {
                "HOME": str(self.home),
                "AET_PROJECT_ID": "myproject/main",
                "AET_WORK_CONFIG": str(env_config),
            },
            clear=False,
        ):
            self._write_external("myproject/main", {"task_backend": "git-refs"})
            self._write_in_tree({"task_backend": "git-refs"})
            backend = create_backend(
                config_path=str(self.project / ".agents" / "aet-work.json"),
                queue_file=str(self.project / "work-queue.json"),
                history_file=str(self.project / "work-history.jsonl"),
            )
        self.assertIsInstance(backend, JsonBackend)

    def test_noninvasive_setup_leaves_tracked_tree_free_of_aet_config(self):
        env = os.environ.copy()
        env["HOME"] = str(self.home)
        env["AET_PROJECT_ID"] = "noninvasive-project"

        result = subprocess.run(
            [
                str(SCRIPT),
                "--backend",
                "json",
                "--non-interactive",
                "--external-config",
            ],
            cwd=self.project,
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

        in_tree = self.project / ".agents" / "aet-work.json"
        self.assertFalse(in_tree.exists(), "non-invasive setup must not write in-tree config")

        external = self.home / ".aet" / "noninvasive-project" / "config.json"
        self.assertTrue(external.exists(), "external config must be written")
        config = json.loads(external.read_text(encoding="utf-8"))
        self.assertEqual(config["task_backend"], "json")

        self.assertIn("resolution order", result.stderr.lower())


if __name__ == "__main__":
    unittest.main()
