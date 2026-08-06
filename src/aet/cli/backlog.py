"""aet-work backlog — Backlog curation commands.

``aet backlog add <plan>`` puts a plan on the GitHub board. It resolves the
plan by id, commits and pushes the plan's status, then calls the configured
projection to create or reconcile exactly one issue keyed by plan id.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import typer

_SCRIPT_DIR = Path(__file__).resolve().parent
from aet import plan_parser  # noqa: E402
from aet.backends.factory import resolve_config  # noqa: E402
from aet.projections.dispatcher import resolve_projections  # noqa: E402
from aet.queue import commit_and_push_status  # noqa: E402

# Plans accepted by the backlog entry point. Draft and approved plans both
# belong on the board; queued/in-progress plans are sprint members and are
# promoted through ``aet sprint add`` instead.
_BACKLOG_STATUSES = {"draft", "approved"}


def resolve_plan(target: str, plans_dir: Path) -> Path | None:
    """Resolve ``target`` to a plan file path.

    Wraps the shared resolver and converts its ``ValueError`` into ``None``,
    preserving ``aet backlog add``'s existing contract.
    """
    try:
        return Path(plan_parser.resolve_plan_arg(target, plans_dir=plans_dir))
    except ValueError:
        return None


def _fail(message: str) -> int:
    print(f"⛔ {message}", file=sys.stderr)
    return 1


def _task_from_plan(plan_file: Path) -> dict:
    """Build a minimal task record for projection from a plan file."""
    data = plan_parser.parse_frontmatter(plan_file)
    task_id = data.get("id", plan_file.stem)
    return {
        "id": task_id,
        "title": plan_parser.title_from_plan(plan_file),
        "status": data.get("status"),
        "plan_file": str(plan_file),
    }


def _add(args: argparse.Namespace) -> int:
    plans_dir = Path(args.plans_dir)
    plan_file = resolve_plan(args.target, plans_dir)
    if plan_file is None:
        return _fail(f"No plan found for '{args.target}' in {plans_dir}")

    data = plan_parser.parse_frontmatter(plan_file)
    status = data.get("status")
    if status not in _BACKLOG_STATUSES:
        return _fail(
            f"Refusing to add {plan_file.name}: plan status is "
            f"'{status or 'unknown'}'; only 'draft' or 'approved' plans may be "
            f"added to the backlog."
        )

    # Update the plan status. For plan paths under docs/plans/, the deferred
    # durability gate writes the file without committing at intake; terminal
    # closure still commits the final status.
    rc = commit_and_push_status(plan_file, status)
    if rc != 0:
        return _fail(
            f"Backlog add failed for {plan_file.name}: could not write "
            f"status update. Fix the git state and re-run `aet backlog add`."
        )

    # The projection is fail-open: a missing ``gh`` or network problem warns
    # but does not block the commit+push above (R-4).
    config = resolve_config(args.config)
    projections = resolve_projections(config)
    task = _task_from_plan(plan_file)
    projections.on_add(task, is_new=True)

    print(f"✓ Added {plan_file.name} to the backlog as aet:{status}.")
    return 0


app = typer.Typer()


@app.command("add")
def add(
    target: str = typer.Argument(..., help="Plan file path or task ID to add to the backlog"),
    plans_dir: str = typer.Option("docs/plans", "--plans-dir", help="Directory containing atomic plan markdown files"),
    config: str = typer.Option(".agents/aet-config.json", "--config", help="Path to AET backend configuration"),
) -> None:
    """Add a plan to the backlog."""
    args = argparse.Namespace(
        target=target,
        plans_dir=plans_dir,
        config=config,
    )
    rc = _add(args)
    raise typer.Exit(rc)


if __name__ == "__main__":
    app()
