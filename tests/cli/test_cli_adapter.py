"""Tests for cli_adapter module."""


import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from aet import session_log_claude
from aet.cli_adapter import CLIAdapter, resolve_cli_adapter


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

    def test_kimi_declares_wire_file_usage_mode(self):
        """kimi usage is read post-exit from on-disk wire files; stdout
        carries only the resume hint (verified kimi 0.23.6, 2026-07-13)."""
        adapter = resolve_cli_adapter("kimi")
        self.assertEqual(adapter.usage_mode, "wire-file")

    def test_kimi_supervision_defaults_exceed_suite_silence(self):
        """kimi's stall timeout and wall backstop are adapter data (ADR-053)."""
        adapter = resolve_cli_adapter("kimi")
        self.assertGreater(adapter.stall_timeout, 300)
        self.assertGreater(adapter.wall_backstop, adapter.stall_timeout)

    def test_claude_supervision_defaults_exceed_suite_silence(self):
        """claude's stall timeout and wall backstop are adapter data (ADR-053)."""
        adapter = resolve_cli_adapter("claude")
        self.assertGreater(adapter.stall_timeout, 300)
        self.assertGreater(adapter.wall_backstop, adapter.stall_timeout)

    def test_wire_file_mode_appends_no_flags(self):
        """wire-file parsing needs no CLI flags — the tee captures the hint."""
        adapter = resolve_cli_adapter("kimi")
        cmd = adapter.build_cmd("run tests", headless=True)
        self.assertEqual(cmd, ["kimi", "-p", "run tests"])

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


class TestResolveSessionRef(unittest.TestCase):
    """Adapter-resolved session references replace the orchestrator's kimi-only gate."""

    def _write_kimi_session(self, home: Path, session_id: str) -> Path:
        session_dir = home / "sessions" / "wd_proj_abc123" / session_id
        wire = session_dir / "agents" / "main" / "wire.jsonl"
        wire.parent.mkdir(parents=True, exist_ok=True)
        wire.write_text("", encoding="utf-8")
        return session_dir

    def _write_claude_transcript(
        self, home: Path, cwd: str, session_id: str, records: list[dict]
    ) -> Path:
        transcript_dir = home / ".claude" / "projects" / session_log_claude.cwd_slug(cwd)
        transcript_dir.mkdir(parents=True, exist_ok=True)
        transcript = transcript_dir / f"{session_id}.jsonl"
        transcript.write_text(
            "\n".join(json.dumps(r) for r in records) + "\n",
            encoding="utf-8",
        )
        return transcript

    def test_kimi_session_reference_unchanged(self):
        """kimi resolution keeps using the resume-hint path; this is a regression fence."""
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            expected = self._write_kimi_session(home / ".kimi-code", "session_stub1")
            output = "To resume this session: kimi -r session_stub1\n"
            adapter = resolve_cli_adapter("kimi")
            with patch("pathlib.Path.home", return_value=home):
                ref = adapter.resolve_session_ref(output)
            self.assertEqual(ref, expected)

    def test_claude_session_reference_resolved_from_envelope_session_id(self):
        """Claude resolves by session_id from the envelope confirmed against cwd."""
        envelope = (
            '[{"type":"system","subtype":"init","session_id":"s1","cwd":"/tmp/proj"},'
            '{"type":"result","subtype":"success","is_error":false,"session_id":"s1",'
            '"usage":{"input_tokens":2,"output_tokens":4}}]'
        )
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            adapter = resolve_cli_adapter("claude")
            expected = self._write_claude_transcript(
                home,
                "/tmp/proj",
                "s1",
                [{"cwd": "/tmp/proj", "session_id": "s1"}],
            )
            with patch("pathlib.Path.home", return_value=home):
                ref = adapter.resolve_session_ref(envelope, workdir="/tmp/proj")
            self.assertEqual(ref, expected)

    def test_claude_session_reference_resolved_from_single_object_envelope(self):
        """`--output-format json` emits one object, not a list — the shipped shape."""
        envelope = json.dumps(
            {
                "type": "result",
                "subtype": "success",
                "is_error": False,
                "session_id": "s9",
                "result": "done",
                "usage": {"input_tokens": 2, "output_tokens": 4},
            }
        )
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            adapter = resolve_cli_adapter("claude")
            expected = self._write_claude_transcript(
                home, "/tmp/proj", "s9", [{"cwd": "/tmp/proj", "session_id": "s9"}]
            )
            with patch("pathlib.Path.home", return_value=home):
                ref = adapter.resolve_session_ref(envelope, workdir="/tmp/proj")
            self.assertEqual(ref, expected)

    def test_claude_session_reference_survives_log_noise_before_envelope(self):
        """A captured tail carries CLI chatter ahead of the envelope."""
        envelope = json.dumps(
            {"type": "result", "subtype": "success", "session_id": "s9", "usage": {}}
        )
        noisy = "starting stage...\nwarming worktree\n" + envelope
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            adapter = resolve_cli_adapter("claude")
            expected = self._write_claude_transcript(
                home, "/tmp/proj", "s9", [{"cwd": "/tmp/proj", "session_id": "s9"}]
            )
            with patch("pathlib.Path.home", return_value=home):
                ref = adapter.resolve_session_ref(noisy, workdir="/tmp/proj")
            self.assertEqual(ref, expected)

    def test_claude_session_reference_null_when_cwd_mismatches(self):
        """A transcript at the expected path whose own cwd disagrees is not a match."""
        envelope = (
            '[{"type":"system","subtype":"init","session_id":"s1","cwd":"/tmp/proj"},'
            '{"type":"result","subtype":"success","is_error":false,"session_id":"s1",'
            '"usage":{"input_tokens":2,"output_tokens":4}}]'
        )
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            adapter = resolve_cli_adapter("claude")
            # Written at the slug the resolver will look under, but every record
            # inside claims a different cwd — the confirmation must reject it.
            self._write_claude_transcript(
                home,
                "/tmp/proj",
                "s1",
                [{"cwd": "/tmp/other", "session_id": "s1"}],
            )
            with patch("pathlib.Path.home", return_value=home):
                ref = adapter.resolve_session_ref(envelope, workdir="/tmp/proj")
            self.assertIsNone(ref)

    def test_claude_session_reference_null_when_transcript_missing(self):
        """A resolvable session_id with no transcript on disk yields no guess."""
        envelope = (
            '[{"type":"result","subtype":"success","is_error":false,'
            '"session_id":"s1","usage":{"input_tokens":2,"output_tokens":4}}]'
        )
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            adapter = resolve_cli_adapter("claude")
            with patch("pathlib.Path.home", return_value=home):
                ref = adapter.resolve_session_ref(envelope, workdir="/tmp/proj")
            self.assertIsNone(ref)

    def test_claude_session_reference_null_when_envelope_unparseable(self):
        adapter = resolve_cli_adapter("claude")
        ref = adapter.resolve_session_ref("not valid json", workdir="/tmp/proj")
        self.assertIsNone(ref)

    def test_unknown_adapter_returns_none_session_reference(self):
        adapter = CLIAdapter(
            name="custom", bin="custom", prompt_flag="-p", workdir_flag=None, headless_flag=None
        )
        self.assertIsNone(adapter.resolve_session_ref("any output", workdir="/tmp/proj"))


if __name__ == "__main__":
    unittest.main()
