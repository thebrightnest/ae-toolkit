"""Parse usage (tokens, cost) from agent CLI headless output.

Each supported CLI declares a machine-readable usage mode in
``cli_adapter.ADAPTERS``; this module turns the captured stdout of such a
session into a ``{"input_tokens", "output_tokens", "total_tokens",
"cost_usd"}`` dict, or ``None`` when nothing parseable was emitted. Numbers
are never estimated from prompt or response size — an unparseable session
records ``None`` and the telemetry schema's null contract applies.
"""

from __future__ import annotations

import json
import re
from typing import Any

# Only the tail of captured output is scanned: usage blocks are emitted at
# exit, and sessions can stream megabytes. Matches the orchestrator's tee
# buffer size so the parser never sees a larger window than capture kept.
TAIL_SCAN_BYTES = 256 * 1024

_RESULT_MARKER_RE = re.compile(r'\{\s*"type"\s*:\s*"result"')


def parse_usage(agent_cli: str, text: str) -> dict[str, Any] | None:
    """Parse usage from captured CLI output, or return ``None``.

    ``text`` is the (bounded) captured stdout+stderr of one headless session.
    Unknown CLIs and unparseable output both yield ``None``.
    """
    if not text:
        return None
    # Bound the scan to the tail: usage blocks are emitted at exit, and a
    # long session can stream megabytes. This mirrors the orchestrator's tee
    # buffer so parsing never loads more than capture would keep.
    if len(text) > TAIL_SCAN_BYTES:
        text = text[-TAIL_SCAN_BYTES:]
    if agent_cli == "claude":
        return _parse_claude(text)
    return None


def _parse_claude(text: str) -> dict[str, Any] | None:
    """Parse claude's ``--output-format json`` envelope.

    The envelope is a single JSON array; the final element with
    ``type == "result"`` carries ``usage`` and ``total_cost_usd``.
    """
    result = _find_result_element(text)
    if result is None:
        return None
    usage = result.get("usage")
    if not isinstance(usage, dict):
        return None
    input_tokens = (
        _as_int(usage.get("input_tokens"))
        + _as_int(usage.get("cache_creation_input_tokens"))
        + _as_int(usage.get("cache_read_input_tokens"))
    )
    output_tokens = _as_int(usage.get("output_tokens"))
    cost = result.get("total_cost_usd")
    cost_usd = float(cost) if isinstance(cost, (int, float)) and not isinstance(cost, bool) else None
    total = input_tokens + output_tokens
    if total == 0 and cost_usd is None:
        return None
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total,
        "cost_usd": cost_usd,
    }


def _find_result_element(text: str) -> dict[str, Any] | None:
    """Locate the ``type == "result"`` object in claude's JSON output.

    The common case is a whole-document parse. When the capture buffer cut
    the head of the (single-line) envelope, fall back to decoding from the
    last result marker — the result element sits at the end of the array.
    """
    stripped = text.strip()
    if stripped:
        try:
            doc = json.loads(stripped)
        except ValueError:
            doc = None
        if isinstance(doc, list):
            for element in reversed(doc):
                if isinstance(element, dict) and element.get("type") == "result":
                    return element
        elif isinstance(doc, dict) and doc.get("type") == "result":
            return doc

    markers = list(_RESULT_MARKER_RE.finditer(text))
    if not markers:
        return None
    decoder = json.JSONDecoder()
    try:
        element, _end = decoder.raw_decode(text, markers[-1].start())
    except ValueError:
        return None
    if isinstance(element, dict) and element.get("type") == "result":
        return element
    return None


def _as_int(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0
