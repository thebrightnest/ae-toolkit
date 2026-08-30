"""aet-work backlog — Backlog curation commands.

``aet backlog add <plan>`` puts a plan on the GitHub board. It resolves the
plan by id and calls the configured projection to create or reconcile exactly
one issue keyed by plan id. The plan file is not mutated.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import typer

_SCRIPT_DIR = Path(__file__).resolve().parent
from aet import admission, plan_parser  # noqa: E402
from aet.backends.factory import create_backend, resolve_config  # noqa: E402
from aet.projections.dispatcher import resolve_projections  # noqa: E402
from aet.queue import QueueIntegrityError  # noqa: E402


def resolve_plan(target: str, plans_dir: Path) -> Path | None:
    """Resolve ``target`` to a plan file path.

    Wraps the shared resolver and converts its ``ValueError`` into ``None``,
    preserving ``aet backlog add``'s existing contract.
    """
    return admission.resolve_plan(target, plans_dir)


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
        "state": "backlog",
        "plan_file": str(plan_file),
    }


def _add(args: argparse.Namespace) -> int:
    plans_dir = Path(args.plans_dir)
    plan_file = resolve_plan(args.target, plans_dir)
    if plan_file is None:
        return _fail(f"No plan found for '{args.target}' in {plans_dir}")

    backend = create_backend(
        config_path=args.config,
        queue_file=args.queue_file,
        history_file=args.history_file,
    )
    try:
        data = backend.load()
    except QueueIntegrityError as exc:
        print(f"⛔ {exc}", file=sys.stderr)
        backend.close()
        return 1
    queue = data["queue"]
    history = data["history"]

    plan_str = str(plan_file)
    existing = next(
        (
            t
            for t in queue
            if t.get("plan_file") == plan_str or t.get("id") == plan_file.stem
        ),
        None,
    )
    if existing is not None:
        backend.close()
        return _fail(
            f"Refusing to add {plan_file.name}: already a sprint member "
            f"({existing.get('state', 'planned')})."
        )

    settled_ids = {t.get("id") for t in history if t.get("id")}
    if plan_file.stem in settled_ids:
        backend.close()
        return _fail(
            f"Refusing to add {plan_file.name}: task is already settled in history."
        )

    # The projection is fail-open: a missing ``gh`` or network problem warns
    # but does not block the local record (R-4). In shadow posture projections
    # are suppressed entirely.
    config = resolve_config(args.config)
    projections = resolve_projections(config, posture=backend.posture)
    task = _task_from_plan(plan_file)
    projections.on_add(task, is_new=True)
    backend.close()

    print(f"✓ Added {plan_file.name} to the backlog as aet:backlog.")
    return 0


app = typer.Typer()


@app.command("add")
def add(
    target: str = typer.Argument(..., help="Plan file path or task ID to add to the backlog"),
    plans_dir: str = typer.Option("docs/plans", "--plans-dir", help="Directory containing atomic plan markdown files"),
    config: str = typer.Option(".agents/aet-config.json", "--config", help="Path to AET backend configuration"),
    queue_file: str = typer.Option(
        ".agents/aet-queue", "--queue-file", help="Path to queue anchor"
    ),
    history_file: str = typer.Option(
        ".agents/work-history.jsonl", "--history-file", help="Path to work-history.jsonl"
    ),
) -> None:
    """Add a plan to the backlog."""
    args = argparse.Namespace(
        target=target,
        plans_dir=plans_dir,
        config=config,
        queue_file=queue_file,
        history_file=history_file,
    )
    rc = _add(args)
    raise typer.Exit(rc)


if __name__ == "__main__":
    app()
