"""Tests for the adapter-dispatched session-log reader seam."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from aet import session_log, session_log_claude, wirelog


def _fixture_path(name: str) -> Path:
    return Path(__file__).parents[1] / "fixtures" / "session_logs" / name


CLAUDE_TRANSCRIPT = _fixture_path("claude") / "transcript.jsonl"


class TestKimiRegression:
    """R-4: the kimi reader behind the seam yields byte-identical output."""

    def test_kimi_fixture_replay_matches_pre_change_output(self):
        session_dir = _fixture_path("kimi")
        expected = [
            {
                "command": "python3 -m pytest tests/ -q",
                "start_time": "2026-07-14T17:23:20Z",
                "end_time": "2026-07-14T17:24:05Z",
                "duration_seconds": 45.0,
                "exit_code": 0,
            },
            {
                "command": "pytest tests/",
                "start_time": "2026-07-14T17:25:00Z",
                "end_time": "2026-07-14T17:26:00Z",
                "duration_seconds": 60.0,
                "exit_code": 1,
            },
            {
                "command": "pytest tests/test_unpaired.py",
                "start_time": "2026-07-14T17:26:40Z",
                "end_time": None,
                "duration_seconds": None,
                "exit_code": None,
            },
        ]
        assert wirelog.extract_test_invocations(session_dir) == expected


class TestDispatch:
    """R-4 seam behaviour: one call site keyed on agent_cli."""

    def test_dispatch_selects_reader_by_agent_cli(self):
        assert session_log.extract_test_invocations("kimi", _fixture_path("kimi"))
        assert session_log.extract_test_invocations("claude", CLAUDE_TRANSCRIPT)

    def test_dispatch_returns_empty_for_adapter_without_reader(self):
        """ADR-050 decision 4: an unsupported CLI resolves to no records."""
        assert session_log.extract_test_invocations("unknown", _fixture_path("kimi")) == []


class TestClaudeReader:
    """R-5: Claude Code transcript parsing."""

    def test_claude_reader_pairs_tool_use_and_tool_result(self):
        invocations = session_log_claude.extract_test_invocations(CLAUDE_TRANSCRIPT)
        commands = [inv["command"] for inv in invocations]
        assert "python3 -m pytest tests/ -q" in commands
        assert "pytest tests/" in commands
        assert "pytest tests/test_unpaired.py" in commands

    def test_claude_reader_derives_iso_timestamps_and_duration(self):
        invocations = session_log_claude.extract_test_invocations(CLAUDE_TRANSCRIPT)
        paired = [inv for inv in invocations if inv["end_time"] is not None]
        assert len(paired) == 2
        inv = next(inv for inv in paired if inv["command"] == "python3 -m pytest tests/ -q")
        assert inv["start_time"] == "2026-07-14T17:23:20Z"
        assert inv["end_time"] == "2026-07-14T17:24:05Z"
        assert inv["duration_seconds"] == 45.0

    def test_claude_reader_maps_is_error_to_exit_status(self):
        invocations = session_log_claude.extract_test_invocations(CLAUDE_TRANSCRIPT)
        passing = next(inv for inv in invocations if inv["command"] == "python3 -m pytest tests/ -q")
        failing = next(inv for inv in invocations if inv["command"] == "pytest tests/" and inv["end_time"] is not None)
        assert passing["exit_code"] == 0
        assert failing["exit_code"] == 1

    def test_claude_reader_emits_null_end_and_duration_for_unpaired_call(self):
        invocations = session_log_claude.extract_test_invocations(CLAUDE_TRANSCRIPT)
        unpaired = next(inv for inv in invocations if inv["command"] == "pytest tests/test_unpaired.py")
        assert unpaired["start_time"] == "2026-07-14T17:26:30Z"
        assert unpaired["end_time"] is None
        assert unpaired["duration_seconds"] is None
        assert unpaired["exit_code"] is None

    def test_claude_reader_ignores_non_bash_tool_use_blocks(self):
        invocations = session_log_claude.extract_test_invocations(CLAUDE_TRANSCRIPT)
        commands = [inv["command"] for inv in invocations]
        assert "git status" not in commands


def _kimi_call_line(uuid, command, time_ms):
    return {
        "type": "context.append_loop_event",
        "event": {
            "type": "tool.call",
            "uuid": uuid,
            "toolCallId": uuid,
            "name": "Bash",
            "args": {"command": command},
        },
        "time": time_ms,
    }


def _kimi_result_line(call_uuid, output, time_ms, is_error=False):
    return {
        "type": "context.append_loop_event",
        "event": {
            "type": "tool.result",
            "parentUuid": call_uuid,
            "toolCallId": call_uuid,
            "result": {"output": output, "isError": is_error},
        },
        "time": time_ms,
    }


def _claude_call_line(tool_use_id, command, timestamp):
    return {
        "timestamp": timestamp,
        "sessionId": "s1",
        "cwd": "/x",
        "gitBranch": "main",
        "role": "assistant",
        "message": {
            "content": [
                {
                    "type": "tool_use",
                    "name": "Bash",
                    "id": tool_use_id,
                    "input": {"command": command},
                }
            ]
        },
    }


def _claude_result_line(tool_use_id, timestamp, is_error=False):
    return {
        "timestamp": timestamp,
        "sessionId": "s1",
        "cwd": "/x",
        "gitBranch": "main",
        "role": "user",
        "message": {
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "is_error": is_error,
                    "content": "ok",
                }
            ]
        },
    }


class TestReaderHardening:
    """ADR-050: line cap, tolerant decode, and OSError tolerance are interface properties."""

    def test_kimi_reader_tolerates_malformed_json_and_overlong_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            import json

            session_dir = Path(tmp)
            wire_dir = session_dir / "agents" / "main"
            wire_dir.mkdir(parents=True)
            wire = wire_dir / "wire.jsonl"
            giant = '{"type": "metadata", "blob": "' + ("x" * (4 * 1024 * 1024 + 10)) + '"}'
            lines = [
                "not json",
                '{"trun":',
                giant,
                json.dumps(_kimi_call_line("c1", "pytest tests/", 1784049800000)),
                json.dumps(_kimi_result_line("c1", "ok", 1784049801000)),
            ]
            wire.write_text("\n".join(lines) + "\n")
            invocations = wirelog.extract_test_invocations(session_dir)
            assert len(invocations) == 1
            assert invocations[0]["command"] == "pytest tests/"

    def test_claude_reader_tolerates_malformed_json_and_overlong_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            import json

            transcript = Path(tmp) / "transcript.jsonl"
            giant = '{"type": "metadata", "blob": "' + ("x" * (4 * 1024 * 1024 + 10)) + '"}'
            lines = [
                "not json",
                '{"trun":',
                giant,
                json.dumps(_claude_call_line("c1", "pytest tests/", "2026-07-14T17:23:20Z")),
                json.dumps(_claude_result_line("c1", "2026-07-14T17:24:05Z")),
            ]
            transcript.write_text("\n".join(lines) + "\n")
            invocations = session_log_claude.extract_test_invocations(transcript)
            assert len(invocations) == 1
            assert invocations[0]["command"] == "pytest tests/"

    def test_claude_reader_tolerates_missing_transcript_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            assert session_log_claude.extract_test_invocations(Path(tmp) / "missing.jsonl") == []

    def test_kimi_reader_tolerates_missing_session_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            assert wirelog.extract_test_invocations(Path(tmp) / "nope") == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
