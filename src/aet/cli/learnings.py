"""``aet learnings`` — append-only writer for ``.agents/learnings.jsonl``."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import typer
from filelock import FileLock

app = typer.Typer(help="Append-only learning journal commands.")

DEFAULT_LEARNINGS_FILE = ".agents/learnings.jsonl"


def _now_utc() -> str:
    """Return an ISO-8601 UTC timestamp string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _validate_nonempty(value: str) -> str:
    """Reject values that are empty or whitespace-only after stripping."""
    if not value.strip():
        typer.echo("error: --problem/--layer/--fix/--prevents must be non-empty", err=True)
        raise typer.Exit(1)
    return value


def _exit_recurrence() -> None:
    """Print recurrence error and exit non-zero."""
    typer.echo("error: --recurrence must be a positive integer", err=True)
    raise typer.Exit(1)


@app.command("append")
def append_learning(
    problem: str = typer.Option(
        ...,
        "--problem",
        help="What went wrong or what was misunderstood.",
        callback=_validate_nonempty,
    ),
    layer: str = typer.Option(
        ...,
        "--layer",
        help="The layer (file, command, skill, etc.) where the issue lives.",
        callback=_validate_nonempty,
    ),
    fix: str = typer.Option(
        ...,
        "--fix",
        help="The concrete change that prevents recurrence.",
        callback=_validate_nonempty,
    ),
    prevents: str = typer.Option(
        ...,
        "--prevents",
        help="The failure this learning prevents.",
        callback=_validate_nonempty,
    ),
    trigger: list[str] = typer.Option(
        [],
        "--trigger",
        help="Keyword trigger(s) for retrieval (repeatable).",
    ),
    recurrence: Optional[int] = typer.Option(
        None,
        "--recurrence",
        help="How many times this issue has recurred (positive integer).",
        callback=lambda v: v if v is None or v >= 1 else (_exit_recurrence() or v),
    ),
    file: Path = typer.Option(
        Path(DEFAULT_LEARNINGS_FILE),
        "--file",
        help="Path to the learnings JSONL file.",
    ),
) -> None:
    """Append one canonical learning entry to ``.agents/learnings.jsonl``."""
    entry: dict[str, object] = {
        "timestamp": _now_utc(),
        "problem": problem,
        "layer": layer,
        "fix": fix,
        "prevents": prevents,
    }
    if trigger:
        entry["trigger"] = trigger
    if recurrence is not None:
        entry["recurrence"] = recurrence

    lock_path = str(file.resolve()) + ".lock"
    with FileLock(lock_path):
        file.parent.mkdir(parents=True, exist_ok=True)
        with open(file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    typer.echo("Learning appended.")
