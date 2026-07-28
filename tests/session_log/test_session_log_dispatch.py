"""Tests for the adapter-dispatched session-log reader seam."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aet import session_log, session_log_claude, wirelog


def _fixture_path(name: str) -> Path:
    return Path(__file__).parents[1] / "fixtures" / "session_logs" / name


CLAUDE_TRANSCRIPT = _fixture_path("claude") / "transcript.jsonl"


class TestKimiRegression:
    """R-4: the kimi reader behind the seam yields byte-identical output."""

    def test_kimi_fixture_replay_matches_pre_change_output(self, tmp_path):
        session_id = "session_fixture_replay"
        session_dir = (
            tmp_path
            / ".kimi-code"
            / "sessions"
            / "fixture"
            / session_id
        )
        session_dir.mkdir(parents=True)
        # Copy fixture wires into the resolved session dir.
        fixture = _fixture_path("kimi")
        for wire in fixture.glob("agents/*/wire.jsonl"):
            dest = session_dir / wire.relative_to(fixture)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(wire.read_bytes())
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
        invocations = wirelog.extract_test_invocations(
            session_id, kimi_home=tmp_path / ".kimi-code"
        )
        assert invocations == expected


class TestDispatch:
    """R-4 seam behaviour: one call site keyed on agent_cli."""

    def test_dispatch_selects_kimi_reader_by_agent_cli(self, tmp_path):
        session_id = "session_dispatch_kimi"
        session_dir = (
            tmp_path
            / ".kimi-code"
            / "sessions"
            / "wd"
            / session_id
            / "agents"
            / "main"
        )
        session_dir.mkdir(parents=True)
        wire = session_dir / "wire.jsonl"
        wire.write_text(
            "\n".join(
                [
                    json.dumps(
                        _kimi_call_line("c1", "pytest tests/", 1784049800000)
                    ),
                    json.dumps(
                        _kimi_result_line("c1", "ok", 1784049801000)
                    ),
                ]
            )
            + "\n"
        )
        invocations = session_log.extract_test_invocations(
            "kimi", session_id, home=tmp_path / ".kimi-code"
        )
        assert len(invocations) == 1
        assert invocations[0]["command"] == "pytest tests/"

    def test_dispatch_selects_claude_reader_by_agent_cli(self, tmp_path):
        session_id = "session_dispatch_claude"
        cwd = "/x/y"
        transcript_dir = tmp_path / ".claude" / "projects" / session_log_claude.cwd_slug(cwd)
        transcript_dir.mkdir(parents=True)
        transcript = transcript_dir / f"{session_id}.jsonl"
        transcript.write_text(
            "\n".join(
                [
                    json.dumps(_claude_call_line("c1", "pytest tests/", "2026-07-14T17:23:20Z")),
                    json.dumps(_claude_result_line("c1", "2026-07-14T17:24:05Z")),
                ]
            )
            + "\n"
        )
        invocations = session_log.extract_test_invocations(
            "claude", session_id, worktree_dir=cwd, home=tmp_path / ".claude"
        )
        assert len(invocations) == 1
        assert invocations[0]["command"] == "pytest tests/"

    def test_dispatch_returns_empty_for_adapter_without_reader(self):
        """ADR-050 decision 4: an unsupported CLI resolves to no records."""
        assert session_log.extract_test_invocations("unknown", "any_id") == []

    def test_dispatch_requires_worktree_dir_for_claude(self):
        """Claude identifier resolution needs cwd; missing worktree_dir yields []."""
        assert session_log.extract_test_invocations("claude", "any_id") == []


class TestClaudeReader:
    """R-5: Claude Code transcript parsing."""

    _FIXTURE_SESSION_ID = "claude-session-t1"
    _FIXTURE_CWD = "/Users/pedrorocha/Sites/aiskills"

    def _install_claude_fixture(self, home: Path) -> Path:
        """Copy the fixture transcript into the location the reader expects."""
        transcript_dir = (
            home
            / ".claude"
            / "projects"
            / session_log_claude.cwd_slug(self._FIXTURE_CWD)
        )
        transcript_dir.mkdir(parents=True, exist_ok=True)
        transcript = transcript_dir / f"{self._FIXTURE_SESSION_ID}.jsonl"
        transcript.write_bytes(CLAUDE_TRANSCRIPT.read_bytes())
        return transcript

    def test_claude_reader_pairs_tool_use_and_tool_result(self, tmp_path):
        self._install_claude_fixture(tmp_path)
        invocations = session_log_claude.extract_test_invocations(
            self._FIXTURE_SESSION_ID, self._FIXTURE_CWD, home=tmp_path / ".claude"
        )
        commands = [inv["command"] for inv in invocations]
        assert "python3 -m pytest tests/ -q" in commands
        assert "pytest tests/" in commands
        assert "pytest tests/test_unpaired.py" in commands

    def test_claude_reader_derives_iso_timestamps_and_duration(self, tmp_path):
        self._install_claude_fixture(tmp_path)
        invocations = session_log_claude.extract_test_invocations(
            self._FIXTURE_SESSION_ID, self._FIXTURE_CWD, home=tmp_path / ".claude"
        )
        paired = [inv for inv in invocations if inv["end_time"] is not None]
        assert len(paired) == 2
        inv = next(inv for inv in paired if inv["command"] == "python3 -m pytest tests/ -q")
        assert inv["start_time"] == "2026-07-14T17:23:20Z"
        assert inv["end_time"] == "2026-07-14T17:24:05Z"
        assert inv["duration_seconds"] == 45.0

    def test_claude_reader_maps_is_error_to_exit_status(self, tmp_path):
        self._install_claude_fixture(tmp_path)
        invocations = session_log_claude.extract_test_invocations(
            self._FIXTURE_SESSION_ID, self._FIXTURE_CWD, home=tmp_path / ".claude"
        )
        passing = next(inv for inv in invocations if inv["command"] == "python3 -m pytest tests/ -q")
        failing = next(inv for inv in invocations if inv["command"] == "pytest tests/" and inv["end_time"] is not None)
        assert passing["exit_code"] == 0
        assert failing["exit_code"] == 1

    def test_claude_reader_emits_null_end_and_duration_for_unpaired_call(self, tmp_path):
        self._install_claude_fixture(tmp_path)
        invocations = session_log_claude.extract_test_invocations(
            self._FIXTURE_SESSION_ID, self._FIXTURE_CWD, home=tmp_path / ".claude"
        )
        unpaired = next(inv for inv in invocations if inv["command"] == "pytest tests/test_unpaired.py")
        assert unpaired["start_time"] == "2026-07-14T17:26:30Z"
        assert unpaired["end_time"] is None
        assert unpaired["duration_seconds"] is None
        assert unpaired["exit_code"] is None

    def test_claude_reader_ignores_non_bash_tool_use_blocks(self, tmp_path):
        self._install_claude_fixture(tmp_path)
        invocations = session_log_claude.extract_test_invocations(
            self._FIXTURE_SESSION_ID, self._FIXTURE_CWD, home=tmp_path / ".claude"
        )
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

    def test_kimi_reader_tolerates_malformed_json_and_overlong_lines(self, tmp_path):
        session_id = "session_kimi_noise"
        session_dir = (
            tmp_path
            / ".kimi-code"
            / "sessions"
            / "wd"
            / session_id
        )
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
        invocations = wirelog.extract_test_invocations(
            session_id, kimi_home=tmp_path / ".kimi-code"
        )
        assert len(invocations) == 1
        assert invocations[0]["command"] == "pytest tests/"

    def test_claude_reader_tolerates_malformed_json_and_overlong_lines(self, tmp_path):
        session_id = "session_claude_noise"
        cwd = "/x"
        transcript_dir = tmp_path / ".claude" / "projects" / session_log_claude.cwd_slug(cwd)
        transcript_dir.mkdir(parents=True)
        transcript = transcript_dir / f"{session_id}.jsonl"
        giant = '{"type": "metadata", "blob": "' + ("x" * (4 * 1024 * 1024 + 10)) + '"}'
        lines = [
            "not json",
            '{"trun":',
            giant,
            json.dumps(_claude_call_line("c1", "pytest tests/", "2026-07-14T17:23:20Z")),
            json.dumps(_claude_result_line("c1", "2026-07-14T17:24:05Z")),
        ]
        transcript.write_text("\n".join(lines) + "\n")
        invocations = session_log_claude.extract_test_invocations(
            session_id, cwd, home=tmp_path / ".claude"
        )
        assert len(invocations) == 1
        assert invocations[0]["command"] == "pytest tests/"

    def test_claude_reader_tolerates_missing_transcript_file(self):
        assert session_log_claude.extract_test_invocations("missing", "/x") == []

    def test_kimi_reader_tolerates_missing_session_dir(self):
        assert wirelog.extract_test_invocations("missing") == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
