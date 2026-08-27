"""Extract real test invocations from Antigravity (``agy``) transcripts.

Antigravity writes one JSONL transcript per conversation at
``~/.gemini/antigravity-cli/brain/<conversation-id>/.system_generated/logs/transcript.jsonl``.
Unlike Claude Code it keys transcripts by conversation id alone, so no cwd
slug is involved and the reader needs no worktree directory.

Verified against real transcripts 2026-08-27. A shell run is a
``type: "PLANNER_RESPONSE"`` record whose ``tool_calls`` carries a single
``run_command`` entry; its ``args.CommandLine`` is a *JSON-quoted* string
(``"\\"pytest -q\\""``). The result is not a structured field: it is the
``content`` of the immediately following record, a fixed text block of the
form::

    Created At: 2026-08-27T09:59:06+01:00
    Completed At: 2026-08-27T09:59:51+01:00

    The command exited with code 0.
    Output:
    631 passed

``Stdout:`` appears in place of ``Output:`` in some runs. A command handed to
the background task runner gets no ``Completed At`` and no exit code — its
outcome never re-enters the transcript, so it is reported with nulls rather
than an estimate.

Defensive by contract, matching ``wirelog.py`` and ``session_log_claude.py``:
the transcript is an internal recovery stream, so oversized lines, malformed
JSON, unpaired calls, and unparseable timestamps yield skipped records or null
fields — never crashes, never estimates.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aet.test_runners import resolve_test_command
from aet.usage import _MAX_WIRE_LINE_CHARS

# Antigravity names every conversation directory with a UUID or identifier.
# Anything with path traversal characters is refused rather than joined onto a
# path: a session reference reaches the filesystem, and an id shaped like
# ``../../etc`` must never resolve.
_CONVERSATION_ID_RE = re.compile(r"\A[A-Za-z0-9_-]+\Z")

_CREATED_AT_RE = re.compile(r"^Created At:[ \t]*(\S+)", re.MULTILINE)
_COMPLETED_AT_RE = re.compile(r"^Completed At:[ \t]*(\S+)", re.MULTILINE)
_EXIT_CODE_RE = re.compile(r"^The command exited with code (-?\d+)\.", re.MULTILINE)
_OUTPUT_RE = re.compile(r"^(?:Output|Stdout):\n(.*)\Z", re.MULTILINE | re.DOTALL)


def is_conversation_id(value: Any) -> bool:
    """Return True when ``value`` is a well-formed Antigravity conversation id."""
    return isinstance(value, str) and _CONVERSATION_ID_RE.match(value) is not None


def transcript_path_for(conversation_id: str, home: Path | None = None) -> Path:
    """Return the transcript path for an Antigravity conversation.

    ``home`` defaults to ``~/.gemini/antigravity-cli``; callers may override it
    for tests or non-standard installs.
    """
    if home is None:
        home = Path.home() / ".gemini" / "antigravity-cli"
    return (
        home
        / "brain"
        / conversation_id
        / ".system_generated"
        / "logs"
        / "transcript.jsonl"
    )


def extract_test_invocations(
    conversation_id: str,
    worktree_dir: str | None = None,
    home: Path | None = None,
) -> list[dict[str, Any]]:
    """Extract test invocations from an Antigravity transcript.

    ``conversation_id`` is the identifier resolved from the JSON envelope.
    ``worktree_dir`` is accepted for seam symmetry with the Claude reader and
    deliberately unused: Antigravity keys transcripts by conversation id, and
    a command may legitimately run from a subdirectory of the worktree, so
    filtering on cwd would drop real runs. Returns ``[]`` when the transcript
    cannot be located or read.

    Returns a list of ``{command, start_time, end_time, duration_seconds,
    exit_code, output}`` dicts ordered by start time. ``start_time``/``end_time``
    are ISO-8601 UTC strings (or ``None`` when the record carried no usable
    timestamp); ``duration_seconds`` is ``None`` whenever either endpoint is
    missing.
    """
    if not is_conversation_id(conversation_id):
        return []
    transcript_path = transcript_path_for(conversation_id, home=home)
    invocations: list[dict[str, Any]] = []
    pending: dict[str, Any] | None = None
    try:
        f = transcript_path.open(encoding="utf-8", errors="replace")
    except OSError:
        return invocations
    with f:
        for line in f:
            if len(line) > _MAX_WIRE_LINE_CHARS:
                # An oversized line also orphans the call it would have
                # answered; the pending call keeps its null result.
                continue
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if not isinstance(record, dict):
                continue
            call = _run_command_call(record)
            if pending is not None:
                # Only the record immediately after a call carries its result;
                # anything else leaves the call unpaired.
                if call is None:
                    _apply_result(pending, record.get("content"))
                invocations.append(pending)
                pending = None
            if call is not None:
                pending = call
    if pending is not None:
        invocations.append(pending)
    invocations.sort(key=lambda inv: inv.get("start_time") or "")
    return invocations


def _run_command_call(record: dict[str, Any]) -> dict[str, Any] | None:
    """Return a started invocation for a test-running ``run_command``, else None."""
    tool_calls = record.get("tool_calls")
    if not isinstance(tool_calls, list):
        return None
    for tool_call in tool_calls:
        if not isinstance(tool_call, dict) or tool_call.get("name") != "run_command":
            continue
        args = tool_call.get("args")
        if not isinstance(args, dict):
            continue
        command = _unquote(args.get("CommandLine"))
        if command is None or resolve_test_command(command) is None:
            continue
        return {
            "command": command,
            "start_time": _iso_from_dt(_parse_iso_timestamp(record.get("created_at"))),
            "end_time": None,
            "duration_seconds": None,
            "exit_code": None,
            "output": None,
        }
    return None


def _apply_result(invocation: dict[str, Any], content: Any) -> None:
    """Complete ``invocation`` from the result record's text block.

    The block's own ``Created At`` is the command's start — it trails the
    planner record by however long the model streamed — so it supersedes the
    tool-call timestamp when present.
    """
    if not isinstance(content, str):
        return
    start_dt = _search_timestamp(_CREATED_AT_RE, content)
    if start_dt is not None:
        invocation["start_time"] = _iso_from_dt(start_dt)
    else:
        start_dt = _parse_iso_timestamp(invocation["start_time"])
    end_dt = _search_timestamp(_COMPLETED_AT_RE, content)
    invocation["end_time"] = _iso_from_dt(end_dt)
    if start_dt is not None and end_dt is not None and end_dt >= start_dt:
        invocation["duration_seconds"] = (end_dt - start_dt).total_seconds()
    exit_match = _EXIT_CODE_RE.search(content)
    if exit_match is not None:
        invocation["exit_code"] = int(exit_match.group(1))
    output_match = _OUTPUT_RE.search(content)
    if output_match is not None:
        invocation["output"] = output_match.group(1)


def _unquote(value: Any) -> str | None:
    """Return a ``run_command`` arg as plain text.

    Antigravity stores each arg as its JSON encoding, so ``CommandLine`` on a
    real transcript arrives double-quoted. Values that are already plain
    strings pass through unchanged.
    """
    if not isinstance(value, str):
        return None
    if value.startswith('"'):
        try:
            decoded = json.loads(value)
        except ValueError:
            return value
        return decoded if isinstance(decoded, str) else value
    return value


def _search_timestamp(pattern: re.Pattern[str], content: str) -> datetime | None:
    """Return the first timestamp ``pattern`` captures in ``content``, or None."""
    match = pattern.search(content)
    if match is None:
        return None
    return _parse_iso_timestamp(match.group(1))


def _parse_iso_timestamp(value: Any) -> datetime | None:
    """Parse an ISO-8601 timestamp string to an aware UTC datetime.

    The record-level ``created_at`` is UTC (``...Z``); the timestamps inside a
    result block are local with an offset. Both normalise to UTC here.
    """
    if not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _iso_from_dt(dt: datetime | None) -> str | None:
    """Format an aware datetime as an ISO-8601 UTC string."""
    if dt is None:
        return None
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
