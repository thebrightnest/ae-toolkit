# Claude Code Token Capture Verification

## Context

`docs/plans/tap-07-claude-token-capture-verification.md` asked whether Claude Code stage
sessions really record non-null `token_count`. The archive contained three Claude stage records
with `token_count: null`, while the unit-tested parser chain had never been exercised end to end
on a live session.

## Verification Procedure

Run a live Claude Code headless session, preserve the raw stdout, and walk the parser chain:

1. **Envelope generation.** Invoke the same command shape the orchestrator builds:

   ```bash
   claude --dangerously-skip-permissions --output-format json \
     -p "Reply with exactly 'OK' and then exit without modifying any files."
   ```

2. **Envelope reaches capture.** The session exited 0 and produced a single JSON array of
   6,207 characters, well inside the `TAIL_SCAN_BYTES` window (`256 KiB`).
3. **Envelope reaches `parse_usage`.** Ran `parse_usage("claude", <captured stdout>)` from
   `src/aet/usage.py`.
4. **Parse result.** The function returned:

   ```json
   {
     "input_tokens": 21395,
     "output_tokens": 4,
     "total_tokens": 21399,
     "cost_usd": 0.21403999999999998
   }
   ```

## Findings per Link

| Link | Finding |
|---|---|
| `--output-format json` is appended before the prompt flag | Confirmed: `cli_adapter.py` emits usage-mode flags at positions 2–3, prompt at positions 4–5. |
| JSON envelope reaches the captured stdout tail | Confirmed: envelope is present and within the tail window. |
| `_find_result_element` locates the `type == "result"` object | Confirmed: parses the final array element. |
| `usage` block is present and numeric | Confirmed: `input_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`, `output_tokens` all present. |
| `total == 0 and cost_usd is None` early return avoided | Confirmed: total is non-zero and cost is present. |

## Defect Determination

No defect was found. The current code correctly captures and parses Claude Code token usage
from a live headless session.

## Explanation of the Three Archived Nulls

The three null Claude records predate the wiring of `--output-format json` into the adapter
(`cli_adapter.py` now declares `usage_mode="json-envelope"`). Before that change, Claude stdout
carried no machine-readable usage envelope, so `parse_usage` legitimately returned `None` and
the stage record kept `token_count: null`. Those sessions are historical artifacts, not evidence
of a parser bug.

## Artifacts Produced

- `tests/fixtures/usage/claude_live_envelope.json` — redacted live envelope fixture.
- `tests/usage/test_usage_parsing.py::TestParseUsageClaude::test_claude_live_captured_envelope_parses` —
  regression test proving the captured envelope parses to the values above.

## Conclusion

Claude Code token capture is verified end to end. No code change was required.
