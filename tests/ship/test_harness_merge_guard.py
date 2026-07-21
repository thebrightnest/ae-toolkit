"""Tests for the per-provider merge guard harness detection and adapters."""

import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]
SCRIPT = REPO_ROOT / "src" / "aet" / "cli" / "harness_guard.py"
_HARNESS_GUARD_PY = REPO_ROOT / "src" / "aet" / "harness_guard.py"

_spec = importlib.util.spec_from_loader(
    "harness_guard",
    importlib.machinery.SourceFileLoader("harness_guard", str(_HARNESS_GUARD_PY)),
)
harness_guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(harness_guard)


class TestHarnessDetection(unittest.TestCase):
    """Behavior-driven tests for active-harness detection."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name) / "project"
        self.project.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_detects_claude_code_from_marker(self):
        """A .claude/ directory in the project root resolves to claude-code."""
        (self.project / ".claude").mkdir()
        harness = harness_guard.detect_harness(self.project)
        self.assertEqual(harness, "claude-code")

    def test_detects_kimi_from_marker(self):
        """A .kimi-code/ directory in the project root resolves to kimi."""
        (self.project / ".kimi-code").mkdir()
        harness = harness_guard.detect_harness(self.project)
        self.assertEqual(harness, "kimi")

    def test_explicit_override_beats_detection(self):
        """An explicit harness id overrides filesystem markers."""
        (self.project / ".claude").mkdir()
        harness = harness_guard.detect_harness(self.project, override="kimi")
        self.assertEqual(harness, "kimi")

    def test_unknown_marker_is_none(self):
        """No recognized markers yields None so the caller can fail safe."""
        harness = harness_guard.detect_harness(self.project)
        self.assertIsNone(harness)


class TestClaudeMergeGuard(unittest.TestCase):
    """Behavior-driven tests for the Claude Code PreToolUse merge guard."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name) / "project"
        self.project.mkdir()
        (self.project / ".claude").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def _load_guard(self):
        """Return the generated guard as a Python dict."""
        settings_path = self.project / ".claude" / "settings.json"
        self.assertTrue(settings_path.exists())
        return json.loads(settings_path.read_text())

    def _run_guard(self, command):
        """Simulate a PreToolUse hook invocation for a Bash command."""
        settings = self._load_guard()
        script_rel = settings["hooks"]["PreToolUse"][0]
        script_path = self.project / script_rel
        payload = {
            "tool_name": "Bash",
            "input": {"command": command},
        }
        result = subprocess.run(
            [sys.executable, str(script_path)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            cwd=self.project,
        )
        return result.returncode, result.stdout, result.stderr

    def test_claude_guard_refuses_gh_pr_merge(self):
        """The generated guard blocks a Bash tool call matching gh pr merge."""
        harness_guard.install_merge_guard(self.project)
        rc, _stdout, stderr = self._run_guard("gh pr merge --squash 123")
        self.assertNotEqual(rc, 0)
        self.assertIn("merge", stderr.lower())

    def test_guard_ignores_git_push_and_desk_merge(self):
        """The guard allows git push and aet desk merge."""
        harness_guard.install_merge_guard(self.project)
        for command in ["git push origin feature-branch", "aet desk merge"]:
            with self.subTest(command=command):
                rc, _stdout, _stderr = self._run_guard(command)
                self.assertEqual(rc, 0)

    def test_guard_install_is_idempotent_and_non_clobbering(self):
        """Repeated install succeeds and does not overwrite a non-AET file."""
        harness_guard.install_merge_guard(self.project)
        first = self._load_guard()
        harness_guard.install_merge_guard(self.project)
        second = self._load_guard()
        self.assertEqual(first, second)

        # A non-AET settings file is left untouched.
        foreign = '{"project": "name"}'
        settings_path = self.project / ".claude" / "settings.json"
        settings_path.write_text(foreign)
        rc = harness_guard.install_merge_guard(self.project)
        self.assertNotEqual(rc, 0)
        self.assertEqual(settings_path.read_text(), foreign)

    def test_unsupported_harness_named_gap_nonzero(self):
        """An unsupported harness exits non-zero with a named gap message."""
        # Remove the Claude marker so detection falls through to the unsupported harness.
        (self.project / ".claude").rmdir()
        (self.project / ".kimi-code").mkdir()
        rc = harness_guard.install_merge_guard(self.project)
        self.assertNotEqual(rc, 0)


class TestHarnessGuardCLI(unittest.TestCase):
    """Behavior-driven tests for the harness-guard CLI."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name) / "project"
        self.project.mkdir()
        (self.project / ".claude").mkdir()
        subprocess.run(
            ["git", "init", "--quiet"],
            cwd=self.project,
            check=True,
            capture_output=True,
        )

    def tearDown(self):
        self.tmp.cleanup()

    def run_script(self, args=None, env=None, cwd=None, input_text=None):
        """Run the harness-guard helper and return CompletedProcess."""
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

    def test_cli_install_detects_and_writes_guard(self):
        """`harness-guard install` detects the harness and writes the guard."""
        result = self.run_script(["install"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.project / ".claude" / "settings.json").exists())

    def test_cli_check_reports_installed_guard(self):
        """`harness-guard check` reports the installed harness guard."""
        self.run_script(["install"])
        result = self.run_script(["check"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("claude-code", result.stdout)
