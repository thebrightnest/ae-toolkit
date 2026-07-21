"""aet-work report — Print an execution telemetry summary.

Scans the telemetry archive for the current project (or a given project/run)
and prints a text summary: runs, success/failure counts, wall-clock time,
and average isolation level. With ``--prune DAYS``, lists (or with ``--force``,
deletes) telemetry run dirs older than DAYS, never touching the run that
holds the work-queue lease or ``AET_RUN_ID``.
"""

from __future__ import annotations

import os
from pathlib import Path

import typer

_SCRIPT_DIR = Path(__file__).resolve().parent
from aet import telemetry  # noqa: E402


def _leased_run_id() -> str | None:
    """Return the run_id holding the cwd's work-queue lease, if any."""
    queue_file = Path(".agents/work-queue.json")
    if not queue_file.is_file():
        return None
    from aet import queue as queue_lib  # noqa: PLC0415

    lease = queue_lib.read_lease(str(queue_file))
    if isinstance(lease, dict):
        run_id = lease.get("run_id")
        return run_id if isinstance(run_id, str) else None
    return None


def _protected_run_ids() -> frozenset:
    """Assemble the never-prune set: lease holder plus ``AET_RUN_ID``."""
    protected = set()
    leased = _leased_run_id()
    if leased:
        protected.add(leased)
    env_run = os.environ.get("AET_RUN_ID")
    if env_run:
        protected.add(env_run)
    return frozenset(protected)


def _format_prune_report(result: dict, force: bool) -> str:
    lines = []
    if not force:
        lines.append("DRY RUN — no files deleted (rerun with --force to delete)")
    lines.append(f"Prune candidates: {len(result['candidates'])}")
    lines.extend(f"  {path}" for path in result["candidates"])
    if result["kept_protected"]:
        lines.append(f"Kept (protected): {len(result['kept_protected'])}")
        lines.extend(f"  {path}" for path in result["kept_protected"])
    lines.append(f"Deleted: {len(result['deleted'])}")
    lines.extend(f"  {path}" for path in result["deleted"])
    lines.append(f"Bytes reclaimed: {result['bytes_reclaimed']}")
    return "\n".join(lines) + "\n"


def _run(
    project: str | None,
    run_dir: str | None,
    task_log: str | None,
    since: str | None,
    prune: int | None,
    force: bool,
) -> int:
    if prune is not None:
        root = telemetry.archive_dir() / project if project else None
        result = telemetry.prune_archive(
            prune,
            root=root,
            force=force,
            protected_run_ids=_protected_run_ids(),
        )
        print(_format_prune_report(result, force), end="")
        return 0

    target = task_log or run_dir or project
    print(telemetry.report(target=target, since=since), end="")
    return 0


app = typer.Typer(invoke_without_command=True)


@app.callback()
def report(
    project: str | None = typer.Option(
        None,
        "--project",
        help="Project slug (defaults to the current repository)",
    ),
    run_dir: str | None = typer.Option(
        None,
        "--run-dir",
        help="Path to a specific run directory in the archive",
    ),
    task_log: str | None = typer.Option(
        None,
        "--task-log",
        help="Path to a single task JSONL file",
    ),
    since: str | None = typer.Option(
        None,
        "--since",
        help="Only include records at or after this ISO-8601 timestamp",
    ),
    prune: int | None = typer.Option(
        None,
        "--prune",
        help="Prune telemetry runs older than DAYS (dry run unless --force)",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Actually delete prune candidates (default is a dry run)",
    ),
) -> None:
    """Print execution telemetry summary."""
    rc = _run(project, run_dir, task_log, since, prune, force)
    raise typer.Exit(rc)


def main(argv: list[str] | None = None) -> int:
    try:
        return app(argv or [], standalone_mode=False)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 0


if __name__ == "__main__":
    app()
