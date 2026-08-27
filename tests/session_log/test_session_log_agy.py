"""Tests for the Antigravity (``agy``) session-transcript reader.

The fixture under ``tests/fixtures/session_logs/agy/`` is a verbatim capture of
a real ``agy --dangerously-skip-permissions --output-format json -p ...``
session (agy 2026-08-27) that ran ``python3 -m pytest``. Unit cases below build
records in the same shape for edge conditions the capture does not contain.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aet import session_log, session_log_agy

FIXTURE = Path(__file__).parents[1] / "fixtures" / "session_logs" / "agy"
CONVERSATION_ID = "be8415f8-2aaa-4ca5-b480-d96a9092f3f2"


def _install_transcript(home: Path, conversation_id: str, records: list[dict]) -> Path:
    """Write ``records`` where the reader expects a conversation's transcript."""
    path = session_log_agy.transcript_path_for(conversation_id, home=home)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8"
    )
    return path


def _install_fixture(home: Path, conversation_id: str = CONVERSATION_ID) -> Path:
    path = session_log_agy.transcript_path_for(conversation_id, home=home)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((FIXTURE / "transcript.jsonl").read_bytes())
    return path


def _tool_call_record(command: str, created_at: str, step: int = 1) -> dict:
    """A PLANNER_RESPONSE record carrying one ``run_command`` call.

    ``transcript.jsonl`` stores every arg JSON-quoted (``"\\"pytest\\""``);
    the fixture confirms it, so the shape is reproduced here rather than
    simplified.
    """
    return {
        "step_index": step,
        "source": "MODEL",
        "type": "PLANNER_RESPONSE",
        "status": "DONE",
        "created_at": created_at,
        "tool_calls": [
            {
                "name": "run_command",
                "args": {
                    "CommandLine": json.dumps(command),
                    "Cwd": json.dumps("/tmp/proj"),
                    "WaitMsBeforeAsync": "5000",
                },
            }
        ],
    }


def _result_record(content: str, created_at: str, step: int = 2) -> dict:
    return {
        "step_index": step,
        "source": "MODEL",
        "type": "GENERIC",
        "status": "DONE",
        "created_at": created_at,
        "content": content,
    }


class TestTranscriptPath:
    def test_path_follows_the_brain_layout(self):
        path = session_log_agy.transcript_path_for("abc", home=Path("/h"))
        assert path == Path(
            "/h/brain/abc/.system_generated/logs/transcript.jsonl"
        )

    def test_default_home_is_the_antigravity_cli_dir(self, monkeypatch):
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: Path("/u")))
        path = session_log_agy.transcript_path_for("abc")
        assert path.parts[:4] == ("/", "u", ".gemini", "antigravity-cli")


class TestSessionLogAgy:
    """R-4: real test invocations, read from a real transcript."""

    def test_fixture_replay_extracts_the_real_pytest_invocation(self, tmp_path):
        _install_fixture(tmp_path)
        invocations = session_log_agy.extract_test_invocations(
            CONVERSATION_ID, home=tmp_path
        )
        assert invocations == [
            {
                "command": "python3 -m pytest tests/test_identity.py -q",
                "start_time": "2026-08-27T09:00:43Z",
                "end_time": "2026-08-27T09:00:43Z",
                "duration_seconds": 0.0,
                "exit_code": 4,
                "output": (
                    "ERROR: file or directory not found: "
                    "tests/test_identity.py\n\n\nno tests ran in 0.00s\n\n"
                ),
            }
        ]

    def test_command_line_is_unquoted_from_the_transcript_encoding(self, tmp_path):
        """``transcript.jsonl`` JSON-quotes args; the raw command is reported."""
        _install_transcript(
            tmp_path,
            "c1",
            [
                _tool_call_record("pytest -q", "2026-08-27T09:00:00Z"),
                _result_record(
                    "Created At: 2026-08-27T10:00:00+01:00\n"
                    "Completed At: 2026-08-27T10:00:05+01:00\n\n"
                    "The command exited with code 0.\nOutput:\n1 passed\n",
                    "2026-08-27T09:00:05Z",
                ),
            ],
        )
        (inv,) = session_log_agy.extract_test_invocations("c1", home=tmp_path)
        assert inv["command"] == "pytest -q"

    def test_unquoted_args_are_read_too(self, tmp_path):
        """``transcript_full.jsonl`` stores raw args; both encodings parse."""
        record = _tool_call_record("pytest -q", "2026-08-27T09:00:00Z")
        record["tool_calls"][0]["args"]["CommandLine"] = "pytest -q"
        _install_transcript(tmp_path, "c1", [record])
        (inv,) = session_log_agy.extract_test_invocations("c1", home=tmp_path)
        assert inv["command"] == "pytest -q"

    def test_duration_comes_from_the_commands_own_window(self, tmp_path):
        """The result body times the command; the step timestamp times the step."""
        _install_transcript(
            tmp_path,
            "c1",
            [
                _tool_call_record("pytest -q", "2026-08-27T09:00:00Z"),
                _result_record(
                    "Created At: 2026-08-27T10:00:02+01:00\n"
                    "Completed At: 2026-08-27T10:00:47+01:00\n\n"
                    "The command exited with code 0.\nOutput:\n631 passed\n",
                    "2026-08-27T09:00:47Z",
                ),
            ],
        )
        (inv,) = session_log_agy.extract_test_invocations("c1", home=tmp_path)
        assert inv["start_time"] == "2026-08-27T09:00:02Z"
        assert inv["end_time"] == "2026-08-27T09:00:47Z"
        assert inv["duration_seconds"] == 45.0

    def test_start_time_falls_back_to_the_step_timestamp(self, tmp_path):
        """A result body without ``Created At`` still dates the invocation."""
        _install_transcript(
            tmp_path,
            "c1",
            [
                _tool_call_record("pytest -q", "2026-08-27T09:00:00Z"),
                _result_record(
                    "The command exited with code 0.\nOutput:\nok\n",
                    "2026-08-27T09:00:05Z",
                ),
            ],
        )
        (inv,) = session_log_agy.extract_test_invocations("c1", home=tmp_path)
        assert inv["start_time"] == "2026-08-27T09:00:00Z"
        assert inv["end_time"] is None
        assert inv["duration_seconds"] is None
        assert inv["exit_code"] == 0

    def test_nonzero_exit_code_is_reported(self, tmp_path):
        _install_transcript(
            tmp_path,
            "c1",
            [
                _tool_call_record("pytest -q", "2026-08-27T09:00:00Z"),
                _result_record(
                    "Created At: 2026-08-27T10:00:00+01:00\n"
                    "Completed At: 2026-08-27T10:00:01+01:00\n\n"
                    "The command exited with code 1.\nOutput:\n2 failed\n",
                    "2026-08-27T09:00:01Z",
                ),
            ],
        )
        (inv,) = session_log_agy.extract_test_invocations("c1", home=tmp_path)
        assert inv["exit_code"] == 1
        assert inv["output"] == "2 failed\n"

    def test_stdout_labelled_output_is_captured(self, tmp_path):
        """agy labels an empty-stderr result ``Stdout:`` instead of ``Output:``."""
        _install_transcript(
            tmp_path,
            "c1",
            [
                _tool_call_record("pytest -q", "2026-08-27T09:00:00Z"),
                _result_record(
                    "Created At: 2026-08-27T10:00:00+01:00\n"
                    "Completed At: 2026-08-27T10:00:01+01:00\n\n"
                    "The command exited with code 0.\nStdout:\n1 passed\n",
                    "2026-08-27T09:00:01Z",
                ),
            ],
        )
        (inv,) = session_log_agy.extract_test_invocations("c1", home=tmp_path)
        assert inv["output"] == "1 passed\n"

    def test_backgrounded_command_yields_null_end_and_exit_code(self, tmp_path):
        """A command agy pushed to the background never reported a result."""
        _install_transcript(
            tmp_path,
            "c1",
            [
                _tool_call_record("pytest -q", "2026-08-27T09:00:00Z"),
                _result_record(
                    "Created At: 2026-08-27T10:00:00+01:00\n"
                    "Tool is running as a background task with task id: t1\n",
                    "2026-08-27T09:00:00Z",
                ),
            ],
        )
        (inv,) = session_log_agy.extract_test_invocations("c1", home=tmp_path)
        assert inv["end_time"] is None
        assert inv["duration_seconds"] is None
        assert inv["exit_code"] is None
        assert inv["output"] is None

    def test_unpaired_call_is_emitted_with_null_completion(self, tmp_path):
        _install_transcript(
            tmp_path,
            "c1",
            [_tool_call_record("pytest -q", "2026-08-27T09:00:00Z")],
        )
        (inv,) = session_log_agy.extract_test_invocations("c1", home=tmp_path)
        assert inv["start_time"] == "2026-08-27T09:00:00Z"
        assert inv["end_time"] is None
        assert inv["exit_code"] is None

    def test_non_test_commands_are_ignored(self, tmp_path):
        _install_transcript(
            tmp_path,
            "c1",
            [
                _tool_call_record("git status", "2026-08-27T09:00:00Z"),
                _result_record(
                    "Created At: 2026-08-27T10:00:00+01:00\n"
                    "Completed At: 2026-08-27T10:00:01+01:00\n\n"
                    "The command exited with code 0.\nOutput:\nclean\n",
                    "2026-08-27T09:00:01Z",
                ),
            ],
        )
        assert session_log_agy.extract_test_invocations("c1", home=tmp_path) == []

    def test_non_run_command_tools_do_not_shift_result_pairing(self, tmp_path):
        """A ``view_file`` call between test runs must not steal a result."""
        view = _tool_call_record("noop", "2026-08-27T09:00:10Z", step=3)
        view["tool_calls"][0] = {
            "name": "view_file",
            "args": {"AbsolutePath": json.dumps("/tmp/proj/a.py")},
        }
        _install_transcript(
            tmp_path,
            "c1",
            [
                _tool_call_record("pytest -q", "2026-08-27T09:00:00Z"),
                _result_record(
                    "Created At: 2026-08-27T10:00:00+01:00\n"
                    "Completed At: 2026-08-27T10:00:01+01:00\n\n"
                    "The command exited with code 0.\nOutput:\nfirst\n",
                    "2026-08-27T09:00:01Z",
                ),
                view,
                _result_record("file contents", "2026-08-27T09:00:11Z", step=4),
                _tool_call_record("pytest -q tests/b.py", "2026-08-27T09:00:20Z", step=5),
                _result_record(
                    "Created At: 2026-08-27T10:00:20+01:00\n"
                    "Completed At: 2026-08-27T10:00:21+01:00\n\n"
                    "The command exited with code 1.\nOutput:\nsecond\n",
                    "2026-08-27T09:00:21Z",
                    step=6,
                ),
            ],
        )
        invocations = session_log_agy.extract_test_invocations("c1", home=tmp_path)
        assert [inv["output"] for inv in invocations] == ["first\n", "second\n"]
        assert [inv["exit_code"] for inv in invocations] == [0, 1]

    def test_invocations_are_ordered_by_start_time(self, tmp_path):
        _install_transcript(
            tmp_path,
            "c1",
            [
                _tool_call_record("pytest -q tests/b.py", "2026-08-27T09:05:00Z"),
                _tool_call_record("pytest -q tests/a.py", "2026-08-27T09:00:00Z", step=3),
            ],
        )
        invocations = session_log_agy.extract_test_invocations("c1", home=tmp_path)
        assert [inv["start_time"] for inv in invocations] == [
            "2026-08-27T09:00:00Z",
            "2026-08-27T09:05:00Z",
        ]

    def test_missing_transcript_yields_no_invocations(self, tmp_path):
        assert session_log_agy.extract_test_invocations("absent", home=tmp_path) == []

    def test_malformed_and_overlong_lines_are_skipped(self, tmp_path):
        path = session_log_agy.transcript_path_for("c1", home=tmp_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        overlong = json.dumps(
            _result_record("x" * (5 * 1024 * 1024), "2026-08-27T09:00:01Z")
        )
        path.write_text(
            "not json\n"
            + json.dumps([1, 2, 3])
            + "\n"
            + json.dumps(_tool_call_record("pytest -q", "2026-08-27T09:00:00Z"))
            + "\n"
            + overlong
            + "\n",
            encoding="utf-8",
        )
        (inv,) = session_log_agy.extract_test_invocations("c1", home=tmp_path)
        assert inv["command"] == "pytest -q"
        assert inv["exit_code"] is None


class TestAgyDispatch:
    """R-5: the seam routes ``agy`` to this reader."""

    def test_dispatch_selects_the_agy_reader_by_agent_cli(self, tmp_path):
        _install_fixture(tmp_path)
        invocations = session_log.extract_test_invocations(
            "agy", CONVERSATION_ID, worktree_dir="/tmp/proj", home=tmp_path
        )
        assert [inv["command"] for inv in invocations] == [
            "python3 -m pytest tests/test_identity.py -q"
        ]

    def test_dispatch_does_not_require_a_worktree_dir(self, tmp_path):
        """agy transcripts are keyed by conversation id alone, not by cwd."""
        _install_fixture(tmp_path)
        invocations = session_log.extract_test_invocations(
            "agy", CONVERSATION_ID, home=tmp_path
        )
        assert len(invocations) == 1


@pytest.mark.parametrize("content", [None, 42, {"text": "x"}, []])
def test_unusable_result_content_shapes_leave_the_call_unpaired(content, tmp_path):
    record = _result_record("placeholder", "2026-08-27T09:00:01Z")
    record["content"] = content
    _install_transcript(
        tmp_path,
        "c1",
        [_tool_call_record("pytest -q", "2026-08-27T09:00:00Z"), record],
    )
    (inv,) = session_log_agy.extract_test_invocations("c1", home=tmp_path)
    assert inv["exit_code"] is None
    assert inv["output"] is None
