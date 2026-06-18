"""Tests for cli_adapter module."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "aet-work" / "lib"))

import unittest

from cli_adapter import CLIAdapter, resolve_cli_adapter


class TestCLIAdapter(unittest.TestCase):
    def test_kimi_adapter(self):
        adapter = resolve_cli_adapter("kimi")
        self.assertEqual(adapter.name, "kimi")
        self.assertEqual(adapter.bin, "kimi")
        self.assertEqual(adapter.prompt_flag, "-p")
        self.assertIsNone(adapter.workdir_flag)
        self.assertEqual(adapter.headless_flag, "")

    def test_claude_adapter(self):
        adapter = resolve_cli_adapter("claude")
        self.assertEqual(adapter.name, "claude")
        self.assertEqual(adapter.bin, "claude")
        self.assertEqual(adapter.prompt_flag, "-p")
        self.assertIsNone(adapter.workdir_flag)
        self.assertEqual(adapter.headless_flag, "--dangerously-skip-permissions")

    def test_build_cmd(self):
        adapter = CLIAdapter(
            name="test",
            bin="test",
            prompt_flag="-p",
            workdir_flag="--cwd",
            headless_flag="--headless",
        )
        cmd = adapter.build_cmd("run tests", workdir="/tmp/proj", headless=True)
        self.assertEqual(cmd, ["test", "--headless", "-p", "run tests", "--cwd", "/tmp/proj"])

    def test_build_cmd_no_workdir_flag(self):
        """When workdir_flag is None, cwd is omitted (handled by subprocess)."""
        adapter = CLIAdapter(
            name="test", bin="test", prompt_flag="-p", workdir_flag=None, headless_flag="--headless"
        )
        cmd = adapter.build_cmd("run tests", workdir="/tmp/proj", headless=True)
        self.assertEqual(cmd, ["test", "--headless", "-p", "run tests"])

    def test_kimi_headless_build_cmd(self):
        """Regression: kimi -p mode cannot combine with --yolo or --auto."""
        adapter = resolve_cli_adapter("kimi")
        cmd = adapter.build_cmd("run tests", headless=True)
        self.assertNotIn("--yolo", cmd)
        self.assertNotIn("--auto", cmd)
        self.assertEqual(cmd, ["kimi", "-p", "run tests"])

    def test_build_cmd_no_headless(self):
        adapter = CLIAdapter(
            name="test", bin="test", prompt_flag="-p", workdir_flag="", headless_flag=""
        )
        cmd = adapter.build_cmd("run tests")
        self.assertEqual(cmd, ["test", "-p", "run tests"])

    def test_unsupported_cli_raises(self):
        with self.assertRaises(ValueError) as ctx:
            resolve_cli_adapter("nonexistent")
        self.assertIn("nonexistent", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
