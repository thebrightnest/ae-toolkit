"""Extract real test invocations from Claude Code session transcripts.

Claude Code writes one JSONL transcript per session at
``~/.claude/projects/<cwd-slug>/<sessionId>.jsonl``. Assistant records carry
``message.content[]`` blocks of ``type: "tool_use"`` with ``name: "Bash"``,
``id``, and ``input.command``; the paired user record carries a block of
``type: "tool_result"`` with ``tool_use_id``, ``is_error``, and ``content``.
Every record carries an ISO-8601 ``timestamp``.

Defensive by contract, matching ``wirelog.py``: the transcript schema is an
internal recovery stream. Oversized lines, malformed JSON, missing pairs, and
missing ``timestamp`` fields yield null fields or skipped records — never
crashes, never estimates.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aet.test_runners import resolve_test_command
from aet.usage import _MAX_WIRE_LINE_CHARS


def extract_test_invocations(transcript_path: Path) -> list[dict[str, Any]]:
    """Extract test invocations from a Claude Code transcript.

    Returns a list of ``{command, start_time, end_time, duration_seconds,
    exit_code}`` dicts, ordered by start time. ``start_time``/``end_time``
    are ISO-8601 UTC strings (or ``None`` when the record lacks a usable
    ``timestamp``); ``duration_seconds`` is ``None`` whenever either timestamp
    is missing — unpaired calls are emitted with null end/duration/exit_code,
    never an estimate.
    """
    pending: dict[str, dict[str, Any]] = {}
    invocations: list[dict[str, Any]] = []
    try:
        f = Path(transcript_path).open(encoding="utf-8", errors="replace")
    except OSError:
        return invocations
    with f:
        for line in f:
            if len(line) > _MAX_WIRE_LINE_CHARS:
                continue
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if not isinstance(record, dict):
                continue
            timestamp = record.get("timestamp")
            role = record.get("role")
            message = record.get("message")
            if not isinstance(message, dict):
                continue
            content = message.get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict):
                    continue
                block_type = block.get("type")
                if block_type == "tool_use" and role == "assistant":
                    _on_tool_use(block, timestamp, pending)
                elif block_type == "tool_result" and role == "user":
                    _on_tool_result(block, timestamp, pending, invocations)
    # Calls that never saw a result: emitted with null end/duration/exit code.
    for inv in pending.values():
        inv.pop("_start_dt", None)
        invocations.append(inv)
    invocations.sort(key=lambda inv: inv["start_time"] or "")
    return invocations


def _on_tool_use(
    block: dict, timestamp: Any, pending: dict[str, dict[str, Any]]
) -> None:
    """Stash a Bash test invocation, keyed by its tool_use id (first wins)."""
    if block.get("name") != "Bash":
        return
    tool_use_id = block.get("id")
    if not isinstance(tool_use_id, str) or tool_use_id in pending:
        return
    input_data = block.get("input")
    command = input_data.get("command") if isinstance(input_data, dict) else None
    if not isinstance(command, str) or resolve_test_command(command) is None:
        return
    start_dt = _parse_iso_timestamp(timestamp)
    pending[tool_use_id] = {
        "command": command,
        "start_time": _iso_from_dt(start_dt),
        "_start_dt": start_dt,
        "end_time": None,
        "duration_seconds": None,
        "exit_code": None,
    }


def _on_tool_result(
    block: dict,
    timestamp: Any,
    pending: dict[str, dict[str, Any]],
    invocations: list[dict[str, Any]],
) -> None:
    """Pair a tool_result with its stashed call and complete the record."""
    tool_use_id = block.get("tool_use_id")
    if not isinstance(tool_use_id, str) or tool_use_id not in pending:
        return
    inv = pending.pop(tool_use_id)
    end_dt = _parse_iso_timestamp(timestamp)
    inv["end_time"] = _iso_from_dt(end_dt)
    start_dt = inv.pop("_start_dt", None)
    if start_dt is not None and end_dt is not None and end_dt >= start_dt:
        inv["duration_seconds"] = (end_dt - start_dt).total_seconds()
    inv["exit_code"] = _exit_code_from_result(block.get("is_error"))
    invocations.append(inv)


def _exit_code_from_result(is_error: Any) -> int | None:
    """Derive the exit code from a Claude tool_result block.

    Claude signals failure with a boolean ``is_error``; unlike kimi's wire
    format there is no structured exit code in the content. A true ``is_error``
    therefore maps to ``1`` (non-zero failure observed), and false/no error
    maps to ``0``. ``None`` is reserved for unpaired calls.
    """
    if isinstance(is_error, bool):
        return 1 if is_error else 0
    return 0 if is_error is not None else None


def _parse_iso_timestamp(value: Any) -> datetime | None:
    """Parse an ISO-8601 timestamp string to an aware UTC datetime."""
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
