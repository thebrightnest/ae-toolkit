"""Adapter-dispatched session-log reader seam.

One call site reaches the per-CLI reader that knows how to turn a session
reference into test invocations. This mirrors ``usage.parse_usage`` (ADR-050):
callers pass ``agent_cli`` and a session reference; they never name a schema,
path template, or record type.

Supported CLIs:

- ``kimi`` — reads ``agents/*/wire.jsonl`` under a kimi session directory.
- ``claude`` — reads a Claude Code transcript JSONL file.

An unsupported CLI returns an empty list; that is an explicit, tested property
of the seam rather than an accidental silence.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from aet import session_log_claude, wirelog


def extract_test_invocations(agent_cli: str, session_ref: Path) -> list[dict[str, Any]]:
    """Return test invocations for ``agent_cli`` from ``session_ref``.

    The shape of ``session_ref`` is adapter-defined: a directory for kimi, a
    transcript file for Claude. Returns ``[]`` for adapters without a reader.
    """
    if agent_cli == "kimi":
        return wirelog.extract_test_invocations(session_ref)
    if agent_cli == "claude":
        return session_log_claude.extract_test_invocations(session_ref)
    return []
