"""Tests for aet-work/lib/usage.py — parsing agent CLI headless usage output."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "aet-work" / "lib"))

import unittest

from usage import parse_usage

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
# hint, and no token/cost data of any kind.
KIMI_TEXT_OUTPUT = (
    '• The user asked me to reply with exactly "OK". Simple instruction.\n'
    "\n"
    "• OK\n"
    "\n"
    "To resume this session: kimi -r session_f00f44f4-729f-48e9-8459-ff25c43c5923\n"
)

# Real `kimi --output-format stream-json` output captured 2026-07-12: NDJSON
# events, still no usage/token fields.
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


class TestParseUsageKimi(unittest.TestCase):
    def test_kimi_text_output_returns_none(self):
        self.assertIsNone(parse_usage("kimi", KIMI_TEXT_OUTPUT))

    def test_kimi_stream_json_output_returns_none(self):
        self.assertIsNone(parse_usage("kimi", KIMI_STREAM_JSON_OUTPUT))


class TestParseUsageGarbage(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
