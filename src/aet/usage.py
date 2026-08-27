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
from pathlib import Path
from typing import Any

# Only the tail of captured output is scanned: usage blocks are emitted at
# exit, and sessions can stream megabytes. Matches the orchestrator's tee
# buffer size so the parser never sees a larger window than capture kept.
TAIL_SCAN_BYTES = 256 * 1024

_RESULT_MARKER_RE = re.compile(r'\{\s*"type"\s*:\s*"result"')
_AGY_ENVELOPE_RE = re.compile(r'\{\s*"conversation_id"\s*:')

# Kimi prints no usage to stdout; the resume hint at exit carries the session
# id, and per-step usage lives in that session's wire files. Both `session_`
# and `ses_` id prefixes exist in the wild.
_KIMI_RESUME_HINT_RE = re.compile(r"kimi -r ((?:session_|ses_)[A-Za-z0-9_-]+)")

# Wire lines are JSONL; a pathological line is skipped rather than loaded
# whole. Real lines are ≤ a few hundred KB (config.update carries prompts).
_MAX_WIRE_LINE_CHARS = 4 * 1024 * 1024

# USD per 1M tokens as (input, output), keyed by the modelAlias from the
# wire's `config.update` event. Verified 2026-07-13: the alias this CLI emits
# (`kimi-code/kimi-for-coding`) is a subscription/quota plan with no published
# per-token price (platform.moonshot.ai/docs/pricing/chat), so the table is
# empty and `cost_usd` records null. Add dated entries here when a
# per-token-priced alias appears — never invent a price.
_KIMI_MODEL_PRICES_USD_PER_1M: dict[str, tuple[float, float]] = {}


def parse_usage(
    agent_cli: str, text: str, *, kimi_home: str | Path | None = None
) -> dict[str, Any] | None:
    """Parse usage from captured CLI output, or return ``None``.

    ``text`` is the (bounded) captured stdout+stderr of one headless session.
    For ``kimi`` the stdout only supplies the session id; usage is then read
    from that session's wire files under ``kimi_home`` (default
    ``~/.kimi-code``). Unknown CLIs and unparseable output both yield
    ``None``.
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
    if agent_cli == "kimi":
        return _parse_kimi(text, kimi_home)
    if agent_cli == "agy":
        return _parse_agy(text)
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


def resolve_kimi_session_id_from_output(text: str) -> str | None:
    """Return the session id from a kimi resume hint, or ``None``.

    This is the machine-independent identifier stored on stage records; path
    resolution happens later, at test-run extraction time, via
    ``resolve_kimi_session_dir_from_output`` or ``_resolve_kimi_session_dir``.
    """
    if not text:
        return None
    if len(text) > TAIL_SCAN_BYTES:
        text = text[-TAIL_SCAN_BYTES:]
    hints = _KIMI_RESUME_HINT_RE.findall(text)
    if not hints:
        return None
    return hints[-1]


def resolve_kimi_session_dir_from_output(
    text: str, kimi_home: str | Path | None = None
) -> Path | None:
    """Resolve a kimi session's wire dir from captured CLI output.

    Kimi prints a resume hint carrying the session id at exit; this is the
    same resolution ``parse_usage`` performs for token extraction — one
    shared path, so wire-log consumers (usage, test-run extraction) never
    fork the hint parsing. Returns ``None`` when no hint is present or the
    session dir cannot be located.
    """
    session_id = resolve_kimi_session_id_from_output(text)
    if session_id is None:
        return None
    home = Path(kimi_home) if kimi_home is not None else Path.home() / ".kimi-code"
    return _resolve_kimi_session_dir(home, session_id)


def _parse_kimi(text: str, kimi_home: str | Path | None) -> dict[str, Any] | None:
    """Parse kimi usage from the session's on-disk wire files.

    Kimi (verified 0.23.6) writes per-step usage to
    ``~/.kimi-code/sessions/<workDirKey>/<sessionId>/agents/<agentId>/wire.jsonl``
    and prints a resume hint carrying the session id at exit. Wire files are
    append-only and read after process exit, so parsing is race-free. The
    wire schema is a recovery stream, not a documented public contract —
    re-verify on kimi upgrades.
    """
    session_dir = resolve_kimi_session_dir_from_output(text, kimi_home)
    if session_dir is None:
        return None
    return _sum_wire_usage(session_dir)


def resolve_kimi_session_dir_from_id(
    session_id: str, kimi_home: str | Path | None = None
) -> Path | None:
    """Resolve a kimi session directory from its session id.

    Looks up ``session_index.jsonl`` first, then falls back to globbing the
    ``sessions/*/<session_id>`` layout under ``kimi_home`` (default
    ``~/.kimi-code``).
    """
    home = Path(kimi_home) if kimi_home is not None else Path.home() / ".kimi-code"
    return _resolve_kimi_session_dir(home, session_id)


def _resolve_kimi_session_dir(home: Path, session_id: str) -> Path | None:
    """Locate a session dir via session_index.jsonl, else glob the layout."""
    index = home / "session_index.jsonl"
    if index.is_file():
        try:
            with index.open(encoding="utf-8", errors="replace") as f:
                for line in f:
                    if len(line) > _MAX_WIRE_LINE_CHARS:
                        continue
                    try:
                        entry = json.loads(line)
                    except ValueError:
                        continue
                    if isinstance(entry, dict) and entry.get("sessionId") == session_id:
                        session_dir = Path(str(entry.get("sessionDir", "")))
                        if session_dir.is_dir():
                            return session_dir
        except OSError:
            pass
    for candidate in sorted(home.glob(f"sessions/*/{session_id}")):
        if candidate.is_dir():
            return candidate
    return None


def _sum_wire_usage(session_dir: Path) -> dict[str, Any] | None:
    """Sum ``step.end`` usage across every agent wire in a session dir.

    Envelopes (``context.append_loop_event``) are unwrapped; inner events
    with ``type == "step.end"`` are deduped by ``uuid`` so a duplicated or
    replayed line cannot double-count. ``modelAlias`` comes from the wire's
    ``config.update`` event.
    """
    seen_uuids: set[str] = set()
    input_tokens = 0
    output_tokens = 0
    found = False
    model_alias: str | None = None
    for wire in sorted(session_dir.glob("agents/*/wire.jsonl")):
        try:
            f = wire.open(encoding="utf-8", errors="replace")
        except OSError:
            continue
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
                if record.get("type") == "config.update":
                    alias = record.get("modelAlias")
                    if isinstance(alias, str):
                        model_alias = alias
                    continue
                if record.get("type") != "context.append_loop_event":
                    continue
                event = record.get("event")
                if not isinstance(event, dict) or event.get("type") != "step.end":
                    continue
                uuid = event.get("uuid")
                if isinstance(uuid, str):
                    if uuid in seen_uuids:
                        continue
                    seen_uuids.add(uuid)
                usage = event.get("usage")
                if not isinstance(usage, dict):
                    continue
                input_tokens += (
                    _as_int(usage.get("inputOther"))
                    + _as_int(usage.get("inputCacheRead"))
                    + _as_int(usage.get("inputCacheCreation"))
                )
                output_tokens += _as_int(usage.get("output"))
                found = True
    if not found:
        return None
    cost_usd = None
    prices = _KIMI_MODEL_PRICES_USD_PER_1M.get(model_alias or "")
    if prices is not None:
        cost_usd = (input_tokens * prices[0] + output_tokens * prices[1]) / 1_000_000
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "cost_usd": cost_usd,
    }


def _as_int(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _parse_agy(text: str) -> dict[str, Any] | None:
    """Parse Antigravity's JSON envelope.

    agy prints a JSON object with `conversation_id`, `status`, and `usage`.
    Cache reads are added to `input_tokens`; thinking tokens to `output_tokens`.
    `cost_usd` is null (Antigravity does not publish per-token pricing in the envelope).
    """
    doc = _find_agy_envelope(text)
    if doc is None:
        return None
    usage = doc.get("usage")
    if not isinstance(usage, dict):
        return None
    input_tokens = _as_int(usage.get("input_tokens")) + _as_int(
        usage.get("cache_read_tokens")
    )
    output_tokens = _as_int(usage.get("output_tokens")) + _as_int(
        usage.get("thinking_tokens")
    )
    total = input_tokens + output_tokens
    if total == 0:
        return None
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total,
        "cost_usd": None,
    }


def resolve_agy_conversation_id_from_output(text: str) -> str | None:
    """Return the conversation id from an agy JSON envelope, or ``None``."""
    if not text:
        return None
    if len(text) > TAIL_SCAN_BYTES:
        text = text[-TAIL_SCAN_BYTES:]
    doc = _find_agy_envelope(text)
    if doc is None:
        return None
    conv_id = doc.get("conversation_id")
    if isinstance(conv_id, str) and conv_id:
        return conv_id
    return None


def _find_agy_result_event(text: str) -> dict[str, Any] | None:
    """Return the payload of the last stream-json ``result`` event, or ``None``.

    Under ``--output-format stream-json`` agy emits NDJSON and wraps the final
    payload as ``{"event": "result", "result": {...}}``. That inner object is
    field-for-field the same envelope ``--output-format json`` prints on its
    own, so unwrapping it here lets one parser serve both output modes.

    The tail bound can truncate the first line, and a session killed before it
    finished emits no result event at all; both are ordinary and yield ``None``.
    """
    found: dict[str, Any] | None = None
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("{") or '"result"' not in line:
            continue
        try:
            doc = json.loads(line)
        except ValueError:
            continue
        if not isinstance(doc, dict) or doc.get("event") != "result":
            continue
        payload = doc.get("result")
        if isinstance(payload, dict) and "conversation_id" in payload:
            found = payload
    return found


def _find_agy_envelope(text: str) -> dict[str, Any] | None:
    """Locate the JSON envelope carrying conversation_id in agy's output.

    Handles both output modes: the stream-json ``result`` event is preferred
    when present, since a stream also carries ``init`` and ``step_update``
    objects with a ``conversation_id`` but no usage block.
    """
    result_event = _find_agy_result_event(text)
    if result_event is not None:
        return result_event

    stripped = text.strip()
    if stripped:
        try:
            doc = json.loads(stripped)
            if isinstance(doc, dict) and "conversation_id" in doc:
                return doc
        except ValueError:
            pass

    markers = list(_AGY_ENVELOPE_RE.finditer(text))
    if not markers:
        return None
    decoder = json.JSONDecoder()
    try:
        element, _end = decoder.raw_decode(text, markers[-1].start())
        if isinstance(element, dict) and "conversation_id" in element:
            return element
    except ValueError:
        return None
    return None
