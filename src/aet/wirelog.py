"""Extract real test invocations from kimi session wire logs.

Every kimi session records its tool calls in
``~/.kimi-code/sessions/<workDirKey>/<sessionId>/agents/<agentId>/wire.jsonl``
(verified against kimi 0.23.x). A Bash tool call whose command is a test
invocation, paired with its ``tool.result`` event, yields one record with the
real command, start/end timestamps, measured duration, and exit code.

Defensive by contract (mirrors ``usage.py``): the wire schema is an internal
recovery stream, not a public contract. Oversized lines, malformed JSON,
missing pairs, and missing ``time`` fields yield null fields or skipped
records — never crashes, never estimates.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aet import test_runners
from aet.usage import _MAX_WIRE_LINE_CHARS, resolve_kimi_session_dir_from_id

# The Bash tool appends this trailer to the output of a failed command; it is
# the only place a measured exit code appears in a wire tool.result.
_EXIT_CODE_RE = re.compile(r"Command failed with exit code: (\d+)")


def is_test_command(command: str) -> bool:
    """Return True when a shell command resolves to a test runner.

    Detection delegates to the shared runner registry
    (``test_runners.resolve_test_command``) — the same parse that feeds
    ``telemetry.classify_test_scope``, so a detected command is classifiable
    by construction.
    """
    return test_runners.resolve_test_command(command) is not None


def extract_test_invocations(
    session_id: str, kimi_home: str | Path | None = None
) -> list[dict[str, Any]]:
    """Extract test invocations from every agent wire in a kimi session.

    ``session_id`` is the identifier resolved from the resume hint; the
    session directory is located via ``usage.resolve_kimi_session_dir_from_id``.

    Returns a list of ``{command, start_time, end_time, duration_seconds,
    exit_code, output}`` dicts, ordered by start time. ``start_time``/``end_time``
    are ISO-8601 UTC strings (or ``None`` when the wire event lacks a usable
    ``time``); ``duration_seconds`` is ``None`` whenever either timestamp is
    missing — unpaired calls are emitted with null end/duration, never an
    estimate.
    """
    invocations: list[dict[str, Any]] = []
    session_dir = resolve_kimi_session_dir_from_id(session_id, kimi_home)
    if session_dir is None:
        return invocations
    for wire in sorted(session_dir.glob("agents/*/wire.jsonl")):
        invocations.extend(_extract_from_wire(wire))
    invocations.sort(key=lambda inv: inv["start_time"] or "")
    return invocations


def _extract_from_wire(wire: Path) -> list[dict[str, Any]]:
    """Extract test invocations from one agent's wire.jsonl."""
    pending: dict[str, dict[str, Any]] = {}
    invocations: list[dict[str, Any]] = []
    try:
        f = wire.open(encoding="utf-8", errors="replace")
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
            if record.get("type") != "context.append_loop_event":
                continue
            event = record.get("event")
            if not isinstance(event, dict):
                continue
            event_type = event.get("type")
            if event_type == "tool.call":
                _on_tool_call(event, record.get("time"), pending)
            elif event_type == "tool.result":
                _on_tool_result(event, record.get("time"), pending, invocations)
    # Calls that never saw a result: emitted with null end/duration/exit code.
    for inv in pending.values():
        inv.pop("_start_ms")
        invocations.append(inv)
    return invocations


def _on_tool_call(event: dict, time: Any, pending: dict[str, dict[str, Any]]) -> None:
    """Stash a Bash test invocation, keyed by its call uuid (first wins)."""
    if event.get("name") != "Bash":
        return
    uuid = event.get("uuid")
    if not isinstance(uuid, str) or uuid in pending:
        return
    args = event.get("args")
    command = args.get("command") if isinstance(args, dict) else None
    if not isinstance(command, str) or not is_test_command(command):
        return
    pending[uuid] = {
        "command": command,
        "start_time": _iso_from_ms(time),
        "_start_ms": time if _is_number(time) else None,
        "end_time": None,
        "duration_seconds": None,
        "exit_code": None,
        "output": None,
    }


def _on_tool_result(
    event: dict,
    time: Any,
    pending: dict[str, dict[str, Any]],
    invocations: list[dict[str, Any]],
) -> None:
    """Pair a tool.result with its stashed call and complete the record."""
    uuid = event.get("parentUuid")
    if not isinstance(uuid, str) or uuid not in pending:
        uuid = event.get("toolCallId")
    if not isinstance(uuid, str) or uuid not in pending:
        return
    inv = pending.pop(uuid)
    inv["end_time"] = _iso_from_ms(time)
    start_ms = inv.pop("_start_ms")
    if start_ms is not None and _is_number(time):
        duration = (time - start_ms) / 1000.0
        if duration >= 0:
            inv["duration_seconds"] = duration
    inv["exit_code"] = _exit_code_from_result(event.get("result"))
    inv["output"] = _output_from_result(event.get("result"))
    invocations.append(inv)


def _output_from_result(result: Any) -> str | None:
    """Return the command's own output text, or ``None`` when unavailable.

    Consumers read it for markers a command prints about itself — notably the
    resolved pytest targets of a ``make validate``, whose sub-make the session
    log never sees. Anything but a string is ``None``: the field reports what
    the wire carried, never a rendering of it.
    """
    if not isinstance(result, dict):
        return None
    output = result.get("output")
    return output if isinstance(output, str) else None


def _exit_code_from_result(result: Any) -> int | None:
    """Derive the exit code from a wire tool.result payload.

    The wire carries no structured exit code. The Bash tool appends
    ``Command failed with exit code: N`` to the output of failed commands
    and sets ``isError``; a result without ``isError`` exited 0. A failure
    without a parseable code (killed by timeout, premature close) yields
    ``None`` — the code is unknown, never estimated.
    """
    if not isinstance(result, dict):
        return None
    if not result.get("isError"):
        return 0
    output = result.get("output")
    if isinstance(output, str):
        matches = _EXIT_CODE_RE.findall(output)
        if matches:
            return int(matches[-1])
    return None


def _iso_from_ms(time: Any) -> str | None:
    """Convert an epoch-millis wire ``time`` to an ISO-8601 UTC string."""
    if not _is_number(time):
        return None
    return datetime.fromtimestamp(time / 1000, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)
