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
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from filelock import FileLock

ALLOWED_KINDS = frozenset({"cut", "stage", "verdict", "land"})
ALLOWED_REF_KINDS = frozenset({"git-sha", "pr", "plan-hash", "evidence-path"})
RESERVED_SOURCE = "ingest-backfill"
SCHEMA_VERSION = 1


def _canonical_json(value: Any) -> bytes:
    """Serialize ``value`` to stable UTF-8 JSON bytes for content addressing."""
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _event_id(source: str, task: str, kind: str, ref_or_occurred: str | None) -> str:
    """Return the deterministic sha256 id for an event tuple."""
    payload = f"{source}:{task}:{kind}:{ref_or_occurred or ''}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class Ledger:
    """Append-only, idempotent content-addressed event store."""

    def __init__(self, path: str | Path | None = None) -> None:
        """Initialize the ledger at ``path`` (default: ``.agents/ledger.jsonl``)."""
        self.path = Path(path) if path else Path(".agents/ledger.jsonl")
        self._lock = FileLock(str(self.path) + ".lock")
        self._events: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        """Read existing events and index them by id."""
        self._events = {}
        if not self.path.exists():
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    event_id = event.get("id")
                    if isinstance(event_id, str):
                        self._events[event_id] = event
        except OSError:
            return

    def _write_all(self, events: list[dict[str, Any]]) -> None:
        """Atomically rewrite the ledger file with the given events."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            dir=str(self.path.parent), prefix=".ledger-tmp-"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                for event in events:
                    f.write(_canonical_json(event).decode("utf-8"))
                    f.write("\n")
                    f.flush()
                    os.fsync(f.fileno())
            os.replace(tmp_path, self.path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except FileNotFoundError:
                pass
            raise

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

            events = list(self._events.values())
            events.append(event)
            self._write_all(events)
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
