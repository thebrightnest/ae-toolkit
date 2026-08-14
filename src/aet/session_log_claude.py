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
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aet.test_runners import resolve_test_command
from aet.usage import _MAX_WIRE_LINE_CHARS

# Every character outside ``[A-Za-z0-9-]`` becomes ``-`` in a Claude Code project
# slug. Derived from the observed corpus, not guessed: ``/`` (``/Users/x`` →
# ``-Users-x``), ``.`` (``p.rocha`` → ``p-rocha``, and ``.worktrees`` → ``-worktrees``,
# so a path separator followed by a dot yields ``--worktrees``), and ``_``
# (``ki_mcp`` → ``ki-mcp``). Case is preserved and consecutive dashes are **not**
# collapsed.
_SLUG_UNSAFE = re.compile(r"[^A-Za-z0-9-]")


def cwd_slug(cwd: str) -> str:
    """Return the slug Claude Code uses for ``cwd`` in its projects directory.

    Verified against real project directories: ``/Users/alice/proj`` →
    ``-Users-alice-proj``, ``/private/tmp`` → ``-private-tmp``, and
    ``/Users/p.rocha/Work/ae-toolkit/.worktrees/t`` →
    ``-Users-p-rocha-Work-ae-toolkit--worktrees-t``. Trailing separators are
    stripped before slugging so ``/tmp/`` and ``/tmp`` share one directory.

    Replacing only ``/`` — as this did until the fix — silently missed every
    orchestrated session, because an AET worktree always lives under
    ``.worktrees/``, and every user whose name contains a dot. A missed slug
    yields a path that does not exist, which reads as "no test invocations"
    rather than as an error.
    """
    return _SLUG_UNSAFE.sub("-", cwd.rstrip("/"))


def transcript_path_for(
    cwd: str, session_id: str, home: Path | None = None
) -> Path:
    """Return the Claude Code transcript path for a session.

    ``cwd`` is resolved before slugging so symlinked worktrees (e.g.
    ``.worktrees/foo``) map to the same slug as the real path Claude logged.
    ``home`` defaults to ``~/.claude``; callers may override it for tests or
    non-standard installs.
    """
    if home is None:
        home = Path.home() / ".claude"
    return home / "projects" / cwd_slug(str(Path(cwd).resolve())) / f"{session_id}.jsonl"


def _record_role(record: dict[str, Any], message: Any) -> str | None:
    """Return ``"assistant"``/``"user"`` for a transcript record.

    Claude Code puts the role at ``message.role`` and mirrors it in the
    top-level ``type`` field; it emits no top-level ``role``. Reading only
    ``record["role"]`` — as this did until the fix — matched nothing on a real
    transcript, so no tool call was ever paired and the reader always returned
    an empty list. ``record["role"]`` is still accepted last so the older
    hand-written fixture keeps resolving.
    """
    if isinstance(message, dict):
        role = message.get("role")
        if isinstance(role, str):
            return role
    for key in ("type", "role"):
        value = record.get(key)
        if isinstance(value, str):
            return value
    return None


def extract_test_invocations(
    session_id: str, worktree_dir: str, home: Path | None = None
) -> list[dict[str, Any]]:
    """Extract test invocations from a Claude Code transcript.

    ``session_id`` is the identifier resolved from the result envelope;
    ``worktree_dir`` is the session's cwd, used to build the transcript path
    via ``transcript_path_for``. Returns ``[]`` when the transcript cannot be
    located or read.

    Returns a list of ``{command, start_time, end_time, duration_seconds,
    exit_code, output}`` dicts, ordered by start time. ``start_time``/``end_time``
    are ISO-8601 UTC strings (or ``None`` when the record lacks a usable
    ``timestamp``); ``duration_seconds`` is ``None`` whenever either timestamp
    is missing — unpaired calls are emitted with null end/duration/exit_code,
    never an estimate.
    """
    transcript_path = transcript_path_for(worktree_dir, session_id, home=home)
    pending: dict[str, dict[str, Any]] = {}
    invocations: list[dict[str, Any]] = []
    try:
        f = transcript_path.open(encoding="utf-8", errors="replace")
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
            message = record.get("message")
            role = _record_role(record, message)
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
        "output": None,
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
    inv["output"] = _output_from_content(block.get("content"))
    invocations.append(inv)


def _output_from_content(content: Any) -> str | None:
    """Return the command's own output text, or ``None`` when unavailable.

    Claude's ``tool_result`` content is either a plain string or a list of
    content blocks; the text blocks are joined in order. Anything else is
    ``None`` — the field reports what the transcript carried, never a
    rendering of it.
    """
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return None
    texts = [
        block["text"]
        for block in content
        if isinstance(block, dict)
        and block.get("type") == "text"
        and isinstance(block.get("text"), str)
    ]
    return "\n".join(texts) if texts else None


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
