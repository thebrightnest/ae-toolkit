"""Tests for src/aet/usage.py — parsing agent CLI headless usage output."""

import json
import tempfile
import unittest
from pathlib import Path

from aet.usage import parse_usage, resolve_kimi_session_dir_from_output

# Trimmed from real `claude -p --output-format json` output captured 2026-07-12:
# a single-line JSON array whose final element (type "result") carries `usage`
# and `total_cost_usd`.
CLAUDE_ENVELOPE = (
    '[{"type":"system","subtype":"init","session_id":"s1"},'
    '{"type":"assistant","message":{"content":[{"type":"text","text":"OK"}],'
    '"usage":{"input_tokens":2,"cache_creation_input_tokens":13845,'
    '"cache_read_input_tokens":0,"output_tokens":1}}},'
    '{"type":"result","subtype":"success","is_error":false,"num_turns":1,'
    '"result":"OK","total_cost_usd":0.139146,'
    '"usage":{"input_tokens":2,"cache_creation_input_tokens":13845,'
    '"cache_read_input_tokens":0,"output_tokens":4,'
    '"server_tool_use":{"web_search_requests":0}}}]'
)


# Real `kimi -p` text output captured 2026-07-12: response text plus a resume
# hint. Stdout carries no token/cost data; usage lives in the session's
# on-disk wire files (see TestParseUsageKimiWire).
KIMI_TEXT_OUTPUT = (
    '• The user asked me to reply with exactly "OK". Simple instruction.\n'
    "\n"
    "• OK\n"
    "\n"
    "To resume this session: kimi -r session_f00f44f4-729f-48e9-8459-ff25c43c5923\n"
)

# Real `kimi --output-format stream-json` output captured 2026-07-12: NDJSON
# events, still no usage/token fields on stdout.
KIMI_STREAM_JSON_OUTPUT = (
    '{"role":"assistant","content":"OK"}\n'
    '{"role":"meta","type":"session.resume_hint","session_id":"session_9f98",'
    '"command":"kimi -r session_9f98","content":"To resume this session: kimi -r session_9f98"}\n'
)


class TestParseUsageClaude(unittest.TestCase):
    def test_claude_json_envelope_parses_tokens_and_cost(self):
        usage = parse_usage("claude", CLAUDE_ENVELOPE)
        self.assertIsNotNone(usage)
        # Input side includes cache creation/read tokens (billed input).
        self.assertEqual(usage["input_tokens"], 2 + 13845 + 0)
        self.assertEqual(usage["output_tokens"], 4)
        self.assertEqual(usage["total_tokens"], 13847 + 4)
        self.assertAlmostEqual(usage["cost_usd"], 0.139146)

    def test_claude_truncated_array_head_still_parses(self):
        """The tee buffer keeps the tail; a giant envelope can lose its head."""
        tail = CLAUDE_ENVELOPE[len('[{"type":"system","subtype":"init","session_id":"s1"},') :]
        usage = parse_usage("claude", tail)
        self.assertIsNotNone(usage)
        self.assertEqual(usage["total_tokens"], 13851)
        self.assertAlmostEqual(usage["cost_usd"], 0.139146)

    def test_claude_error_result_without_cost(self):
        """A failed session still reports tokens; cost may be absent."""
        text = (
            '{"type":"result","subtype":"error_during_execution","is_error":true,'
            '"usage":{"input_tokens":10,"output_tokens":3}}'
        )
        usage = parse_usage("claude", text)
        self.assertIsNotNone(usage)
        self.assertEqual(usage["total_tokens"], 13)
        self.assertIsNone(usage["cost_usd"])

    def test_claude_result_without_usage_returns_none(self):
        text = '{"type":"result","subtype":"error_during_execution","is_error":true}'
        self.assertIsNone(parse_usage("claude", text))

    def test_truncated_mid_result_returns_none(self):
        """A result object cut mid-stream by process death is not half-parsed."""
        text = '{"type":"result","subtype":"success","usage":{"input_tokens":10,"out'
        self.assertIsNone(parse_usage("claude", text))

    def test_claude_live_captured_envelope_parses(self):
        """Live 2026-07-28 envelope (redacted) parses to non-null tokens and cost."""
        fixture = Path(__file__).parent.parent / "fixtures" / "usage" / "claude_live_envelope.json"
        text = fixture.read_text()
        usage = parse_usage("claude", text)
        self.assertIsNotNone(usage)
        self.assertEqual(usage["input_tokens"], 21395)
        self.assertEqual(usage["output_tokens"], 4)
        self.assertEqual(usage["total_tokens"], 21399)
        self.assertAlmostEqual(usage["cost_usd"], 0.21404)


class TestParseUsageKimi(unittest.TestCase):
    """Kimi prints no usage to stdout (verified 2026-07-12); its usage lives
    in on-disk wire files. With no resolvable session, parsing yields None."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.kimi_home = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_kimi_text_output_returns_none_without_wire_session(self):
        self.assertIsNone(parse_usage("kimi", KIMI_TEXT_OUTPUT, kimi_home=self.kimi_home))

    def test_kimi_stream_json_output_returns_none(self):
        self.assertIsNone(
            parse_usage("kimi", KIMI_STREAM_JSON_OUTPUT, kimi_home=self.kimi_home)
        )


def _step_end_line(uuid, input_other=100, output=10, cache_read=20, cache_creation=5):
    """One wire.jsonl line, trimmed from real kimi 0.23.6 wire files."""
    return json.dumps(
        {
            "type": "context.append_loop_event",
            "event": {
                "type": "step.end",
                "uuid": uuid,
                "turnId": "0",
                "step": 1,
                "usage": {
                    "inputOther": input_other,
                    "output": output,
                    "inputCacheRead": cache_read,
                    "inputCacheCreation": cache_creation,
                },
                "finishReason": "stop",
            },
            "time": 1781943979640,
        }
    )


def _config_update_line(model_alias):
    return json.dumps(
        {"type": "config.update", "modelAlias": model_alias, "thinkingLevel": "high", "time": 1}
    )


def _write_kimi_session(home, session_id, wires, workdir_key="wd_proj_abc123", index=True):
    """Materialize a fake ~/.kimi-code session: agents/<id>/wire.jsonl files,
    optionally registered in session_index.jsonl."""
    session_dir = home / "sessions" / workdir_key / session_id
    for agent_id, lines in wires.items():
        wire = session_dir / "agents" / agent_id / "wire.jsonl"
        wire.parent.mkdir(parents=True, exist_ok=True)
        wire.write_text("\n".join(lines) + "\n")
    if index:
        with (home / "session_index.jsonl").open("a") as f:
            f.write(
                json.dumps(
                    {
                        "sessionId": session_id,
                        "sessionDir": str(session_dir),
                        "workDir": "/tmp/proj",
                    }
                )
                + "\n"
            )
    return session_dir


def _resume_hint(session_id):
    return f"some output\nTo resume this session: kimi -r {session_id}\n"


class TestParseUsageKimiWire(unittest.TestCase):
    """Kimi usage is parsed post-exit from ~/.kimi-code wire files."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.kimi_home = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_wire_sums_step_end_usage(self):
        session_id = "session_f00f44f4-729f-48e9-8459-ff25c43c5923"
        _write_kimi_session(
            self.kimi_home,
            session_id,
            {
                "main": [
                    _config_update_line("kimi-code/kimi-for-coding"),
                    _step_end_line("u1", input_other=100, output=10, cache_read=20, cache_creation=5),
                    _step_end_line("u2", input_other=200, output=30, cache_read=0, cache_creation=7),
                ]
            },
        )
        usage = parse_usage("kimi", _resume_hint(session_id), kimi_home=self.kimi_home)
        self.assertIsNotNone(usage)
        # input = Σ(inputOther + inputCacheRead + inputCacheCreation)
        self.assertEqual(usage["input_tokens"], (100 + 20 + 5) + (200 + 0 + 7))
        self.assertEqual(usage["output_tokens"], 10 + 30)
        self.assertEqual(usage["total_tokens"], 332 + 40)
        # kimi-for-coding is subscription/quota-billed: no per-token price.
        self.assertIsNone(usage["cost_usd"])

    def test_wire_dedupes_duplicate_uuids(self):
        """A replayed/duplicated step.end line counts once, within one wire
        and across agent wires."""
        session_id = "session_a1"
        _write_kimi_session(
            self.kimi_home,
            session_id,
            {
                "main": [
                    _step_end_line("dup", input_other=100, output=10),
                    _step_end_line("dup", input_other=100, output=10),
                ],
                "sub_0": [_step_end_line("dup", input_other=100, output=10)],
            },
        )
        usage = parse_usage("kimi", _resume_hint(session_id), kimi_home=self.kimi_home)
        self.assertIsNotNone(usage)
        self.assertEqual(usage["input_tokens"], 100 + 20 + 5)
        self.assertEqual(usage["output_tokens"], 10)

    def test_wire_sums_main_and_subagent_wires(self):
        session_id = "session_b2"
        _write_kimi_session(
            self.kimi_home,
            session_id,
            {
                "main": [_step_end_line("m1", input_other=100, output=10)],
                "agent_7f3a": [
                    _step_end_line("s1", input_other=50, output=5),
                    _step_end_line("s2", input_other=60, output=6),
                ],
            },
        )
        usage = parse_usage("kimi", _resume_hint(session_id), kimi_home=self.kimi_home)
        self.assertIsNotNone(usage)
        self.assertEqual(usage["input_tokens"], (100 + 25) + (50 + 25) + (60 + 25))
        self.assertEqual(usage["output_tokens"], 10 + 5 + 6)

    def test_ses_prefix_session_id_resolves(self):
        """Both `ses_` and `session_` id prefixes exist in the wild."""
        session_id = "ses_54ef083f-6e11-47e5-a0ab-48e621e99b72"
        _write_kimi_session(
            self.kimi_home,
            session_id,
            {"main": [_step_end_line("u1", input_other=10, output=1)]},
        )
        usage = parse_usage("kimi", _resume_hint(session_id), kimi_home=self.kimi_home)
        self.assertIsNotNone(usage)
        self.assertEqual(usage["total_tokens"], 10 + 25 + 1)

    def test_glob_fallback_when_index_missing(self):
        """No session_index.jsonl entry → glob sessions/*/<sessionId>/."""
        session_id = "session_c3"
        _write_kimi_session(
            self.kimi_home,
            session_id,
            {"main": [_step_end_line("u1", input_other=10, output=1)]},
            index=False,
        )
        usage = parse_usage("kimi", _resume_hint(session_id), kimi_home=self.kimi_home)
        self.assertIsNotNone(usage)
        self.assertEqual(usage["total_tokens"], 10 + 25 + 1)

    def test_missing_session_returns_none(self):
        """A resume hint for a session that exists nowhere yields None."""
        usage = parse_usage(
            "kimi", _resume_hint("session_does-not-exist"), kimi_home=self.kimi_home
        )
        self.assertIsNone(usage)

    def test_wire_without_step_end_returns_none(self):
        """A session that died before any LLM step records null usage."""
        session_id = "session_d4"
        _write_kimi_session(
            self.kimi_home,
            session_id,
            {"main": [_config_update_line("kimi-code/kimi-for-coding")]},
        )
        self.assertIsNone(
            parse_usage("kimi", _resume_hint(session_id), kimi_home=self.kimi_home)
        )

    def test_garbage_and_truncated_wire_lines_skipped(self):
        session_id = "session_e5"
        _write_kimi_session(
            self.kimi_home,
            session_id,
            {
                "main": [
                    "not json at all",
                    '{"type": "context.append_loop_event", "event": {"type": "step.e',  # truncated
                    _step_end_line("u1", input_other=10, output=1),
                    '{"type": "context.append_loop_event", "event": {"type": "step.end"}}',  # no usage
                    "",
                ]
            },
        )
        usage = parse_usage("kimi", _resume_hint(session_id), kimi_home=self.kimi_home)
        self.assertIsNotNone(usage)
        self.assertEqual(usage["total_tokens"], 10 + 25 + 1)

    def test_oversized_wire_line_skipped(self):
        """A pathological line is skipped, not loaded/parsed whole."""
        session_id = "session_f6"
        giant = '{"type": "metadata", "blob": "' + ("x" * (4 * 1024 * 1024 + 10)) + '"}'
        _write_kimi_session(
            self.kimi_home,
            session_id,
            {"main": [giant, _step_end_line("u1", input_other=10, output=1)]},
        )
        usage = parse_usage("kimi", _resume_hint(session_id), kimi_home=self.kimi_home)
        self.assertIsNotNone(usage)
        self.assertEqual(usage["total_tokens"], 36)

    def test_last_resume_hint_wins(self):
        """Resumed sessions print several hints; the final id is current."""
        old_id = "session_g7"
        new_id = "session_g7-resumed"
        _write_kimi_session(
            self.kimi_home, old_id, {"main": [_step_end_line("old", input_other=1, output=1)]}
        )
        _write_kimi_session(
            self.kimi_home, new_id, {"main": [_step_end_line("new", input_other=10, output=1)]}
        )
        text = _resume_hint(old_id) + "more output\n" + _resume_hint(new_id)
        usage = parse_usage("kimi", text, kimi_home=self.kimi_home)
        self.assertIsNotNone(usage)
        self.assertEqual(usage["total_tokens"], 36)

    def test_unknown_model_alias_cost_null(self):
        """No published price for the alias → null, never an invented number."""
        session_id = "session_h8"
        _write_kimi_session(
            self.kimi_home,
            session_id,
            {
                "main": [
                    _config_update_line("kimi-code/some-future-model"),
                    _step_end_line("u1", input_other=10, output=1),
                ]
            },
        )
        usage = parse_usage("kimi", _resume_hint(session_id), kimi_home=self.kimi_home)
        self.assertIsNotNone(usage)
        self.assertEqual(usage["total_tokens"], 36)
        self.assertIsNone(usage["cost_usd"])
    def test_garbage_returns_none(self):
        self.assertIsNone(parse_usage("claude", "not json at all\n>>> random <<<"))

    def test_empty_returns_none(self):
        self.assertIsNone(parse_usage("claude", ""))

    def test_unknown_cli_returns_none(self):
        self.assertIsNone(parse_usage("some-future-cli", CLAUDE_ENVELOPE))

    def test_never_estimates_from_text_size(self):
        """A huge response with no usage block yields None, not a guess."""
        self.assertIsNone(parse_usage("kimi", "x" * 1_000_000))

    def test_oversize_input_is_tail_scanned(self):
        """A result inside the tail window of a huge capture is still found."""
        result = (
            '{"type":"result","subtype":"success","total_cost_usd":0.01,'
            '"usage":{"input_tokens":5,"output_tokens":2}}'
        )
        text = "noise line\n" * 100_000 + result  # ~1.1 MB of noise first
        usage = parse_usage("claude", text)
        self.assertIsNotNone(usage)
        self.assertEqual(usage["total_tokens"], 7)

    def test_result_older_than_tail_window_returns_none(self):
        """A result pushed out of the tail window by later output is lost."""
        result = (
            '{"type":"result","subtype":"success","total_cost_usd":0.01,'
            '"usage":{"input_tokens":5,"output_tokens":2}}'
        )
        text = result + "\n" + "later noise\n" * 100_000
        self.assertIsNone(parse_usage("claude", text))


class TestResolveKimiSessionDirFromOutput(unittest.TestCase):
    """The shared resume-hint → session-dir path used by usage and wirelog."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.kimi_home = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_resolves_via_session_index(self):
        session_id = "session_r1"
        expected = _write_kimi_session(self.kimi_home, session_id, {"main": []})
        resolved = resolve_kimi_session_dir_from_output(
            _resume_hint(session_id), kimi_home=self.kimi_home
        )
        self.assertEqual(resolved, expected)

    def test_glob_fallback_without_index(self):
        session_id = "session_r2"
        expected = _write_kimi_session(self.kimi_home, session_id, {"main": []}, index=False)
        resolved = resolve_kimi_session_dir_from_output(
            _resume_hint(session_id), kimi_home=self.kimi_home
        )
        self.assertEqual(resolved, expected)

    def test_last_resume_hint_wins(self):
        _write_kimi_session(self.kimi_home, "session_old", {"main": []})
        expected = _write_kimi_session(self.kimi_home, "session_new", {"main": []})
        text = _resume_hint("session_old") + "noise\n" + _resume_hint("session_new")
        resolved = resolve_kimi_session_dir_from_output(text, kimi_home=self.kimi_home)
        self.assertEqual(resolved, expected)

    def test_no_hint_returns_none(self):
        self.assertIsNone(
            resolve_kimi_session_dir_from_output("plain output\n", kimi_home=self.kimi_home)
        )

    def test_unresolvable_session_returns_none(self):
        resolved = resolve_kimi_session_dir_from_output(
            _resume_hint("session_ghost"), kimi_home=self.kimi_home
        )
        self.assertIsNone(resolved)

    def test_empty_output_returns_none(self):
        self.assertIsNone(resolve_kimi_session_dir_from_output("", kimi_home=self.kimi_home))


if __name__ == "__main__":
    unittest.main()
