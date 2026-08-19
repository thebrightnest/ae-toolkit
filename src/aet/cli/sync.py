"""aet queue sync — Reconcile the existing work queue.

Loads the existing queue, drops terminal records (the board is open work),
recomputes the dependency DAG, and persists the result. Intake is curated:
sync **never adds new plans** (that is `aet sprint add`) and it does **not**
scan the plans directory or derive status from it.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime

import typer

from aet.backends.factory import create_backend  # noqa: E402
from aet.queue import QueueIntegrityError, build_blocks, current_state, lease_guard  # noqa: E402


def _sync(args: argparse.Namespace) -> int:
    queue_file = args.queue_file
    backend = create_backend(
        config_path=args.config,
        queue_file=queue_file,
        history_file=args.history_file,
    )
    backend.fetch()

    try:
        data = backend.load()
    except QueueIntegrityError as exc:
        # Mutating command: fail closed with a one-line refusal, not a
        # traceback. The error message names the recovery path (ADR-024).
        print(f"⛔ {exc}", file=sys.stderr)
        return 1
    queue = data["queue"]

    # The board is the set of open work. Anything already terminal does not
    # belong in the live queue.
    final_queue: list[dict] = []
    skipped_terminal = 0
    for task in queue:
        if current_state(task) in {"merged", "abandoned"}:
            skipped_terminal += 1
            continue
        final_queue.append(task)

    build_blocks(final_queue)

    for task in final_queue:
        backend.sync_task(task, is_new=False)

    if not lease_guard(queue_file, force=args.force):
        backend.close()
        return 1

    backend.save(final_queue, wrapper={"queue_updated_at": datetime.now().isoformat()})

    print(
        f"\n✅ Sync complete: 0 new tasks added, {len(final_queue)} existing tasks preserved, "
        f"{skipped_terminal} skipped (already settled)."
    )
    backend.close()
    return 0


app = typer.Typer()


@app.command("sync")
def sync(
    queue_file: str = typer.Option(
        ".agents/work-queue.json", "--queue-file", help="Path to work-queue.json"
    ),
    history_file: str = typer.Option(
        ".agents/work-history.jsonl", "--history-file", help="Path to work-history.jsonl"
    ),
    plans_dir: str = typer.Option(
        "docs/plans", "--plans-dir", help="Deprecated and ignored: sync no longer scans the plans directory."
    ),
    config: str = typer.Option(
        ".agents/aet-config.json", "--config", help="Path to AET backend configuration"
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Override a live run lease and mutate the queue anyway (with a warning).",
    ),
) -> None:
    """Reconcile the existing work queue (never scans docs/plans)."""
    args = argparse.Namespace(
        queue_file=queue_file,
        history_file=history_file,
        plans_dir=plans_dir,
        config=config,
        force=force,
    )
    rc = _sync(args)
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
