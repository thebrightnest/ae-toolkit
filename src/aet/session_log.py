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


def extract_test_invocations(
    agent_cli: str,
    session_ref: str,
    worktree_dir: str | None = None,
    home: Path | None = None,
) -> list[dict[str, Any]]:
    """Return test invocations for ``agent_cli`` from ``session_ref``.

    ``session_ref`` is an adapter-resolved session identifier (a session id
    for both kimi and Claude). ``worktree_dir`` is required for the Claude
    reader, which builds the transcript path from the cwd slug.
    ``home`` overrides the default CLI home directory (``~/.kimi-code`` or
    ``~/.claude``) for tests or non-standard installs.

    Returns ``[]`` for adapters without a reader or when the reference cannot
    be resolved to a log.
    """
    if agent_cli == "kimi":
        return wirelog.extract_test_invocations(session_ref, kimi_home=home)
    if agent_cli == "claude":
        if worktree_dir is None:
            return []
        return session_log_claude.extract_test_invocations(
            session_ref, worktree_dir, home=home
        )
    return []
