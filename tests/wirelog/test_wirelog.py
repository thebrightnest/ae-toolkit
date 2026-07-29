"""Tests for src/aet/wirelog.py — test-invocation extraction from kimi wire logs."""

import json
import tempfile
import unittest
from pathlib import Path

from aet import wirelog

_FIXTURES = Path(__file__).parents[1] / "fixtures" / "session_logs"


def _tool_call_line(uuid, command, time_ms, name="Bash"):
    """One wire.jsonl line for a tool.call event (kimi 0.23.x shape)."""
    return json.dumps(
        {
            "type": "context.append_loop_event",
            "event": {
                "type": "tool.call",
                "uuid": uuid,
                "toolCallId": uuid,
                "name": name,
                "args": {"command": command},
            },
            "time": time_ms,
        }
    )


def _tool_result_line(call_uuid, output, time_ms, is_error=None):
    """One wire.jsonl line for the tool.result paired with a call."""
    result = {"output": output}
    if is_error is not None:
        result["isError"] = is_error
    return json.dumps(
        {
            "type": "context.append_loop_event",
            "event": {
                "type": "tool.result",
                "parentUuid": call_uuid,
                "toolCallId": call_uuid,
                "result": result,
            },
            "time": time_ms,
        }
    )


def _write_session(root, wires):
    """Materialize a kimi session dir with agents/<id>/wire.jsonl files.

    Returns the session id; wires live under ``root/.kimi-code/sessions/...``
    so ``wirelog.extract_test_invocations`` can resolve them by id.
    """
    session_id = "session_t1"
    session_dir = Path(root) / ".kimi-code" / "sessions" / "wd_proj_abc123" / session_id
    for agent_id, lines in wires.items():
        wire = session_dir / "agents" / agent_id / "wire.jsonl"
        wire.parent.mkdir(parents=True, exist_ok=True)
        wire.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return session_id


class TestExtractTestInvocations(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_paired_pytest_call_yields_one_invocation(self):
        session_id = _write_session(
            self.root,
            {
                "main": [
                    _tool_call_line("c1", "python3 -m pytest tests/ -q", 1784049800000),
                    _tool_result_line("c1", "631 passed", 1784049845000),
                ]
            },
        )
        invocations = wirelog.extract_test_invocations(
            session_id, kimi_home=self.root / ".kimi-code"
        )
        self.assertEqual(len(invocations), 1)
        inv = invocations[0]
        self.assertEqual(inv["command"], "python3 -m pytest tests/ -q")
        self.assertEqual(inv["start_time"], "2026-07-14T17:23:20Z")
        self.assertEqual(inv["end_time"], "2026-07-14T17:24:05Z")
        self.assertEqual(inv["duration_seconds"], 45.0)
        self.assertEqual(inv["exit_code"], 0)

    def test_unpaired_call_yields_null_duration_and_exit_code(self):
        """A test call whose result never arrived keeps honest nulls."""
        session_id = _write_session(
            self.root,
            {"main": [_tool_call_line("c1", "pytest tests/", 1784049800000)]},
        )
        invocations = wirelog.extract_test_invocations(
            session_id, kimi_home=self.root / ".kimi-code"
        )
        self.assertEqual(len(invocations), 1)
        inv = invocations[0]
        self.assertEqual(inv["command"], "pytest tests/")
        self.assertEqual(inv["start_time"], "2026-07-14T17:23:20Z")
        self.assertIsNone(inv["end_time"])
        self.assertIsNone(inv["duration_seconds"])
        self.assertIsNone(inv["exit_code"])
        self.assertIsNone(inv["output"])
        self.assertEqual(
            set(inv),
            {"command", "start_time", "end_time", "duration_seconds", "exit_code", "output"},
        )

    def test_non_test_commands_are_ignored(self):
        session_id = _write_session(
            self.root,
            {
                "main": [
                    _tool_call_line("c1", "git status", 1784049800000),
                    _tool_result_line("c1", "clean", 1784049801000),
                    _tool_call_line("c2", "ls -la", 1784049802000),
                    _tool_result_line("c2", "...", 1784049803000),
                    _tool_call_line("c3", "echo pytest", 1784049804000),
                    _tool_result_line("c3", "pytest", 1784049805000),
                ]
            },
        )
        self.assertEqual(wirelog.extract_test_invocations(session_id, kimi_home=self.root / ".kimi-code"), [])

    def test_non_bash_tool_calls_are_ignored(self):
        session_id = _write_session(
            self.root,
            {
                "main": [
                    _tool_call_line("c1", "pytest tests/", 1784049800000, name="Shell"),
                    _tool_result_line("c1", "ok", 1784049801000),
                ]
            },
        )
        self.assertEqual(wirelog.extract_test_invocations(session_id, kimi_home=self.root / ".kimi-code"), [])

    def test_all_v1_runners_match(self):
        lines = []
        commands = [
            "pytest",
            "python -m pytest tests/",
            "python3 -m pytest tests/ -q",
            "vitest run",
            "jest",
            "make test",
            "make validate",
            "npm test",
            "cargo test",
            "go test ./...",
        ]
        for i, command in enumerate(commands):
            lines.append(_tool_call_line(f"c{i}", command, 1784049800000 + i * 1000))
            lines.append(_tool_result_line(f"c{i}", "ok", 1784049800500 + i * 1000))
        session_id = _write_session(self.root, {"main": lines})
        invocations = wirelog.extract_test_invocations(session_id, kimi_home=self.root / ".kimi-code")
        self.assertEqual([inv["command"] for inv in invocations], commands)

    def test_failed_command_yields_measured_exit_code(self):
        session_id = _write_session(
            self.root,
            {
                "main": [
                    _tool_call_line("c1", "pytest tests/", 1784049800000),
                    _tool_result_line(
                        "c1",
                        "3 failed, 2 passed\nCommand failed with exit code: 1.",
                        1784049860000,
                        is_error=True,
                    ),
                ]
            },
        )
        inv = wirelog.extract_test_invocations(session_id, kimi_home=self.root / ".kimi-code")[0]
        self.assertEqual(inv["exit_code"], 1)
        self.assertEqual(inv["duration_seconds"], 60.0)

    def test_killed_command_yields_null_exit_code(self):
        """Timeout/kill failures carry no code — null, never an estimate."""
        session_id = _write_session(
            self.root,
            {
                "main": [
                    _tool_call_line("c1", "pytest tests/", 1784049800000),
                    _tool_result_line(
                        "c1", "Command killed by timeout (300s)", 1784050100000, is_error=True
                    ),
                ]
            },
        )
        inv = wirelog.extract_test_invocations(session_id, kimi_home=self.root / ".kimi-code")[0]
        self.assertIsNone(inv["exit_code"])
        self.assertEqual(inv["duration_seconds"], 300.0)

    def test_malformed_and_oversized_lines_are_skipped(self):
        giant = '{"type": "metadata", "blob": "' + ("x" * (4 * 1024 * 1024 + 10)) + '"}'
        session_id = _write_session(
            self.root,
            {
                "main": [
                    "not json at all",
                    '{"type": "context.append_loop_event", "event": {"type": "tool.c',  # truncated
                    giant,
                    "",
                    _tool_call_line("c1", "pytest tests/", 1784049800000),
                    _tool_result_line("c1", "ok", 1784049801000),
                ]
            },
        )
        invocations = wirelog.extract_test_invocations(session_id, kimi_home=self.root / ".kimi-code")
        self.assertEqual(len(invocations), 1)
        self.assertEqual(invocations[0]["command"], "pytest tests/")

    def test_missing_time_yields_null_fields(self):
        call = json.dumps(
            {
                "type": "context.append_loop_event",
                "event": {
                    "type": "tool.call",
                    "uuid": "c1",
                    "toolCallId": "c1",
                    "name": "Bash",
                    "args": {"command": "pytest tests/"},
                },
            }
        )
        session_id = _write_session(
            self.root,
            {"main": [call, _tool_result_line("c1", "ok", 1784049801000)]},
        )
        inv = wirelog.extract_test_invocations(session_id, kimi_home=self.root / ".kimi-code")[0]
        self.assertIsNone(inv["start_time"])
        self.assertIsNone(inv["duration_seconds"])
        self.assertEqual(inv["end_time"], "2026-07-14T17:23:21Z")

    def test_multi_agent_wires_all_contribute(self):
        session_id = _write_session(
            self.root,
            {
                "main": [
                    _tool_call_line("m1", "make validate", 1784049800000),
                    _tool_result_line("m1", "ok", 1784049810000),
                ],
                "agent_7f3a": [
                    _tool_call_line("s1", "pytest tests/test_a.py", 1784049900000),
                    _tool_result_line("s1", "1 passed", 1784049905000),
                ],
            },
        )
        invocations = wirelog.extract_test_invocations(session_id, kimi_home=self.root / ".kimi-code")
        self.assertEqual(len(invocations), 2)
        commands = {inv["command"] for inv in invocations}
        self.assertEqual(commands, {"make validate", "pytest tests/test_a.py"})

    def test_duplicate_call_lines_deduped(self):
        """A replayed/duplicated tool.call line yields one invocation."""
        session_id = _write_session(
            self.root,
            {
                "main": [
                    _tool_call_line("c1", "pytest tests/", 1784049800000),
                    _tool_call_line("c1", "pytest tests/", 1784049800000),
                    _tool_result_line("c1", "ok", 1784049801000),
                ]
            },
        )
        self.assertEqual(len(wirelog.extract_test_invocations(session_id, kimi_home=self.root / ".kimi-code")), 1)

    def test_missing_session_id_yields_empty(self):
        self.assertEqual(
            wirelog.extract_test_invocations("no-such-session", kimi_home=self.root / ".kimi-code"),
            [],
        )

    def test_is_test_command_rejects_prefixed_words(self):
        self.assertTrue(wirelog.is_test_command("pytest tests/"))
        self.assertTrue(wirelog.is_test_command("make validate"))
        self.assertFalse(wirelog.is_test_command("pytester --help"))
        self.assertFalse(wirelog.is_test_command("git log --oneline | grep pytest"))
        self.assertFalse(wirelog.is_test_command("make testify"))

    def test_shared_registry_widens_detection_without_losing_v1(self):
        """Every v1 detection survives the registry move; the previously
        missed shapes (`cd … &&`, path prefixes, wrappers, R-2 runners) are
        now detected too — the extracted set is a superset of the old one."""
        v1_commands = [
            "pytest",
            "python -m pytest tests/",
            "python3 -m pytest tests/ -q",
            "vitest run",
            "jest",
            "make test",
            "make validate",
            "npm test",
            "cargo test",
            "go test ./...",
        ]
        newly_detected = [
            "cd /path/to/wt && make validate",
            ".venv/bin/python -m pytest tests/ -q",
            "source .venv/bin/activate && pytest",
            "CI=true pytest tests/",
            "npx vitest run",
            "poetry run pytest tests/test_a.py",
            "rspec",
            "phpunit",
            "php artisan test",
            "dotnet test",
            "gradle test",
            "python -m unittest",
        ]
        lines = []
        for i, command in enumerate(v1_commands + newly_detected):
            lines.append(_tool_call_line(f"c{i}", command, 1784049800000 + i * 1000))
            lines.append(_tool_result_line(f"c{i}", "ok", 1784049800500 + i * 1000))
        session_id = _write_session(self.root, {"main": lines})
        invocations = wirelog.extract_test_invocations(session_id, kimi_home=self.root / ".kimi-code")
        self.assertEqual([inv["command"] for inv in invocations], v1_commands + newly_detected)


class TestKimiFixtureRegression(unittest.TestCase):
    """R-4 regression contract: replaying the captured fixture matches pre-change output.

    tap-06 added ``output`` to the shape; every other field is pinned exactly
    as it was, so a reader change that alters a timestamp, duration, or exit
    code still fails here.
    """

    def test_kimi_fixture_replay_matches_pre_change_output(self):
        session_id = "session_fixture_replay"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            session_dir = (
                root
                / ".kimi-code"
                / "sessions"
                / "fixture"
                / session_id
            )
            session_dir.mkdir(parents=True)
            fixture = _FIXTURES / "kimi"
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
                session_id, kimi_home=root / ".kimi-code"
            )
            self.assertEqual(invocations, expected)


if __name__ == "__main__":
    unittest.main()
