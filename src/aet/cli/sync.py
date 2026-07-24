"""aet queue sync — Reconcile the existing work queue against docs/plans/*.md.

Loads the existing queue and settled history log, drops settled and non-sprint
entries, validates the frontmatter contract and atomicity, recomputes the
dependency DAG, reports drift, and updates wrapper metadata. Intake is curated:
sync **never adds new plans** (that is `aet sprint add`), and it does **not**
derive status or promote tasks.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import typer

_SCRIPT_DIR = Path(__file__).resolve().parent
from aet import plan_validate  # noqa: E402
from aet.backends.factory import create_backend  # noqa: E402
from aet.queue import QueueIntegrityError, build_blocks, lease_guard  # noqa: E402


def _sync(args: argparse.Namespace) -> int:
    queue_file = args.queue_file
    history_file = args.history_file
    plans_dir = Path(args.plans_dir)

    backend = create_backend(
        config_path=args.config,
        queue_file=queue_file,
        history_file=history_file,
    )

    # Ensure the append-only history log exists so commands recreate missing
    # files on demand without waiting for a terminal record to be appended.
    os.makedirs(os.path.dirname(history_file) or ".", exist_ok=True)
    if not os.path.exists(history_file):
        open(history_file, "a", encoding="utf-8").close()

    try:
        data = backend.load()
    except QueueIntegrityError as exc:
        # Mutating command: fail closed with a one-line refusal, not a
        # traceback. The error message names the recovery path (ADR-024).
        print(f"⛔ {exc}", file=sys.stderr)
        return 1
    queue = data["queue"]

    plan_files = sorted(plans_dir.glob("*.md"))
    plan_file_set = {str(pf) for pf in plan_files}

    # Curated intake: only plans already in the queue are reconciled. New plans
    # must be explicitly added via ``aet-work add``; sync never auto-adds them.
    final_queue: list[dict] = []
    preserved = 0
    skipped_settled = 0
    skipped_non_sprint = 0
    for task in queue:
        pf = task.get("plan_file")
        # Settled-ness is derived from committed plan data (status frontmatter),
        # not from the local gitignored history log. A missing plan file cannot
        # be classified as settled; it is reported as drift below.
        pf_path = Path(pf) if pf else None
        if pf_path and pf_path.is_file():
            if plan_validate.is_settled_plan(pf_path):
                skipped_settled += 1
                continue
            if not plan_validate.is_sprint_member(pf_path):
                skipped_non_sprint += 1
                continue
        final_queue.append(task)
        if pf:
            preserved += 1

    build_blocks(final_queue)

    # Validate existing queue entries before any reconciliation or save.
    plan_files_to_validate = []
    for task in final_queue:
        pf = task.get("plan_file")
        if pf:
            plan_path = Path(pf)
            if plan_path.is_file():
                plan_files_to_validate.append(plan_path)

    repo_root = Path(
        subprocess.run(
            ["git", "-C", str(plans_dir), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
        ).stdout.strip()
        or str(plans_dir.parent.parent)
    )
    findings = plan_validate.validate(plan_files_to_validate, repo_root=repo_root)
    plan_texts = {
        pf: pf.read_text(errors="ignore") for pf in plan_files_to_validate
    }
    findings = plan_validate.apply_acks(findings, plan_texts)
    unacked = [f for f in findings if not f.acked]
    if unacked:
        for finding in unacked:
            print(
                f"❌ {finding.plan.name}: {finding.check_id}: {finding.message}",
                file=sys.stderr,
            )
        return 1

    # Report plan drift without mutating stored state.
    drifted = 0
    for task in final_queue:
        pf = task.get("plan_file")
        if pf and pf not in plan_file_set:
            drifted += 1
            print(f"⚠️ Drift: {task.get('id')} -> {pf}")

    for task in final_queue:
        backend.sync_task(task, is_new=False)

    if not lease_guard(queue_file, force=args.force):
        backend.close()
        return 1

    backend.save(final_queue, wrapper={"queue_updated_at": datetime.now().isoformat()})

    print(
        f"\n✅ Sync complete: 0 new tasks added, {preserved} existing tasks preserved, "
        f"{skipped_settled} skipped (already settled), {skipped_non_sprint} skipped (not in sprint), "
        f"{drifted} drifted tasks reported."
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
        "docs/plans", "--plans-dir", help="Directory containing atomic plan markdown files"
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
    """Reconcile queued tasks against docs/plans/*.md (never adds new plans)."""
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
