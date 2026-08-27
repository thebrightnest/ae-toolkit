"""Tests for the adapter-dispatched session-log reader seam."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from aet import session_log, session_log_claude, wirelog


def _fixture_path(name: str) -> Path:
    return Path(__file__).parents[1] / "fixtures" / "session_logs" / name


CLAUDE_TRANSCRIPT = _fixture_path("claude") / "transcript.jsonl"


class TestKimiRegression:
    """R-4: the kimi reader behind the seam yields byte-identical output.

    tap-06 added ``output`` to the shape; every other field stays pinned.
    """

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
                "output": "631 passed",
            },
            {
                "command": "pytest tests/",
                "start_time": "2026-07-14T17:25:00Z",
                "end_time": "2026-07-14T17:26:00Z",
                "duration_seconds": 60.0,
                "exit_code": 1,
                "output": "3 failed, 2 passed\nCommand failed with exit code: 1.",
            },
            {
                "command": "pytest tests/test_unpaired.py",
                "start_time": "2026-07-14T17:26:40Z",
                "end_time": None,
                "duration_seconds": None,
                "exit_code": None,
                "output": None,
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


class TestResultOutputExposure:
    """tap-06: both readers surface the command's own output to the caller.

    `make validate` resolves its pytest targets at runtime and prints them as a
    marker; the scope of that run lives in the output, not the command string.
    Every reader therefore carries `output` in the same shape.
    """

    def test_session_reader_exposes_result_output_to_emission_site(self, tmp_path):
        session_id = "session_output_exposure"
        # kimi: copy fixture wires into the resolved session dir.
        kimi_session_dir = (
            tmp_path / ".kimi-code" / "sessions" / "fixture" / session_id
        )
        kimi_session_dir.mkdir(parents=True)
        kimi_fixture = _fixture_path("kimi")
        for wire in kimi_fixture.glob("agents/*/wire.jsonl"):
            dest = kimi_session_dir / wire.relative_to(kimi_fixture)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(wire.read_bytes())
        invocations = session_log.extract_test_invocations(
            "kimi", session_id, home=tmp_path / ".kimi-code"
        )
        passing = next(
            inv for inv in invocations if inv["command"] == "python3 -m pytest tests/ -q"
        )
        assert passing["output"] == "631 passed"
        unpaired = next(
            inv for inv in invocations if inv["command"] == "pytest tests/test_unpaired.py"
        )
        assert unpaired["output"] is None

        # claude: install the fixture transcript under the expected cwd slug.
        cwd = "/Users/pedrorocha/Sites/aiskills"
        claude_home = tmp_path / ".claude"
        transcript_dir = (
            claude_home
            / "projects"
            / session_log_claude.cwd_slug(cwd)
        )
        transcript_dir.mkdir(parents=True)
        transcript = transcript_dir / f"{session_id}.jsonl"
        transcript.write_bytes(CLAUDE_TRANSCRIPT.read_bytes())
        invocations = session_log.extract_test_invocations(
            "claude", session_id, worktree_dir=cwd, home=claude_home
        )
        passing = next(
            inv for inv in invocations if inv["command"] == "python3 -m pytest tests/ -q"
        )
        assert passing["output"] == "631 passed"
        unpaired = next(
            inv for inv in invocations if inv["command"] == "pytest tests/test_unpaired.py"
        )
        assert unpaired["output"] is None

    def test_claude_reader_joins_structured_content_blocks(self, tmp_path):
        """Claude's tool_result content may be text blocks rather than a string."""
        session_id = "session_claude_structured"
        cwd = "/Users/pedrorocha/Sites/aiskills"
        transcript_dir = (
            tmp_path
            / ".claude"
            / "projects"
            / session_log_claude.cwd_slug(cwd)
        )
        transcript_dir.mkdir(parents=True)
        transcript = transcript_dir / f"{session_id}.jsonl"
        result = _claude_result_line("c1", "2026-07-14T17:24:05Z")
        result["message"]["content"][0]["content"] = [
            {"type": "text", "text": "AET_TEST_SCOPE_TARGETS: tests/queue"},
            {"type": "text", "text": "✓ Tests passed"},
        ]
        transcript.write_text(
            "\n".join(
                json.dumps(line)
                for line in (
                    _claude_call_line("c1", "make validate", "2026-07-14T17:23:20Z"),
                    result,
                )
            )
            + "\n"
        )
        inv = session_log_claude.extract_test_invocations(
            session_id, cwd, home=tmp_path / ".claude"
        )[0]
        assert inv["output"] == "AET_TEST_SCOPE_TARGETS: tests/queue\n✓ Tests passed"

    @pytest.mark.parametrize("content", [42, None, {"type": "text"}, [], ["bare string"]])
    def test_claude_output_is_null_for_unusable_content_shapes(self, content):
        """The transcript is a recovery stream: an odd shape yields null, not a crash."""
        assert session_log_claude._output_from_content(content) is None

    @pytest.mark.parametrize("result", [None, "not a dict", 42, []])
    def test_kimi_output_is_null_for_unusable_result_shapes(self, result):
        """Mirrors the claude reader: the wire schema is not a public contract."""
        assert wirelog._output_from_result(result) is None

    def test_readers_emit_null_output_for_unusable_payloads(self, tmp_path):
        session_id = "session_unusable_output"
        kimi_home = tmp_path / ".kimi-code"
        session_dir = kimi_home / "sessions" / "wd" / session_id
        wire_dir = session_dir / "agents" / "main"
        wire_dir.mkdir(parents=True)
        result = _kimi_result_line("c1", None, 1784049801000)
        result["event"]["result"]["output"] = {"unexpected": "shape"}
        wire_dir.joinpath("wire.jsonl").write_text(
            "\n".join(
                json.dumps(line)
                for line in (
                    _kimi_call_line("c1", "make validate", 1784049800000),
                    result,
                )
            )
            + "\n"
        )
        assert wirelog.extract_test_invocations(session_id, kimi_home=kimi_home)[0]["output"] is None


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


class TestCwdSlugMatchesClaudeCode:
    """Pin the slug against real Claude Code directory names.

    Every other test in this file computes its expected path by calling
    ``cwd_slug`` itself, so all of them passed while the function replaced only
    ``/`` and left ``.`` and ``_`` intact. A tautology cannot catch a wrong rule.
    The literals below are copied from observed ``~/.claude/projects`` directory
    names, so this test fails if the rule drifts from Claude Code's.
    """

    CASES = [
        # (cwd, observed project directory name)
        ("/Users/alice/proj", "-Users-alice-proj"),
        ("/private/tmp", "-private-tmp"),
        # A dot in the username: the case that broke this for a real operator.
        ("/Users/p.rocha/Work/ae-toolkit", "-Users-p-rocha-Work-ae-toolkit"),
        # An AET worktree — always under a dot directory, so this is every
        # orchestrated session. The separator and the dot each yield a dash.
        (
            "/Users/p.rocha/Work/ae-toolkit/.worktrees/sst-01-agents-path-registration",
            "-Users-p-rocha-Work-ae-toolkit--worktrees-sst-01-agents-path-registration",
        ),
        # Underscores are replaced too.
        ("/Users/p.rocha/Work/ki_mcp", "-Users-p-rocha-Work-ki-mcp"),
        # Case is preserved and existing dashes are kept.
        (
            "/Users/p.rocha/Work/mb-intent-agent/.claude-worktrees/feat/PMC-105-austria-market",
            "-Users-p-rocha-Work-mb-intent-agent--claude-worktrees-feat-PMC-105-austria-market",
        ),
    ]

    @pytest.mark.parametrize("cwd,expected", CASES)
    def test_slug_matches_observed_directory_names(self, cwd, expected):
        assert session_log_claude.cwd_slug(cwd) == expected

    def test_trailing_separator_is_normalised(self):
        assert session_log_claude.cwd_slug("/tmp/") == session_log_claude.cwd_slug("/tmp")

    def test_slug_contains_only_dashes_and_alphanumerics(self):
        """Claude Code's project directories never contain other characters."""
        slug = session_log_claude.cwd_slug("/Users/p.rocha/Work/a_b.c/.worktrees/d")
        assert re.fullmatch(r"[A-Za-z0-9-]+", slug)


class TestClaudeReaderAgainstRealShape:
    """Read a transcript in the shape Claude Code actually writes.

    The long-standing fixture (``transcript.jsonl``) carries a top-level
    ``role`` and no ``type``. A real transcript is the opposite: ``type`` at the
    top level, the role under ``message.role``, and no top-level ``role`` at all.
    The reader matched only the invented shape, so it returned an empty list for
    every real session while its tests passed. This fixture is derived from an
    actual transcript, with the command and result text replaced.
    """

    FIXTURE = _fixture_path("claude") / "transcript_real_shape.jsonl"

    def _transcript(self, tmp_path, cwd: str) -> Path:
        home = tmp_path / ".claude"
        d = home / "projects" / session_log_claude.cwd_slug(cwd)
        d.mkdir(parents=True)
        (d / "sess-1.jsonl").write_text(self.FIXTURE.read_text(), encoding="utf-8")
        return home

    def test_recovers_a_piped_invocation_from_a_real_shaped_record(self, tmp_path):
        cwd = "/Users/p.rocha/Work/proj/.worktrees/task-1"
        home = self._transcript(tmp_path, cwd)

        found = session_log_claude.extract_test_invocations("sess-1", cwd, home=home)

        assert len(found) == 1, "a real-shaped transcript must yield its invocation"
        inv = found[0]
        assert "pytest" in inv["command"]
        assert inv["exit_code"] == 0
        assert inv["duration_seconds"] is not None

    def test_dispatch_reaches_the_same_result(self, tmp_path):
        cwd = "/Users/p.rocha/Work/proj/.worktrees/task-1"
        home = self._transcript(tmp_path, cwd)

        found = session_log.extract_test_invocations(
            "claude", "sess-1", worktree_dir=cwd, home=home
        )

        assert len(found) == 1


class TestSessionLogDispatch:
    """R-5: ``agy`` reaches the Antigravity reader through the same seam."""

    FIXTURE = _fixture_path("agy") / "transcript.jsonl"
    CONVERSATION_ID = "7c054dec-a00c-4fad-a7d7-b395cc48d629"

    def _agy_home(self, tmp_path: Path) -> Path:
        home = tmp_path / ".gemini" / "antigravity-cli"
        transcript = (
            home
            / "brain"
            / self.CONVERSATION_ID
            / ".system_generated"
            / "logs"
            / "transcript.jsonl"
        )
        transcript.parent.mkdir(parents=True)
        transcript.write_text(self.FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
        return home

    def test_dispatch_selects_agy_reader_by_agent_cli(self, tmp_path):
        home = self._agy_home(tmp_path)

        invocations = session_log.extract_test_invocations(
            "agy", self.CONVERSATION_ID, home=home
        )

        assert [inv["command"] for inv in invocations] == [
            "python3 -m pytest tests/test_identity.py -q",
        ]

    def test_dispatch_does_not_require_worktree_dir_for_agy(self, tmp_path):
        """Antigravity keys transcripts by conversation id, not by cwd slug."""
        home = self._agy_home(tmp_path)

        assert session_log.extract_test_invocations(
            "agy", self.CONVERSATION_ID, home=home
        ) == session_log.extract_test_invocations(
            "agy", self.CONVERSATION_ID, worktree_dir="/somewhere/else", home=home
        )

    def test_dispatch_returns_empty_for_unknown_agy_conversation(self, tmp_path):
        assert session_log.extract_test_invocations("agy", "no-such-id", home=tmp_path) == []
