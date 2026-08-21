"""aet-work sprint — Sprint membership commands.

``aet sprint add <plan>`` promotes an approved plan into the runnable sprint:
it adds the task to the ephemeral work queue and records a ``cut`` event in
the content-addressed ledger. The plan file itself is no longer mutated; queue
membership is the explicit sprint-add record.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import typer

_SCRIPT_DIR = Path(__file__).resolve().parent
from aet import plan_validate  # noqa: E402
from aet.backends.factory import (  # noqa: E402
    create_backend,
    resolve_config,
)
from aet.backends.github_backend import BackendError, GitHubBackend  # noqa: E402
from aet.ledger import Ledger, resolve_ledger_path  # noqa: E402
from aet.plan_parser import (  # noqa: E402
    new_task_from_plan,
    resolve_plan_arg,
    stage_from_plan,
)
from aet.projections.dispatcher import resolve_projections  # noqa: E402
from aet.queue import (  # noqa: E402
    QueueIntegrityError,
    build_blocks,
    lease_guard,
)


def resolve_plan(target: str, plans_dir: Path) -> Path | None:
    """Resolve ``target`` to a plan file path.

    Wraps the shared resolver and converts its ``ValueError`` into ``None``,
    preserving ``aet sprint add``'s existing contract.
    """
    try:
        return Path(resolve_plan_arg(target, plans_dir=plans_dir))
    except ValueError:
        return None


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
    backend.fetch()
    projections = resolve_projections(
        resolve_config(args.config), posture=backend.posture
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

    task = new_task_from_plan(plan_file, live_tasks=queue)
    queue.append(task)
    build_blocks(queue)

    if not lease_guard(args.queue_file, force=args.force):
        backend.close()
        return 1

    backend.save(queue)
    backend.push()

    # Record the intake event in the content-addressed ledger.
    ledger_path = resolve_ledger_path()
    ledger = Ledger(ledger_path)
    plan_hash = hashlib.sha256(plan_file.read_bytes()).hexdigest()
    ledger.write_event(
        source="sprint-add",
        task=task["id"],
        kind="cut",
        ref=plan_hash,
        ref_kind="plan-hash",
    )

    projections.on_add(task, is_new=True)
    backend.close()

    print(
        f"✓ {plan_file.name} queued without publishing "
        f"(plan durability deferred to PR)."
    )
    return 0


def _intake(args: argparse.Namespace) -> int:
    """Read ``aet:sprint`` issues from GitHub and admit valid candidates."""
    plans_dir = Path(args.plans_dir)
    backend = create_backend(
        config_path=args.config,
        queue_file=args.queue_file,
        history_file=args.history_file,
    )
    backend.fetch()
    projections = resolve_projections(
        resolve_config(args.config), posture=backend.posture
    )

    try:
        data = backend.load()
    except QueueIntegrityError as exc:
        print(f"⛔ {exc}", file=sys.stderr)
        backend.close()
        return 1
    queue = data["queue"]
    history = data["history"]

    github = next(
        (p for p in projections.projections if isinstance(p, GitHubBackend)),
        None,
    )
    if github is None:
        print(
            "⚠️  No GitHub projection configured; nothing to intake from the forge.",
            file=sys.stderr,
        )
        backend.close()
        return 0

    try:
        candidates = github.find_sprint_candidates()
    except BackendError as exc:
        print(f"⛔ Forge read failed; halting intake: {exc}", file=sys.stderr)
        backend.close()
        return 1

    admitted: list[tuple[str, int]] = []
    refused: list[tuple[str, int, str]] = []
    skipped: list[tuple[str, int, str]] = []

    settled_ids = {t.get("id") for t in history if t.get("id")}
    live_ids = {t.get("id") for t in queue if t.get("id")}

    for candidate in candidates:
        task_id = candidate["task_id"]
        issue_number = candidate["issue_number"]

        if task_id in live_ids:
            skipped.append((task_id, issue_number, "already in queue"))
            continue
        if task_id in settled_ids:
            skipped.append((task_id, issue_number, "already settled"))
            continue

        plan_file = resolve_plan(task_id, plans_dir)
        if plan_file is None or not plan_file.exists():
            refused.append((task_id, issue_number, "plan file not found"))
            continue

        stage = stage_from_plan(plan_file)
        if stage != "plan-approved":
            refused.append(
                (task_id, issue_number, f"plan stage is '{stage or 'unknown'}'")
            )
            continue

        task = new_task_from_plan(plan_file, live_tasks=queue)
        if task["state"] == "blocked":
            blockers = [
                b
                for b in task.get("blocked_by", [])
                if b in live_ids
                and next(
                    (
                        t
                        for t in queue
                        if t.get("id") == b
                        and t.get("state") in {"merged", "abandoned"}
                    ),
                    None,
                )
                is None
            ]
            reason = f"blocked by {', '.join(blockers)}" if blockers else "blocked"
            refused.append((task_id, issue_number, reason))
            continue

        queue.append(task)
        admitted.append((task_id, issue_number))

    if admitted:
        build_blocks(queue)

        if not lease_guard(args.queue_file, force=args.force):
            backend.close()
            return 1

        backend.save(queue)
        backend.push()

        ledger_path = resolve_ledger_path()
        ledger = Ledger(ledger_path)
        for task_id, issue_number in admitted:
            task = next((t for t in queue if t.get("id") == task_id), None)
            if task is None:
                continue
            plan_file = Path(task["plan_file"])
            plan_hash = hashlib.sha256(plan_file.read_bytes()).hexdigest()
            ledger.write_event(
                source="sprint-intake",
                task=task_id,
                kind="cut",
                ref=plan_hash,
                ref_kind="plan-hash",
            )
            task["github_issue_number"] = issue_number
            projections.on_add(task, is_new=False)

    backend.close()

    for task_id, issue_number in admitted:
        print(f"✓ Admitted {task_id} (#{issue_number}) to the sprint.")
    for task_id, issue_number, reason in refused:
        print(f"⛔ Refused {task_id} (#{issue_number}): {reason}.", file=sys.stderr)
    for task_id, issue_number, reason in skipped:
        print(f"⚠️  Skipped {task_id} (#{issue_number}): {reason}.")

    if not admitted and not refused and not skipped:
        print("✓ No sprint candidates to intake.")

    return 0


app = typer.Typer()


@app.command("add")
def add(
    target: str = typer.Argument(..., help="Plan file path or task ID to promote"),
    queue_file: str = typer.Option(
        ".agents/aet-queue", "--queue-file", help="Path to queue anchor"
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
    """Promote an approved plan into the sprint."""
    args = argparse.Namespace(
        target=target,
        queue_file=queue_file,
        history_file=history_file,
        plans_dir=plans_dir,
        config=config,
        force=force,
    )
    rc = _add(args)
    raise typer.Exit(rc)


@app.command("intake")
def intake(
    queue_file: str = typer.Option(
        ".agents/aet-queue", "--queue-file", help="Path to aet-queue"
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
    """Read aet:sprint issues from GitHub and admit valid candidates."""
    args = argparse.Namespace(
        queue_file=queue_file,
        history_file=history_file,
        plans_dir=plans_dir,
        config=config,
        force=force,
    )
    rc = _intake(args)
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
