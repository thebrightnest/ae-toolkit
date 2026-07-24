"""aet-work sprint — Sprint membership commands.

``aet sprint add <plan>`` promotes an approved plan into the runnable sprint:
it sets the plan frontmatter to ``status: queued``, commits and pushes that
change, adds the task to the ephemeral work queue, and mirrors the ready/blocked
state to any configured projection (e.g. GitHub Issues labels).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import typer

_SCRIPT_DIR = Path(__file__).resolve().parent
from aet import plan_validate  # noqa: E402
from aet.backends.factory import create_backend, resolve_config  # noqa: E402
from aet.plan_parser import new_task_from_plan, stage_from_plan  # noqa: E402
from aet.projections.dispatcher import resolve_projections  # noqa: E402
from aet.queue import (  # noqa: E402
    QueueIntegrityError,
    build_blocks,
    commit_and_push_status,
    lease_guard,
)


def resolve_plan(target: str, plans_dir: Path) -> Path | None:
    """Resolve ``target`` to a plan file path.

    If ``target`` is an existing path, use it directly. Otherwise treat it as
    a task ID and look for ``<target>.md`` in ``plans_dir``.
    """
    as_path = Path(target)
    if as_path.is_file():
        return as_path

    candidate = plans_dir / f"{target}.md"
    if candidate.is_file():
        return candidate

    return None


def plan_is_untracked(plan_file: Path) -> bool:
    """True when ``plan_file`` is inside a git work tree but not tracked.

    Returns False when the file is tracked *or* when it is not inside any git
    repository — outside version control there is no durability to enforce.
    aet-work builds task worktrees from ``origin/main``; a queued plan that git
    cannot retrieve there yields an empty worktree, so intake refuses an
    untracked plan early instead of failing deep in a run.
    """
    resolved = plan_file.resolve()
    parent = str(resolved.parent)
    inside = subprocess.run(
        ["git", "-C", parent, "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        text=True,
    )
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        return False
    tracked = subprocess.run(
        ["git", "-C", parent, "ls-files", "--error-unmatch", resolved.name],
        capture_output=True,
        text=True,
    )
    return tracked.returncode != 0


def _fail(message: str) -> int:
    print(f"⛔ {message}", file=sys.stderr)
    return 1


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
    projections = resolve_projections(resolve_config(args.config))

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
        (t for t in queue if t.get("plan_file") == plan_str or t.get("id") == plan_file.stem),
        None,
    )
    if existing is not None:
        print(f"✓ {plan_file.name} is already in the queue ({existing.get('state', 'planned')}).")
        backend.close()
        return 0

    settled_ids = {t.get("id") for t in history if t.get("id")}
    if plan_file.stem in settled_ids:
        backend.close()
        return _fail(
            f"Refusing to promote {plan_file.name}: task is already settled in history."
        )

    stage = stage_from_plan(plan_file)
    if stage != "plan-approved":
        backend.close()
        return _fail(
            f"Refusing to promote {plan_file.name}: plan stage is '{stage or 'unknown'}'; "
            f"only 'plan-approved' plans may enter the sprint."
        )

    if not args.allow_untracked and plan_is_untracked(plan_file):
        backend.close()
        return _fail(
            f"Refusing to promote {plan_file.name}: the plan file is not tracked "
            f"in git. Commit it first so aet-work can retrieve it from "
            f"origin/main (it builds task worktrees there); pass "
            f"--allow-untracked to queue a throwaway spike anyway."
        )

    # Validate the target plan in the context of every plan in plans_dir so
    # blocker references resolve, but only report findings for the target plan.
    all_plan_files = sorted(plans_dir.glob("*.md"))
    if plan_file not in all_plan_files:
        all_plan_files.append(plan_file)
    # Settled history ids are valid blocker references even when the plan file
    # is gone, so include them in the structural cross-reference set.
    settled_ids = set()
    if Path(args.history_file).exists():
        for line in Path(args.history_file).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("id"):
                settled_ids.add(record["id"])

    findings = plan_validate.validate(all_plan_files, extra_known_ids=settled_ids)
    plan_texts = {pf: pf.read_text(errors="ignore") for pf in all_plan_files}
    findings = plan_validate.apply_acks(findings, plan_texts)
    unacked = [f for f in findings if f.plan == plan_file and not f.acked]
    if unacked:
        backend.close()
        print(
            f"⛔ Refusing to promote {plan_file.name}: intake validation failed.",
            file=sys.stderr,
        )
        for finding in unacked:
            print(f"  - {finding.check_id}: {finding.message}", file=sys.stderr)
        return 1

    # Promote the plan to sprint member before touching the queue. The commit
    # is the durable source of truth; the queue is rebuilt from it.
    rc = commit_and_push_status(plan_file, "queued")
    if rc != 0:
        backend.close()
        return _fail(
            f"Plan promotion failed for {plan_file.name}: could not commit/push "
            f"status update. Fix the git state and re-run `aet sprint add`."
        )

    task = new_task_from_plan(plan_file, settled_ids=settled_ids)
    task["status"] = "queued"
    queue.append(task)
    build_blocks(queue)

    if not lease_guard(args.queue_file, force=args.force):
        backend.close()
        return 1

    backend.save(queue)
    projections.on_add(task, is_new=True)
    backend.close()

    print(f"✓ Promoted {plan_file.name} to the sprint as {task['state']}.")
    return 0


app = typer.Typer()


@app.command("add")
def add(
    target: str = typer.Argument(..., help="Plan file path or task ID to promote"),
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
    allow_untracked: bool = typer.Option(
        False,
        "--allow-untracked",
        help=(
            "Promote the plan even if its file is not tracked in git. By default "
            "an untracked plan is refused so aet-work can retrieve it from "
            "origin/main; use this only for a throwaway spike."
        ),
    ),
) -> None:
    """Promote an approved plan into the sprint."""
    args = argparse.Namespace(
        target=target,
        queue_file=queue_file,
        history_file=history_file,
        plans_dir=plans_dir,
        config=config,
        force=force,
        allow_untracked=allow_untracked,
    )
    rc = _add(args)
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
