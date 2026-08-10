"""Run-scoped handoff note — working memory shared across stage sessions.

A handoff note is a per-run JSON artifact that lives alongside other run
metadata under ``.agents/runs/<run-id>/handoff.json``.  Earlier stages append
entries; later stages consume the rendered prompt block without
re-deriving context.  The note is explicitly run-scoped working memory, not a
provenance fact, so it does **not** emit ledger events.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from filelock import FileLock

SCHEMA_VERSION = 1
PROMPT_BLOCK_CAP = 4000


class HandoffError(Exception):
    """Base exception for handoff operations that the CLI surfaces as errors."""


class MissingRunIdError(HandoffError):
    """No ``--run-id`` was supplied and ``AET_RUN_ID`` is unset."""


class EmptyEntryError(HandoffError):
    """The append request omitted all four optional entry fields."""


def _utc_now() -> str:
    """Return an ISO-8601 UTC timestamp string."""
    return datetime.now(timezone.utc).isoformat()


def handoff_path(repo_root: str | Path, run_id: str) -> Path:
    """Return the canonical handoff note path for ``run_id``."""
    return Path(repo_root) / ".agents" / "runs" / run_id / "handoff.json"


def _lock_path(path: Path) -> str:
    """Return the filelock path for a handoff note."""
    return str(path) + ".lock"


def _default_repo_root() -> Path:
    """Return the current working directory as the repository root."""
    return Path.cwd()


def _atomic_write(path: Path, data: dict[str, Any]) -> None:
    """Serialize ``data`` to JSON and atomically replace ``path``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        dir=str(path.parent), prefix=".handoff-tmp-"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except FileNotFoundError:
            pass
        raise


def read_note(repo_root: str | Path, run_id: str) -> dict[str, Any] | None:
    """Return the parsed handoff note, or ``None`` if absent or unreadable.

    Never raises: callers use this best-effort read to decide whether to
    inject a handoff block into a prompt.
    """
    path = handoff_path(repo_root, run_id)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None

    if not isinstance(data, dict):
        return None
    if data.get("schema_version") != SCHEMA_VERSION:
        return None
    if data.get("run_id") != run_id:
        return None
    entries = data.get("entries")
    if not isinstance(entries, list) or not entries:
        return None
    return data


def append_entry(
    repo_root: str | Path,
    run_id: str,
    *,
    stage: str,
    decisions: list[str] | None = None,
    pre_existing_failures: list[str] | None = None,
    validation_commands: list[str] | None = None,
    evidence_path: str | None = None,
    recorded_at: str | None = None,
) -> dict[str, Any]:
    """Append one entry to the run's handoff note, creating it if needed.

    The file is written under a ``filelock`` lock so concurrent stage sessions
    in the same run do not corrupt the note.  The ``recorded_at`` timestamp is
    minted from wall-clock UTC unless the caller supplies one.

    Raises:
        EmptyEntryError: if all four optional entry fields are empty.
    """
    if not any(
        [
            decisions,
            pre_existing_failures,
            validation_commands,
            evidence_path,
        ]
    ):
        raise EmptyEntryError(
            "at least one of --decision, --pre-existing-failure, "
            "--validation-command, or --evidence-path is required"
        )

    path = handoff_path(repo_root, run_id)
    lock = FileLock(_lock_path(path))

    entry: dict[str, Any] = {
        "stage": stage,
        "decisions": list(decisions or []),
        "pre_existing_failures": list(pre_existing_failures or []),
        "validation_commands": list(validation_commands or []),
        "evidence_path": evidence_path,
        "recorded_at": recorded_at or _utc_now(),
    }

    with lock:
        note = read_note(repo_root, run_id)
        if note is None:
            note = {
                "schema_version": SCHEMA_VERSION,
                "run_id": run_id,
                "entries": [],
            }
        note["entries"].append(entry)
        _atomic_write(path, note)

    return note


def _format_field(label: str, values: list[str]) -> str:
    """Render one labeled field, joining list values with ``, ``."""
    if not values:
        return f"{label}: (none)"
    return f"{label}: {', '.join(values)}"


def _format_optional(label: str, value: str | None) -> str:
    """Render one optional labeled field."""
    if value:
        return f"{label}: {value}"
    return f"{label}: (none)"


def render_prompt_block(note: dict[str, Any]) -> str:
    """Render the handoff note as a prompt injection block.

    The block is capped at ``PROMPT_BLOCK_CAP`` characters; if truncation is
    required, an explicit marker is appended.
    """
    lines = [
        "Run handoff note (written by earlier stages of this same run — trust "
        "what it records and do NOT re-investigate it):",
    ]
    for entry in note.get("entries", []):
        stage = entry.get("stage", "unknown")
        lines.append(f"[stage: {stage}]")
        lines.append(
            _format_field(
                "decisions", entry.get("decisions") or []
            )
        )
        lines.append(
            _format_field(
                "pre-existing failures",
                entry.get("pre_existing_failures") or [],
            )
        )
        lines.append(
            _format_field(
                "validation commands",
                entry.get("validation_commands") or [],
            )
        )
        lines.append(
            _format_optional(
                "evidence path", entry.get("evidence_path")
            )
        )

    rendered = "\n".join(lines)
    if len(rendered) > PROMPT_BLOCK_CAP:
        truncated = rendered[:PROMPT_BLOCK_CAP]
        marker = "\n[handoff note truncated]"
        # Ensure room for marker; cap is larger than marker length.
        if len(truncated) + len(marker) > PROMPT_BLOCK_CAP:
            truncated = truncated[: PROMPT_BLOCK_CAP - len(marker)]
        rendered = truncated + marker
    return rendered
