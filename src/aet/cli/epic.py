"""aet epic — Epic inspection commands.

``aet epic list`` lists the integration branches that queued tasks resolve to.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import typer

from aet import plan_parser
from aet.backends.factory import create_backend, resolve_config, resolve_integration_mode
from aet.branch_ref import _task_prd_path, resolve_integration_branch_for_task
from aet.project_id import resolve_repo_root

app = typer.Typer(help="Epic inspection.")


def _pr_title(prd_path: Path | None) -> str | None:
    """Return the ``pr_title`` a PRD declares, or None."""
    if prd_path is None or not prd_path.is_file():
        return None
    title = plan_parser.parse_frontmatter(prd_path).get("pr_title")
    return str(title) if title else None


@app.command("list")
def list_epics(
    config: str = typer.Option(
        ".agents/aet-config.json", "--config", help="Path to AET configuration file."
    ),
    queue_file: str = typer.Option(
        ".agents/aet-queue", "--queue-file", help="Path to queue anchor."
    ),
    history_file: str = typer.Option(
        ".agents/work-history.jsonl", "--history-file", help="Path to work history."
    ),
) -> None:
    """List the integration branches that queued tasks resolve to."""
    repo_root = resolve_repo_root()
    queue_path = str(repo_root / queue_file) if not Path(queue_file).is_absolute() else queue_file
    history_path = str(repo_root / history_file) if not Path(history_file).is_absolute() else history_file
    config_full = str(repo_root / config) if not Path(config).is_absolute() else config

    rows = epic_rows(repo_root, config_full, queue_path, history_path)
    if not rows:
        typer.echo("No queued tasks.")
        return

    typer.echo("Epic branches:")
    for row in rows:
        counts = " ".join(f"{state}={n}" for state, n in sorted(row["states"].items()))
        title = f"  pr_title: {row['pr_title']}" if row["pr_title"] else ""
        typer.echo(f"  {row['branch']} ({row['provenance']})  {counts}{title}")


def epic_rows(
    repo_root: Path, config_path: str, queue_path: str, history_path: str
) -> list[dict]:
    """Group queued tasks by the integration branch they resolve to.

    Returns one dict per branch with ``branch``, ``provenance``, ``states``
    (a state-to-count mapping) and ``pr_title``, sorted by branch.
    """
    backend = create_backend(
        config_path=config_path,
        queue_file=queue_path,
        history_file=history_path,
    )
    try:
        queue = backend.load()["queue"]
    finally:
        backend.close()

    cfg = resolve_config(config_path, repo_root=repo_root)
    mode = resolve_integration_mode(config_path, repo_root=repo_root)
    rows: dict[str, dict] = {}
    for task in queue:
        ref = resolve_integration_branch_for_task(repo_root, cfg, task, mode)
        row = rows.setdefault(
            ref.ref,
            {"branch": ref.ref, "provenance": ref.provenance, "states": Counter(), "pr_title": None},
        )
        row["states"][task.get("state", "unknown")] += 1
        if row["pr_title"] is None:
            row["pr_title"] = _pr_title(_task_prd_path(task, repo_root))
    return [rows[branch] for branch in sorted(rows)]
