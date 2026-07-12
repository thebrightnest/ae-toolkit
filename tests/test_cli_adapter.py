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
        self.assertIsNone(adapter.headless_flag)

    def test_kimi_build_cmd_no_headless_flag(self):
        """kimi rejects combining -p/--prompt with --yolo; use -p alone."""
        adapter = resolve_cli_adapter("kimi")
        cmd = adapter.build_cmd("run tests", headless=True)
        self.assertEqual(cmd, ["kimi", "-p", "run tests"])
        self.assertNotIn("--yolo", cmd)

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

    def test_build_cmd_no_headless_flag(self):
        adapter = CLIAdapter(
            name="test", bin="test", prompt_flag="-p", workdir_flag="", headless_flag=None
        )
        cmd = adapter.build_cmd("run tests", headless=True)
        self.assertEqual(cmd, ["test", "-p", "run tests"])

    def test_unsupported_cli_raises(self):
        with self.assertRaises(ValueError) as ctx:
            resolve_cli_adapter("nonexistent")
        self.assertIn("nonexistent", str(ctx.exception))

    def test_claude_declares_json_envelope_usage_mode(self):
        """claude's headless usage data rides in its JSON output envelope."""
        adapter = resolve_cli_adapter("claude")
        self.assertEqual(adapter.usage_mode, "json-envelope")

    def test_kimi_has_no_usage_mode(self):
        """kimi's headless output carries no usage data (verified 2026-07-12)."""
        adapter = resolve_cli_adapter("kimi")
        self.assertIsNone(adapter.usage_mode)

    def test_usage_mode_flags_appended_when_headless(self):
        adapter = CLIAdapter(
            name="test",
            bin="test",
            prompt_flag="-p",
            workdir_flag=None,
            headless_flag="--headless",
            usage_mode="json-envelope",
        )
        cmd = adapter.build_cmd("run tests", headless=True)
        # Usage flags land before the prompt flag: some CLIs treat the token
        # after -p as the prompt value, so trailing flags are unsafe.
        self.assertEqual(
            cmd, ["test", "--headless", "--output-format", "json", "-p", "run tests"]
        )

    def test_usage_mode_flags_omitted_when_not_headless(self):
        adapter = CLIAdapter(
            name="test",
            bin="test",
            prompt_flag="-p",
            workdir_flag=None,
            headless_flag="--headless",
            usage_mode="json-envelope",
        )
        cmd = adapter.build_cmd("run tests", headless=False)
        self.assertEqual(cmd, ["test", "-p", "run tests"])

    def test_no_usage_mode_appends_nothing(self):
        adapter = CLIAdapter(
            name="test", bin="test", prompt_flag="-p", workdir_flag=None, headless_flag=None
        )
        self.assertIsNone(adapter.usage_mode)
        self.assertEqual(adapter.build_cmd("run tests", headless=True), ["test", "-p", "run tests"])


if __name__ == "__main__":
    unittest.main()
