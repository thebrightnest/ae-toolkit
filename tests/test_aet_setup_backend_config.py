"""Tests for the aet-setup task-backend configuration helper."""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).parent.parent
SCRIPT = REPO_ROOT / "aet-setup" / "bin" / "configure-task-backend"


class TestConfigureTaskBackend(unittest.TestCase):
    """Behavior-driven tests for configure-task-backend."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name) / "project"
        self.project.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def run_script(self, args=None, env=None, cwd=None, input_text=None):
        """Run the configure helper and return CompletedProcess."""
        cmd = [str(SCRIPT)]
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
        """Read the generated .agents/aet-work.json."""
        path = self.project / ".agents" / "aet-work.json"
        self.assertTrue(path.exists(), f"Expected config file: {path}")
        return json.loads(path.read_text())

    def test_help_prints_usage(self):
        result = self.run_script(["--help"])
        self.assertEqual(result.returncode, 0)
        self.assertIn("configure-task-backend", result.stdout)

    def test_json_backend_creates_config(self):
        result = self.run_script(["--backend", "json", "--non-interactive"])
        self.assertEqual(result.returncode, 0, result.stderr)
        config = self.read_config()
        self.assertEqual(config["task_backend"], "json")

    def test_github_backend_with_explicit_repo_creates_config(self):
        result = self.run_script(
            ["--backend", "github", "--repo", "acme/widget", "--non-interactive"]
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        config = self.read_config()
        self.assertEqual(config["task_backend"], "github")
        self.assertEqual(config["github"]["repo"], "acme/widget")
        self.assertEqual(config["github"].get("label_prefix"), "aet")

    def test_github_backend_detects_repo_from_git_remote(self):
        subprocess.run(["git", "init"], cwd=self.project, check=True, capture_output=True)
        subprocess.run(
            ["git", "remote", "add", "origin", "git@github.com:detected/repo.git"],
            cwd=self.project,
            check=True,
            capture_output=True,
        )
        result = self.run_script(["--backend", "github", "--non-interactive"])
        self.assertEqual(result.returncode, 0, result.stderr)
        config = self.read_config()
        self.assertEqual(config["github"]["repo"], "detected/repo")

    def test_github_backend_without_gh_cli_records_label_warning(self):
        env = {"PATH": "/usr/bin:/bin"}  # no gh
        result = self.run_script(
            ["--backend", "github", "--repo", "acme/widget", "--non-interactive"],
            env=env,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("gh", result.stderr.lower())
        config = self.read_config()
        self.assertFalse(config["github"].get("labels_created", True))
        self.assertIn("reason", config["github"])

    def test_github_backend_creates_labels_when_gh_available(self):
        fake_gh = self._make_fake_gh(labels=[])
        env = {"PATH": f"{fake_gh.parent}:{os.environ.get('PATH', '')}"}
        result = self.run_script(
            ["--backend", "github", "--repo", "acme/widget", "--non-interactive"],
            env=env,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        config = self.read_config()
        self.assertTrue(config["github"].get("labels_created", False))
        created = json.loads((fake_gh.parent / "labels.json").read_text())
        labels = [label["name"] for label in created]
        self.assertIn("aet:ready", labels)
        self.assertIn("aet:planned", labels)
        self.assertIn("aet:blocked", labels)

    def test_invalid_backend_fails(self):
        result = self.run_script(["--backend", "gitlab", "--non-interactive"])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("json", result.stderr)
        self.assertIn("github", result.stderr)

    def test_forward_only_switch_warns_and_does_not_migrate(self):
        agents = self.project / ".agents"
        agents.mkdir()
        existing = {
            "task_backend": "json",
            "github": {"repo": "old/repo"},
        }
        (agents / "aet-work.json").write_text(json.dumps(existing))
        result = self.run_script(["--backend", "github", "--repo", "new/repo", "--non-interactive"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("forward-only", result.stderr.lower())
        config = self.read_config()
        self.assertEqual(config["task_backend"], "github")
        self.assertEqual(config["github"]["repo"], "new/repo")
        self.assertIn("switch_warning", config)

    def _make_fake_gh(self, labels=None):
        """Create a fake gh binary that records label-create calls."""
        fake_bin = Path(self.tmp.name) / "fake-bin"
        fake_bin.mkdir()
        fake_gh = fake_bin / "gh"
        fake_gh.write_text(
            '#!/usr/bin/env bash\n'
            'set -euo pipefail\n'
            'STATE_FILE="' + str(fake_bin / "labels.json") + '"\n'
            'if [ "$1" = "auth" ] && [ "$2" = "status" ]; then\n'
            '  exit 0\n'
            'fi\n'
            'if [ "$1" = "label" ] && [ "$2" = "create" ]; then\n'
            '  shift 2\n'
            '  name=""\n'
            '  color=""\n'
            '  desc=""\n'
            '  while [ $# -gt 0 ]; do\n'
            '    case "$1" in\n'
            '      --name) name="$2"; shift 2;;\n'
            '      --color) color="$2"; shift 2;;\n'
            '      --description) desc="$2"; shift 2;;\n'
            '      *) shift;;\n'
            '    esac\n'
            '  done\n'
            '  if [ ! -f "$STATE_FILE" ]; then echo "[]" > "$STATE_FILE"; fi\n'
            '  python3 -c "import json; data=json.load(open(\"$STATE_FILE\")); data.append({\"name\":\"$name\",\"color\":\"$color\",\"description\":\"$desc\"}); json.dump(data, open(\"$STATE_FILE\",\"w\"))"\n'
            '  exit 0\n'
            'fi\n'
            'echo "fake-gh: unhandled $*" >&2\n'
            'exit 1\n'
        )
        fake_gh.chmod(0o755)
        return fake_gh


if __name__ == "__main__":
    unittest.main()
