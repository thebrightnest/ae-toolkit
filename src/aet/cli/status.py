"""aet-work status — Show the current state of the work queue.

Reads the stored state and reports counts, next tasks, failed tasks, and
worktree health.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import typer

_SCRIPT_DIR = Path(__file__).resolve().parent
from aet.backends.factory import create_backend  # noqa: E402
from aet.plan_parser import parse_frontmatter  # noqa: E402
from aet.queue import (  # noqa: E402
    QueueIntegrityError,
    current_state,
    pending_blockers,
)


def _display_category(task: dict) -> str:
    """Return the canonical state for summary counting."""
    return current_state(task) or "unknown"


def _declared_size(task: dict) -> str:
    """Return the plan's declared S/M/L size, or '—' when unavailable."""
    spec = task.get("spec")
    if isinstance(spec, dict):
        data = spec.get("frontmatter", {})
    else:
        plan_file = task.get("plan_file")
        if not plan_file:
            return "—"
        try:
            data = parse_frontmatter(Path(plan_file))
        except OSError:
            return "—"
    size = data.get("size")
    return size if size in {"S", "M", "L"} else "—"


def _render_table(headers: list[str], rows: list[list[str]]) -> list[str]:
    """Render a markdown table with columns padded for terminal readability."""
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    def fmt(cells: list[str]) -> str:
        padded = (cell.ljust(width) for cell, width in zip(cells, widths))
        return "| " + " | ".join(padded) + " |"

    separator = "| " + " | ".join("-" * w for w in widths) + " |"
    return [fmt(headers), separator, *(fmt(row) for row in rows)]


def _is_process_alive(pid: int) -> bool:
    """Return True if ``pid`` is still running."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        pass
    return True


def _active_runs(runs_dir: Path) -> list[dict]:
    """List detached runs under ``runs_dir`` whose pid is still alive."""
    runs: list[dict] = []
    if not runs_dir.is_dir():
        return runs
    for entry in sorted(runs_dir.iterdir()):
        if not entry.is_dir():
            continue
        pid_file = entry / "pid"
        started_file = entry / "started"
        if not pid_file.is_file():
            continue
        try:
            pid = int(pid_file.read_text(encoding="utf-8").strip())
        except ValueError:
            continue
        if not _is_process_alive(pid):
            continue
        started = ""
        if started_file.is_file():
            started = started_file.read_text(encoding="utf-8").strip()
        runs.append({"id": entry.name, "pid": pid, "started": started})
    return runs


def _queue_updated_at(queue_file: str) -> str | None:
    """Return the wrapper's queue_updated_at for JSON-backed queues, else None."""
    try:
        with open(queue_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    if isinstance(data, dict):
        return data.get("queue_updated_at")
    return None


def _json_projection(queue: list[dict], queue_file: str, runs_dir: Path) -> dict:
    """Build the machine-readable status projection (minimal v1 schema)."""
    counts: dict[str, int] = {}
    for task in queue:
        category = _display_category(task)
        counts[category] = counts.get(category, 0) + 1
    return {
        "queue_updated_at": _queue_updated_at(queue_file),
        "active_runs": _active_runs(runs_dir),
        "summary": counts,
        "tasks": [
            {
                "id": task.get("id"),
                "state": current_state(task),
                "size": _declared_size(task),
                "stage": task.get("stage"),
                "blocked_by": task.get("blocked_by", []),
                "blocks": task.get("blocks", []),
                "pending_blockers": pending_blockers(task),
                "plan_file": task.get("plan_file"),
            }
            for task in queue
        ],
    }


def _run(
    queue_file: str,
    history_file: str,
    plans_dir: Path,
    json_output: bool,
) -> int:
    config_path = str(Path(queue_file).with_name("aet-config.json"))
    backend = create_backend(
        config_path=config_path, queue_file=queue_file, history_file=history_file
    )
    backend.fetch()
    try:
        data = backend.load()
        queue = data["queue"]
    except QueueIntegrityError as exc:
        print(
            f"⚠️  {exc}; read-only status continues with unverified data.",
            file=sys.stderr,
        )
        # Recover through the backend abstraction, not the JSON reader: the
        # git-refs backend keeps no aet-queue, so read_queue would
        # return an empty list and hide the very tasks status must surface.
        queue = backend.load(verify=False)["queue"]
    runs_dir = Path.cwd() / ".agents" / "runs"

    if json_output:
        print(json.dumps(_json_projection(queue, queue_file, runs_dir), indent=2))
        return 0

    counts = {
        "planned": 0,
        "ready": 0,
        "blocked": 0,
        "in_progress": 0,
        "awaiting_merge": 0,
        "failed": 0,
    }
    for task in queue:
        category = _display_category(task)
        if category in counts:
            counts[category] += 1

    non_zero = {state: count for state, count in counts.items() if count}
    if non_zero:
        print("\nQueue summary:")
        for state, count in non_zero.items():
            print(f"  {state}: {count}")
    else:
        print("\nQueue is empty.")

    active_runs = _active_runs(runs_dir)
    if active_runs:
        print("\nActive detached runs:")
        for run in active_runs:
            started = f" (started {run['started']})" if run["started"] else ""
            print(f"  - {run['id']} (PID {run['pid']}){started}")
    else:
        print("\nNo active detached runs.")

    terminal = {"merged", "abandoned"}
    active_ids = {t.get("id") for t in queue}
    rows = []
    for task in queue:
        if current_state(task) in terminal:
            continue
        deps = [
            "-".join(b.split("-")[:2])
            for b in task.get("blocked_by", [])
            if b in active_ids
        ]
        rows.append(
            [
                task.get("id", ""),
                current_state(task) or "unknown",
                _declared_size(task),
                ", ".join(deps) or "—",
            ]
        )
    if rows:
        print()
        for line in _render_table(["ID", "State", "Size", "Depends on"], rows):
            print(line)
    else:
        print("\nNo active tasks.")

    ready = [t for t in queue if current_state(t) == "ready"]
    if ready:
        print("\nNext ready tasks:")
        for task in ready[:3]:
            print(f"  - {task.get('id')} — {task.get('title')} → {task.get('plan_file')}")
    else:
        print("\nNo ready tasks.")

    failed = [t for t in queue if current_state(t) == "failed"]
    if failed:
        print("\nFailed tasks:")
        for task in failed:
            print(f"  - {task.get('id')} — {task.get('title')}")
    else:
        print("\nNo failed tasks.")

    stale_worktrees = []
    for task in queue:
        worktree = task.get("worktree")
        if worktree and not Path(worktree).is_dir():
            stale_worktrees.append((task.get("id"), worktree))
    if stale_worktrees:
        print("\nWorktree validation:")
        for task_id, worktree in stale_worktrees:
            print(
                f"  ⚠️ Stale worktree: {task_id} → {worktree} does not exist."
            )
    else:
        print("\nAll registered worktrees are present.")

    return 0


app = typer.Typer(invoke_without_command=True)


@app.callback()
def status(
    queue_file: str = typer.Option(
        ".agents/aet-queue",
        "--queue-file",
        help="Path to queue anchor",
    ),
    history_file: str = typer.Option(
        ".agents/work-history.jsonl",
        "--history-file",
        help="Path to work-history.jsonl",
    ),
    plans_dir: Path = typer.Option(
        Path("docs/plans"),
        "--plans-dir",
        help="Directory containing atomic plan markdown files",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Print a machine-readable JSON projection instead of the human report",
    ),
) -> None:
    """Show work queue status."""
    rc = _run(queue_file, history_file, plans_dir, json_output)
    raise typer.Exit(rc)


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    try:
        return app(argv, standalone_mode=False)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 0


if __name__ == "__main__":
    app()
