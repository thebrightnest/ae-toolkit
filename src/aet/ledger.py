"""Content-addressed provenance ledger for aet-work events.

The ledger is an append-only, commutative event store.  Each event has a
deterministic id derived from ``source:task:kind:(ref | occurred_at)``, so
duplicate writes from independent callers are no-ops.  Events reference
external artifacts by hash or path only; verdicts, evidence, and gate
payloads stay in their own files.

Events without an external ``ref`` must carry a caller-supplied
``occurred_at`` timestamp.  The store boundary enforces this for every caller;
it never mints an ``occurred_at`` from wall-clock time.  The reserved source
``ingest-backfill`` is rejected so readers can safely filter reconstructed
events.

**Append-only is literal, and corruption is loud.**  Writes append one line to
the existing file; no code path rewrites it.  Loads verify every line against
its own content address and raise :class:`LedgerCorruptionError` on a
malformed line, an absent or non-string id, an id that does not match the
event body, or two events sharing an id with different bodies.  A store whose
ids no longer attest its contents has lost the only property that makes it a
provenance record, so it refuses to answer rather than answering from a
silently reduced subset.  Read failures raise too — ADR-033 §3 keeps storage
fail-closed, and a load that reported an unreadable file as an empty one led
the writer to persist that emptiness.  :func:`verify` enumerates every problem
at once for repair tooling.

The address covers the identity tuple only, never ``payload``: widening it
would change every existing id and break the idempotence that makes duplicate
writes no-ops (ADR-055).
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from filelock import FileLock

ALLOWED_KINDS = frozenset({"cut", "stage", "verdict", "land"})
ALLOWED_REF_KINDS = frozenset({"git-sha", "pr", "plan-hash", "evidence-path"})
RESERVED_SOURCE = "ingest-backfill"
SCHEMA_VERSION = 1

# Appended to every corruption report: the ledger cannot be re-derived from
# other state, so the remedy is always restore-or-rebuild, never hand-repair.
_REPAIR_HINT = (
    "The ledger is append-only and content-addressed: an edited line's id no "
    "longer attests its body, and the original cannot be re-derived. Restore "
    "the file from a backup, or delete it and rebuild provenance from the "
    "queue with `aet state audit`. Never hand-edit it."
)


class LedgerCorruptionError(RuntimeError):
    """Raised when the ledger on disk does not match its content addresses."""


def _canonical_json(value: Any) -> bytes:
    """Serialize ``value`` to stable UTF-8 JSON bytes for content addressing."""
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _event_id(source: str, task: str, kind: str, ref_or_occurred: str | None) -> str:
    """Return the deterministic sha256 id for an event tuple."""
    payload = f"{source}:{task}:{kind}:{ref_or_occurred or ''}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _expected_id(event: dict[str, Any]) -> str:
    """Recompute the content address of a persisted event.

    Mirrors the writer's key exactly: ``ref`` wins when present, otherwise
    ``occurred_at``.  Fields absent from the body stringify to ``"None"``, the
    same rendering the writer would have produced, so a missing field surfaces
    as a mismatch rather than a coincidental match.
    """
    ref = event.get("ref")
    key = ref if ref is not None else event.get("occurred_at")
    return _event_id(event.get("source"), event.get("task"), event.get("kind"), key)


def _scan(path: Path) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Read ``path`` and return ``(events_by_id, problems)``.

    Every line is verified against its own content address.  Offending lines
    are reported in ``problems`` and excluded from the returned index; the
    caller decides whether to raise.  An absent file is an empty ledger.  I/O
    errors propagate — an unreadable ledger is never reported as an empty one,
    because a caller that believed it would write a new file over live history.
    """
    events: dict[str, dict[str, Any]] = {}
    problems: list[str] = []
    if not path.exists():
        return events, problems

    with open(path, "r", encoding="utf-8") as f:
        for lineno, raw in enumerate(f, start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                problems.append(f"line {lineno}: not valid JSON ({exc})")
                continue
            if not isinstance(event, dict):
                problems.append(f"line {lineno}: event is not a JSON object")
                continue
            event_id = event.get("id")
            if not isinstance(event_id, str) or not event_id:
                problems.append(f"line {lineno}: missing or non-string 'id'")
                continue
            expected = _expected_id(event)
            if event_id != expected:
                problems.append(
                    f"line {lineno}: id does not match event body "
                    f"(stored {event_id[:12]}…, computed {expected[:12]}… from "
                    f"source={event.get('source')!r} task={event.get('task')!r} "
                    f"kind={event.get('kind')!r})"
                )
                continue
            previous = events.get(event_id)
            if previous is not None and previous != event:
                problems.append(
                    f"line {lineno}: duplicate id {event_id[:12]}… with a "
                    "different body than its earlier occurrence"
                )
                continue
            events[event_id] = event

    return events, problems


def verify(path: str | Path | None = None) -> list[str]:
    """Return every integrity problem in the ledger at ``path`` (empty when clean).

    The diagnostic counterpart to loading: it enumerates all problems instead
    of raising on the first, so a repair tool can show the whole picture.
    """
    target = Path(path) if path else Path(".agents/ledger.jsonl")
    _, problems = _scan(target)
    return problems


class Ledger:
    """Append-only, idempotent content-addressed event store."""

    def __init__(self, path: str | Path | None = None) -> None:
        """Initialize the ledger at ``path`` (default: ``.agents/ledger.jsonl``).

        Raises:
            LedgerCorruptionError: When the existing file fails verification.
                Construction is where corruption surfaces, so no caller can
                hold a Ledger whose index is quietly incomplete.
        """
        self.path = Path(path) if path else Path(".agents/ledger.jsonl")
        self._lock = FileLock(str(self.path) + ".lock")
        self._events: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        """Index existing events by id, refusing a ledger that fails verification.

        Raises:
            LedgerCorruptionError: When any line is malformed or its id does
                not attest its body.  Loading a verified-good subset would let
                a damaged store keep answering queries with silently missing
                history, and the next write would then persist that reduction.
            OSError: When the file exists but cannot be read.
        """
        events, problems = _scan(self.path)
        if problems:
            detail = "\n".join(f"  - {problem}" for problem in problems)
            raise LedgerCorruptionError(
                f"{self.path}: {len(problems)} integrity problem(s)\n{detail}\n"
                f"{_REPAIR_HINT}"
            )
        self._events = events

    def _append_event(self, event: dict[str, Any]) -> None:
        """Append one event line to the ledger, creating the file if needed.

        A durable append, not a rewrite: existing lines are never re-serialized,
        so a write cannot narrow the file to whatever the last load happened to
        parse.  A file left without a trailing newline gets one first, so a
        partial previous write cannot fuse two events into an unparseable line.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        needs_newline = False
        if self.path.exists() and self.path.stat().st_size > 0:
            with open(self.path, "rb") as f:
                f.seek(-1, os.SEEK_END)
                needs_newline = f.read(1) != b"\n"
        with open(self.path, "a", encoding="utf-8") as f:
            if needs_newline:
                f.write("\n")
            f.write(_canonical_json(event).decode("utf-8"))
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())

    def write_event(
        self,
        *,
        source: str,
        task: str,
        kind: str,
        ref: str | None = None,
        ref_kind: str | None = None,
        occurred_at: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Append one event to the ledger, or return the existing event if duplicate.

        Args:
            source: Caller identity (e.g. ``"sprint-add"``).  The reserved
                source ``"ingest-backfill"`` is rejected.
            task: Task id the event belongs to.
            kind: One of ``cut``, ``stage``, ``verdict``, ``land``.
            ref: Optional external reference (git sha, PR number, plan hash,
                evidence path).
            ref_kind: Required when ``ref`` is supplied; one of the allowed
                ref kinds.
            occurred_at: Required when ``ref`` is absent; caller-supplied
                timestamp in ISO-8601 format.
            payload: Optional structured payload (e.g. the R-8 closure digest).

        Returns:
            The persisted event dict.  If an event with the same id already
            exists, the existing dict is returned and no write occurs.

        Raises:
            ValueError: When ``source`` is reserved, ``kind`` is unknown,
                ``ref`` is present without ``ref_kind``, ``ref_kind`` is
                unknown, or ``ref`` is absent and ``occurred_at`` is missing.
            LedgerCorruptionError: When the ledger on disk fails verification.
                No event is appended to a store that cannot vouch for what it
                already holds.
        """
        if source == RESERVED_SOURCE:
            raise ValueError(f"reserved source rejected: {RESERVED_SOURCE}")
        if kind not in ALLOWED_KINDS:
            raise ValueError(f"unknown event kind: {kind!r}")
        if ref is not None and ref_kind is None:
            raise ValueError("ref_kind is required when ref is supplied")
        if ref_kind is not None and ref_kind not in ALLOWED_REF_KINDS:
            raise ValueError(f"unknown ref_kind: {ref_kind!r}")
        if not ref and not occurred_at:
            raise ValueError(
                "events without a ref require an explicit caller-supplied occurred_at"
            )

        ref_or_occurred = ref if ref is not None else occurred_at
        event_id = _event_id(source, task, kind, ref_or_occurred)

        with self._lock:
            self._load()
            if event_id in self._events:
                return self._events[event_id]

            created_at = datetime.now(timezone.utc).isoformat()
            event: dict[str, Any] = {
                "id": event_id,
                "schema_version": SCHEMA_VERSION,
                "source": source,
                "task": task,
                "kind": kind,
                "created_at": created_at,
            }
            if ref is not None:
                event["ref"] = ref
                event["ref_kind"] = ref_kind
            if occurred_at is not None:
                event["occurred_at"] = occurred_at
            if payload is not None:
                event["payload"] = payload

            self._append_event(event)
            self._events[event_id] = event
            return event

    def read_events(
        self,
        *,
        task: str | None = None,
        kind: str | None = None,
        source: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return all events, optionally filtered."""
        with self._lock:
            self._load()
            return [
                event
                for event in self._events.values()
                if (task is None or event.get("task") == task)
                and (kind is None or event.get("kind") == kind)
                and (source is None or event.get("source") == source)
            ]
