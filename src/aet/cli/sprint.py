"""aet-work sprint — Sprint membership commands.

``aet sprint add <plan>`` promotes an approved plan into the runnable sprint:
it adds the task to the ephemeral work queue and records a ``cut`` event in
the content-addressed ledger. The plan file itself is no longer mutated; queue
membership is the explicit sprint-add record.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import typer

_SCRIPT_DIR = Path(__file__).resolve().parent
from aet import plan_parser  # noqa: E402
from aet.admission import (  # noqa: E402
    Admitted,
    RefusalReason,
    Refused,
    Skipped,
    SkipReason,
    admit_plan,
    unacked_intake_findings,
)
from aet.admission import resolve_plan as resolve_plan  # noqa: E402, F401
from aet.admission import settled_ids_from as _settled_ids  # noqa: E402, F401
from aet.backends.factory import (  # noqa: E402
    create_backend,
    resolve_config,
)
from aet.backends.github_backend import BackendError, GitHubBackend  # noqa: E402
from aet.ledger import Ledger, resolve_ledger_path  # noqa: E402
from aet.projections.dispatcher import resolve_projections  # noqa: E402
from aet.queue import (  # noqa: E402
    QueueIntegrityError,
    append_history,
    build_blocks,
    lease_guard,
)


def _fail(message: str) -> int:
    print(f"⛔ {message}", file=sys.stderr)
    return 1


def _add(args: argparse.Namespace) -> int:
    plans_dir = Path(args.plans_dir)

    backend = create_backend(
        config_path=args.config,
        queue_file=args.queue_file,
        history_file=args.history_file,
    )
    backend.fetch()
    projections = resolve_projections(resolve_config(args.config), posture=backend.posture)

    try:
        data = backend.load()
    except QueueIntegrityError as exc:
        print(f"⛔ {exc}", file=sys.stderr)
        backend.close()
        return 1
    queue = data["queue"]
    history = data["history"]

    outcome = admit_plan(
        args.target,
        plans_dir=plans_dir,
        backend=backend,
        history_file=args.history_file,
        queue=queue,
        history=history,
        allow_blocked=True,
    )

    if isinstance(outcome, Skipped):
        if outcome.reason == SkipReason.ALREADY_SETTLED:
            backend.close()
            plan_name = outcome.plan_file.name if outcome.plan_file else args.target
            return _fail(f"Refusing to promote {plan_name}: task is already settled in history.")
        if outcome.reason == SkipReason.ALREADY_IN_QUEUE:
            existing_task = outcome.existing_task or {}
            plan_file = outcome.plan_file or resolve_plan(args.target, plans_dir)
            if plan_file is None or not plan_file.is_file():
                backend.close()
                return _fail(f"No plan found for '{args.target}' in {plans_dir}")

            plan_name = plan_file.name

            # Check inertness predicate (R-3)
            inert, blocking_field = plan_parser.is_task_inert(existing_task)
            if not inert:
                backend.close()
                return _fail(f"Refusing to re-ingest {plan_name}: task carries run state ({blocking_field}).")

            # Run intake validation on the updated plan file
            unacked, record = unacked_intake_findings(
                plan_file,
                plans_dir,
                backend,
                history_file=args.history_file,
                queue=queue,
                history=history,
            )
            if unacked:
                backend.close()
                print(
                    f"⛔ Refusing to promote {plan_name}: intake validation failed.",
                    file=sys.stderr,
                )
                for finding in unacked:
                    print(
                        f"  - {finding.check_id}: {finding.message}",
                        file=sys.stderr,
                    )
                return 1

            # Re-run new_task_from_plan against the plan file and current board (R-1, R-4)
            settled_ids = _settled_ids(backend=backend, history_file=args.history_file, history=history)
            rebuilt_task = plan_parser.new_task_from_plan(
                plan_file,
                live_tasks=queue,
                settled_ids=settled_ids,
            )

            # Compare stored and rebuilt spec to choose outcome reporting (R-2)
            old_spec = existing_task.get("spec")
            new_spec = rebuilt_task.get("spec")
            spec_changed = old_spec != new_spec

            # Carry forward id, transition history, and run fields (R-4)
            old_state = existing_task.get("state")
            new_state = rebuilt_task.get("state")
            history_list = list(existing_task.get("history", []))

            updated_task = dict(existing_task)
            updated_task["title"] = rebuilt_task["title"]
            updated_task["plan_file"] = rebuilt_task["plan_file"]
            updated_task["blocked_by"] = rebuilt_task["blocked_by"]
            updated_task["pending_blockers"] = rebuilt_task["pending_blockers"]
            updated_task["state"] = new_state
            updated_task["work_class"] = rebuilt_task["work_class"]
            updated_task["spec"] = new_spec
            updated_task["history"] = history_list

            if old_state != new_state:
                append_history(updated_task, old_state, new_state, "sync")

            # Update queue in place
            for i, t in enumerate(queue):
                if t.get("id") == existing_task.get("id"):
                    queue[i] = updated_task
                    break

            build_blocks(queue)

            if not lease_guard(args.queue_file, force=args.force):
                backend.close()
                return 1

            backend.save(queue)
            backend.push()

            # Record cut event in ledger
            ledger_path = resolve_ledger_path()
            ledger = Ledger(ledger_path)
            plan_hash = hashlib.sha256(plan_file.read_bytes()).hexdigest()
            ledger.write_event(
                source="sprint-add",
                task=updated_task["id"],
                kind="cut",
                ref=plan_hash,
                ref_kind="plan-hash",
            )

            projections.on_add(updated_task, is_new=False)
            backend.close()

            if spec_changed:
                print(f"✓ {plan_file.name} spec re-ingested.")
            else:
                print(f"✓ {plan_file.name} spec unchanged.")
            return 0

    if isinstance(outcome, Refused):
        backend.close()
        if outcome.reason == RefusalReason.PLAN_NOT_FOUND:
            return _fail(f"No plan found for '{args.target}' in {plans_dir}")
        if outcome.reason == RefusalReason.VALIDATION_FAILED:
            plan_name = outcome.plan_file.name if outcome.plan_file else args.target
            print(
                f"⛔ Refusing to promote {plan_name}: intake validation failed.",
                file=sys.stderr,
            )
            findings = outcome.findings or []
            for finding in findings:
                print(
                    f"  - {finding.check_id}: {finding.message}",
                    file=sys.stderr,
                )
            if findings and all(f.check_id == "rtrace" and "cites unknown requirement" in f.message for f in findings):
                print(
                    "  note: this check compares citations against requirements that "
                    "already exist,\n"
                    "        so a plan that introduces one cannot satisfy it. If the "
                    "requirement is\n"
                    "        this plan's own deliverable, an ack is the intended route.",
                    file=sys.stderr,
                )
            print(
                "  Fix the plan, or override a check that does not apply by adding a line to it:",
                file=sys.stderr,
            )
            print("    ⚠️ VALIDATE ACK: <check-id> — <reason>", file=sys.stderr)
            if outcome.coverage:
                for task_id in outcome.coverage.unreadable:
                    print(
                        f"  note: task record {task_id} carries no readable spec; "
                        "its requirement coverage is not counted",
                        file=sys.stderr,
                    )
                if outcome.coverage.source_error:
                    print(
                        f"  note: no coverage read from the task record ({outcome.coverage.source_error})",
                        file=sys.stderr,
                    )
            return 1
        if outcome.reason == RefusalReason.BLOCKED:
            plan_name = outcome.plan_file.name if outcome.plan_file else args.target
            blockers_str = f"blocked by {', '.join(outcome.blockers)}" if outcome.blockers else "blocked"
            return _fail(f"Refusing to promote {plan_name}: {blockers_str}")

    assert isinstance(outcome, Admitted)
    task = outcome.task
    plan_file = outcome.plan_file

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

    print(f"✓ {plan_file.name} queued without publishing (plan durability deferred to PR).")
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
    projections = resolve_projections(resolve_config(args.config), posture=backend.posture)

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

    for candidate in candidates:
        task_id = candidate["task_id"]
        issue_number = candidate["issue_number"]

        outcome = admit_plan(
            task_id,
            plans_dir=plans_dir,
            backend=backend,
            history_file=args.history_file,
            queue=queue,
            history=history,
            allow_blocked=False,
        )

        if isinstance(outcome, Skipped):
            if outcome.reason == SkipReason.ALREADY_IN_QUEUE:
                skipped.append((task_id, issue_number, "already in queue"))
            elif outcome.reason == SkipReason.ALREADY_SETTLED:
                skipped.append((task_id, issue_number, "already settled"))
            continue

        if isinstance(outcome, Refused):
            if outcome.reason == RefusalReason.PLAN_NOT_FOUND:
                refused.append((task_id, issue_number, "plan file not found"))
            elif outcome.reason == RefusalReason.VALIDATION_FAILED:
                findings = outcome.findings or []
                detail = "; ".join(f"{f.check_id}: {f.message}" for f in findings[:3])
                if len(findings) > 3:
                    detail += f"; (+{len(findings) - 3} more)"
                refused.append(
                    (
                        task_id,
                        issue_number,
                        f"intake validation failed — {detail}",
                    )
                )
            elif outcome.reason == RefusalReason.BLOCKED:
                reason = f"blocked by {', '.join(outcome.blockers)}" if outcome.blockers else "blocked"
                refused.append((task_id, issue_number, reason))
            continue

        assert isinstance(outcome, Admitted)
        queue.append(outcome.task)
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
        print(
            f"⛔ Refused {task_id} (#{issue_number}): {reason}.",
            file=sys.stderr,
        )
    for task_id, issue_number, reason in skipped:
        print(f"⚠️  Skipped {task_id} (#{issue_number}): {reason}.")

    if not admitted and not refused and not skipped:
        print("✓ No sprint candidates to intake.")

    return 0


app = typer.Typer()


@app.command("add")
def add(
    target: str = typer.Argument(..., help="Plan file path or task ID to promote"),
    queue_file: str = typer.Option(".agents/aet-queue", "--queue-file", help="Path to queue anchor"),
    history_file: str = typer.Option(".agents/work-history.jsonl", "--history-file", help="Path to work-history.jsonl"),
    plans_dir: str = typer.Option("docs/plans", "--plans-dir", help="Directory containing atomic plan markdown files"),
    config: str = typer.Option(".agents/aet-config.json", "--config", help="Path to AET backend configuration"),
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
    queue_file: str = typer.Option(".agents/aet-queue", "--queue-file", help="Path to aet-queue"),
    history_file: str = typer.Option(".agents/work-history.jsonl", "--history-file", help="Path to work-history.jsonl"),
    plans_dir: str = typer.Option("docs/plans", "--plans-dir", help="Directory containing atomic plan markdown files"),
    config: str = typer.Option(".agents/aet-config.json", "--config", help="Path to AET backend configuration"),
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
