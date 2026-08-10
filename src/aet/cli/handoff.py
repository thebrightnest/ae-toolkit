"""aet handoff — run-scoped handoff note commands.

``handoff append`` writes a structured entry to the current run's handoff
note.  ``handoff show`` renders the note as the prompt block the orchestrator
injects into later stage sessions.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

import typer

from aet import handoff

app = typer.Typer()


def _resolve_run_id(run_id: Optional[str]) -> Optional[str]:
    """Return the explicit run id or fall back to ``AET_RUN_ID``."""
    if run_id:
        return run_id
    return os.environ.get("AET_RUN_ID")


def _require_run_id(run_id: Optional[str]) -> str:
    """Resolve a run id, printing a named error and exiting 1 if absent."""
    resolved = _resolve_run_id(run_id)
    if resolved:
        return resolved
    print("error: missing run id: pass --run-id or set AET_RUN_ID", file=sys.stderr)
    raise typer.Exit(1)


def _resolve_repo_root(repo_root: Optional[str]) -> Path:
    """Return the repository root, defaulting to the current directory."""
    return Path(repo_root).resolve() if repo_root else Path.cwd()


@app.command("append")
def append(
    stage: str = typer.Option(
        ...,
        "--stage",
        help="Stage name recording this entry.",
    ),
    decision: list[str] = typer.Option(
        [],
        "--decision",
        help="Repeatable decision taken in this stage.",
    ),
    pre_existing_failure: list[str] = typer.Option(
        [],
        "--pre-existing-failure",
        help="Repeatable pre-existing failure encountered in this stage.",
    ),
    validation_command: list[str] = typer.Option(
        [],
        "--validation-command",
        help="Repeatable validation command run in this stage.",
    ),
    evidence_path: Optional[str] = typer.Option(
        None,
        "--evidence-path",
        help="Path to the verdict evidence produced by this stage.",
    ),
    run_id: Optional[str] = typer.Option(
        None,
        "--run-id",
        help="Run id (default: $AET_RUN_ID).",
    ),
    repo_root: Optional[str] = typer.Option(
        None,
        "--repo-root",
        help="Repository root (default: current directory).",
    ),
) -> None:
    """Append one entry to the run's handoff note."""
    resolved_run_id = _require_run_id(run_id)
    resolved_repo_root = _resolve_repo_root(repo_root)

    try:
        handoff.append_entry(
            resolved_repo_root,
            resolved_run_id,
            stage=stage,
            decisions=decision or None,
            pre_existing_failures=pre_existing_failure or None,
            validation_commands=validation_command or None,
            evidence_path=evidence_path,
        )
    except handoff.EmptyEntryError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise typer.Exit(1) from exc


@app.command("show")
def show(
    run_id: Optional[str] = typer.Option(
        None,
        "--run-id",
        help="Run id (default: $AET_RUN_ID).",
    ),
    repo_root: Optional[str] = typer.Option(
        None,
        "--repo-root",
        help="Repository root (default: current directory).",
    ),
) -> None:
    """Render the run's handoff note as a prompt block."""
    resolved_run_id = _require_run_id(run_id)
    resolved_repo_root = _resolve_repo_root(repo_root)

    note = handoff.read_note(resolved_repo_root, resolved_run_id)
    if note is None:
        print(
            "Run handoff note (written by earlier stages of this same run — "
            "trust what it records and do NOT re-investigate it):\n"
            "(no handoff note found for this run)",
        )
        return
    print(handoff.render_prompt_block(note))
