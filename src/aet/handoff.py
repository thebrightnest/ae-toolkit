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

SCHEMA_VERSION = 2
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
    if data.get("schema_version") not in (1, 2):
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
    task_id: str | None = None,
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
        "task_id": task_id,
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
        else:
            note["schema_version"] = SCHEMA_VERSION
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


def _entry_key(entry: dict[str, Any]) -> tuple[Any, ...]:
    """Derive a hashable comparison key from all fields except ``recorded_at``."""
    items: list[tuple[str, Any]] = []
    for k in sorted(entry.keys()):
        if k == "recorded_at":
            continue
        v = entry[k]
        if isinstance(v, list):
            items.append((k, tuple(v)))
        elif isinstance(v, dict):
            items.append((k, tuple(sorted(v.items()))))
        else:
            items.append((k, v))
    return tuple(items)


def _matches_task(entry: dict[str, Any], task_id: str | None) -> bool:
    """Return whether ``entry`` belongs to ``task_id`` or is run-level."""
    if task_id is None:
        return True
    entry_task = entry.get("task_id")
    return not entry_task or entry_task == task_id


def _render_entry_block(entry: dict[str, Any], count: int) -> str:
    """Render a single collapsed entry block with optional repeat count."""
    stage = entry.get("stage", "unknown")
    header = (
        f"[stage: {stage}] (repeated {count} times)"
        if count > 1
        else f"[stage: {stage}]"
    )
    lines = [
        header,
        _format_field("decisions", entry.get("decisions") or []),
        _format_field(
            "pre-existing failures",
            entry.get("pre_existing_failures") or [],
        ),
        _format_field(
            "validation commands",
            entry.get("validation_commands") or [],
        ),
        _format_optional("evidence path", entry.get("evidence_path")),
    ]
    return "\n".join(lines)


def render_prompt_block(
    note: dict[str, Any], task_id: str | None = None
) -> str:
    """Render the handoff note as a prompt injection block.

    Renders entries for ``task_id`` and entries with no ``task_id``.
    Identical entries (all fields except ``recorded_at``) are collapsed into
    one with ``(repeated N times)``.  The block is built from the newest entry
    backwards and stops before ``PROMPT_BLOCK_CAP`` characters, ensuring the
    newest entry always renders.
    """
    preamble = (
        "Run handoff note (written by earlier stages of this same run — trust "
        "what it records and do NOT re-investigate it):"
    )

    raw_entries = note.get("entries") or []
    filtered = [e for e in raw_entries if _matches_task(e, task_id)]
    if not filtered:
        return preamble

    collapsed: list[tuple[dict[str, Any], int]] = []
    for e in filtered:
        if collapsed and _entry_key(collapsed[-1][0]) == _entry_key(e):
            collapsed[-1] = (collapsed[-1][0], collapsed[-1][1] + 1)
        else:
            collapsed.append((e, 1))

    blocks = [_render_entry_block(entry, count) for entry, count in collapsed]

    selected: list[str] = []
    for b in reversed(blocks):
        if not selected:
            selected.append(b)
        else:
            candidate_blocks = [b] + list(reversed(selected))
            candidate_text = preamble + "\n" + "\n".join(candidate_blocks)
            if len(candidate_text) > PROMPT_BLOCK_CAP:
                break
            selected.append(b)

    final_blocks = list(reversed(selected))
    rendered = preamble + "\n" + "\n".join(final_blocks)

    if len(rendered) > PROMPT_BLOCK_CAP:
        truncated = rendered[:PROMPT_BLOCK_CAP]
        marker = "\n[handoff note truncated]"
        if len(truncated) + len(marker) > PROMPT_BLOCK_CAP:
            truncated = truncated[: PROMPT_BLOCK_CAP - len(marker)]
        rendered = truncated + marker

    return rendered
