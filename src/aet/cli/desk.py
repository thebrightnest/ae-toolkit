"""aet-work desk — Review cockpit.

Default mode lists every task in the ``awaiting_merge`` state, riskiest first,
with the evidence needed to decide on it.  The ``--eligibility`` projection
shows per-class clean-merge counts and zero-review eligibility.  Merge/abandon
actions are handled by ``twe-03``.
"""

from __future__ import annotations

import argparse
import importlib.machinery
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import typer

_SCRIPT_DIR = Path(__file__).resolve().parent
from aet import (  # noqa: E402
    evidence,
    plan_parser,
    project_id,
    risk,
    telemetry,
    track_record,
)
from aet.backends.factory import create_backend  # noqa: E402
from aet.queue import current_state  # noqa: E402

# Load aet-state as a module so desk actions can reuse queue mutations
# rather than re-implementing closure logic.
_AET_STATE_PY = _SCRIPT_DIR / "aet_state.py"
_aet_state_spec = importlib.util.spec_from_loader(
    "aet_state_desk",
    importlib.machinery.SourceFileLoader("aet_state_desk", str(_AET_STATE_PY)),
)
aet_state = importlib.util.module_from_spec(_aet_state_spec)
_aet_state_spec.loader.exec_module(aet_state)

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Review cockpit for awaiting_merge tasks."
    )
    parser.add_argument(
        "--eligibility",
        action="store_true",
        help="Show per-class clean-merge counts and zero-review eligibility.",
    )
    parser.add_argument(
        "--policy",
        default=track_record.DEFAULT_POLICY_PATH,
        help="Path to the zero-review policy JSON.",
    )
    parser.add_argument(
        "--queue-file",
        default=".agents/work-queue.json",
        help="Path to work-queue.json",
    )
    parser.add_argument(
        "--history-file",
        default=".agents/work-history.jsonl",
        help="Path to the settled work-history JSONL (also used for eligibility).",
    )
    parser.add_argument(
        "--plans-dir",
        default="docs/plans",
        help="Directory containing atomic plan markdown files",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit a machine-readable JSON projection.",
    )

    # Shared args for the action subcommands.
    action_parent = argparse.ArgumentParser(add_help=False)
    action_parent.add_argument(
        "--queue-file",
        default=".agents/work-queue.json",
        help="Path to work-queue.json",
    )
    action_parent.add_argument(
        "--history-file",
        default=".agents/work-history.jsonl",
        help="Path to the settled work-history JSONL.",
    )

    sub = parser.add_subparsers(dest="command")

    merge = sub.add_parser(
        "merge",
        parents=[action_parent],
        help="Merge a PR and record the task as merged.",
        description="Resolve an awaiting_merge task, merge its PR, and drive the aet-ship/record-merge closure path.",
    )
    merge.add_argument("task_id", help="Task ID to merge.")

    abandon = sub.add_parser(
        "abandon",
        parents=[action_parent],
        help="Abandon a task with a recorded reason.",
        description="Resolve an awaiting_merge task and record the terminal abandoned transition.",
    )
    abandon.add_argument("task_id", help="Task ID to abandon.")
    abandon.add_argument(
        "--reason",
        required=True,
        help="Required reason for abandoning the task.",
    )

    return parser


def _plan_path(task: dict, plans_dir: str) -> Path:
    """Resolve the plan file for a task, preferring an absolute plan_file."""
    plan_file = task.get("plan_file")
    if plan_file:
        path = Path(plan_file)
        if path.is_absolute():
            return path
    return Path(plans_dir) / f"{task.get('id', '')}.md"


def _load_evidence(task_id: str, kind: str) -> dict[str, object] | None:
    """Read a single verdict file, or ``None`` when it is absent or unreadable."""
    path = evidence.evidence_path(task_id, kind)
    if not path.exists():
        return None
    try:
        return evidence.read_verdict(path)
    except (OSError, json.JSONDecodeError):
        return None


def _findings_count(record: dict[str, object] | None, kind: str) -> int:
    """Return the number of findings/divergences in a verdict record."""
    if record is None:
        return 0
    if kind == "sync-docs":
        return len(record.get("divergences") or [])  # type: ignore[arg-type]
    return len(record.get("findings") or [])  # type: ignore[arg-type]


def _telemetry_signals(task_id: str) -> tuple[dict[str, object] | None, int]:
    """Return the latest stage record and the highest claimed tests_failed.

    Walks the telemetry archive for this project once, collecting the most
    recent ``stage_record`` (for ``files_modified``) and the maximum
    ``tests_failed`` from ``test_run_record``s.

    Provenance (ADR-051): test counts exist only on ``source: "verdict"``
    records — the QA agent's self-report — so this signal is declared over
    claimed runs. Observed (``"wire"``) records carry timings, not counts, and
    pre-ADR-051 records carry no provenance at all; neither is counted here.
    """
    slug = project_id.derive_project_slug()
    root = telemetry.archive_dir() / slug
    latest_stage: dict[str, object] | None = None
    tests_failed = 0
    if not root.exists():
        return latest_stage, tests_failed

    for path in root.rglob("*.jsonl"):
        for record in telemetry.read_jsonl(path):
            if record.get("task_id") != task_id:
                continue
            if record.get("type") == "stage":
                if latest_stage is None or record.get("end_time", "") > latest_stage.get(  # type: ignore[operator]
                    "end_time", ""
                ):
                    latest_stage = record
            elif record.get("type") == "test_run":
                if record.get("source") != "verdict":
                    continue
                failed = record.get("tests_failed") or 0
                if isinstance(failed, int) and failed > tests_failed:
                    tests_failed = failed
    return latest_stage, tests_failed


def _build_evidence_bundle(
    task_id: str, required: list[str]
) -> tuple[dict[str, dict[str, object]], list[str], list[str]]:
    """Load evidence, build per-kind entries, and collect gaps.

    Returns ``(bundle, failed_verdicts, missing_required_verdicts)``.
    """
    bundle: dict[str, dict[str, object]] = {}
    failed: list[str] = []
    missing: list[str] = []

    for kind in evidence.SCHEMAS:
        record = _load_evidence(task_id, kind)
        is_required = kind in required
        entry: dict[str, object] = {"present": record is not None, "required": is_required}
        if record is not None:
            entry["verdict"] = record.get("verdict")
            entry["summary"] = record.get("summary", "")
            if kind == "qa":
                entry["tests_total"] = record.get("tests_total")
                entry["tests_passed"] = record.get("tests_passed")
                entry["tests_failed"] = record.get("tests_failed")
            else:
                entry["findings_count"] = _findings_count(record, kind)

        if is_required and record is None:
            missing.append(kind)
            entry["gap"] = True
        elif record is not None and record.get("verdict") == "fail":
            failed.append(kind)

        bundle[kind] = entry
    return bundle, failed, missing


def _signals_for_task(
    task: dict,
    plan_data: dict[str, object],
    bundle: dict[str, dict[str, object]],
    latest_stage: dict[str, object] | None,
    telemetry_tests_failed: int,
) -> dict[str, object]:
    """Assemble the signal dict consumed by ``risk.score``."""
    qa_tests_failed = bundle.get("qa", {}).get("tests_failed") or 0
    tests_failed = max(
        telemetry_tests_failed,
        qa_tests_failed if isinstance(qa_tests_failed, int) else 0,
    )
    return {
        "work_class": task.get("work_class") or "unclassified",
        "size": plan_data.get("size") or "",
        "review_findings": bundle.get("review", {}).get("findings_count", 0),
        "cso_findings": bundle.get("cso", {}).get("findings_count", 0),
        "sync_docs_divergences": bundle.get("sync-docs", {}).get("findings_count", 0),
        "failed_verdicts": [
            kind for kind, entry in bundle.items() if entry.get("verdict") == "fail"
        ],
        "missing_required_verdicts": [
            kind for kind, entry in bundle.items() if entry.get("required") and not entry.get("present")
        ],
        "files_modified": len((latest_stage or {}).get("files_modified") or []),
        "tests_failed": tests_failed,
    }


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


def _render_human(rows: list[dict[str, object]]) -> None:
    """Print the risk-ranked human table and the per-task evidence bundle."""
    if not rows:
        print("No awaiting_merge tasks.")
        return

    print(f"Desk: {len(rows)} awaiting_merge task(s), riskiest first\n")

    headers = ["ID", "Title", "Risk", "Size", "Class", "Factors", "Gaps"]
    table_rows: list[list[str]] = []
    for row in rows:
        task = row["task"]  # type: ignore[index]
        table_rows.append(
            [
                str(task.get("id", "")),
                str(task.get("title", ""))[:40],
                str(row["score"]),
                str(row["plan_data"].get("size", "")),
                str(task.get("work_class", "unclassified")),
                ", ".join(row["factors"]) or "—",
                ", ".join(row["gaps"]) or "—",
            ]
        )
    for line in _render_table(headers, table_rows):
        print(line)

    print("\nEvidence bundle:")
    for row in rows:
        task = row["task"]  # type: ignore[index]
        bundle = row["bundle"]  # type: ignore[index]
        print(f"\n{task.get('id')}:")
        for kind in evidence.SCHEMAS:
            entry = bundle[kind]
            if not entry.get("present"):
                suffix = " (required)" if entry.get("required") else " (not required)"
                print(f"  {kind}: missing{suffix}")
                continue
            verdict = entry.get("verdict", "?")
            summary = str(entry.get("summary", ""))[:60]
            if kind == "qa":
                passed = entry.get("tests_passed")
                total = entry.get("tests_total")
                extra = f" [{passed}/{total} passed]"
            else:
                extra = f" ({entry.get('findings_count', 0)} findings)"
            print(f"  {kind}: {verdict} — {summary}{extra}")


def _json_projection(rows: list[dict[str, object]]) -> dict[str, object]:
    """Build the machine-readable desk projection (minimal v1 schema)."""
    return {
        "summary": {"awaiting_merge": len(rows)},
        "tasks": [
            {
                "id": row["task"].get("id"),
                "title": row["task"].get("title"),
                "state": current_state(row["task"]),
                "risk_score": row["score"],
                "factors": row["factors"],
                "gaps": row["gaps"],
                "evidence": row["bundle"],
            }
            for row in rows
        ],
    }


def _run_eligibility(args: argparse.Namespace) -> int:
    """Emit the zero-review eligibility projection."""
    policy = track_record.load_policy(args.policy)
    project_slug = project_id.derive_project_slug()
    report: dict[str, dict] = {}
    for work_class in ("trivial", "normal", "critical"):
        report[work_class] = track_record.class_eligibility(
            work_class,
            policy=policy,
            history_file=args.history_file,
            project_slug=project_slug,
        )

    if args.json:
        print(json.dumps(report, indent=2))
        return 0

    for line in track_record.format_eligibility_report(
        policy=policy,
        history_file=args.history_file,
        project_slug=project_slug,
    ):
        print(line)
    return 0


def _resolve_actionable_task(
    args: argparse.Namespace,
) -> tuple[dict[str, object] | None, object | None, str]:
    """Load the queue, find the task, and fail closed unless it is awaiting_merge.

    Returns ``(task, backend, cwd)`` on success.  On failure prints a named
    error to stderr and returns ``(None, None, "")``; the caller should
    return 1.
    """
    config_path = str(Path(args.queue_file).with_name("aet-config.json"))
    backend = create_backend(
        config_path=config_path,
        queue_file=args.queue_file,
        history_file=args.history_file,
    )
    data = backend.load(verify=False)
    queue = data["queue"]
    task = next((t for t in queue if t.get("id") == args.task_id), None)
    if task is None:
        print(f"error: task not found: {args.task_id}", file=sys.stderr)
        return None, None, ""

    state = current_state(task)
    if state != "awaiting_merge":
        print(
            f"error: task {args.task_id} is not awaiting_merge (state is {state})",
            file=sys.stderr,
        )
        return None, None, ""

    cwd = str(Path(args.queue_file).resolve().parent)
    return task, backend, cwd


def _run_merge(args: argparse.Namespace) -> int:
    """Merge the PR for an awaiting_merge task and record closure."""
    task, _backend, cwd = _resolve_actionable_task(args)
    if task is None:
        return 1
    branch = task.get("branch")
    if not branch:
        print(f"error: task {args.task_id} has no branch", file=sys.stderr)
        return 1

    result = subprocess.run(
        ["gh", "pr", "merge", branch, "--squash"],
        capture_output=True,
        text=True,
        cwd=cwd,
        check=False,
    )
    if result.returncode != 0:
        print(
            f"error: gh pr merge failed for {branch}: {result.stderr.strip()}",
            file=sys.stderr,
        )
        return 1

    ns = aet_state.argparse.Namespace(
        command="record-merge",
        task_id=args.task_id,
        queue=args.queue_file,
        branch=branch,
        merge_commit=None,
        plan=task.get("plan_file"),
        dry_run=False,
    )
    return aet_state.cmd_record_merge(ns)


def _run_abandon(args: argparse.Namespace) -> int:
    """Record the terminal abandoned transition for an awaiting_merge task."""
    task, _backend, cwd = _resolve_actionable_task(args)
    if task is None:
        return 1
    ns = aet_state.argparse.Namespace(
        command="transition",
        task_id=args.task_id,
        from_stage="awaiting_merge",
        to_stage="abandoned",
        queue=args.queue_file,
        reason=args.reason,
        dry_run=False,
    )
    rc = aet_state.cmd_transition(ns)
    if rc != 0:
        return rc

    return 0


def _run_risk_view(args: argparse.Namespace) -> int:
    """Emit the risk-ranked awaiting_merge view."""
    config_path = str(Path(args.queue_file).with_name("aet-config.json"))
    backend = create_backend(
        config_path=config_path,
        queue_file=args.queue_file,
        history_file=args.history_file,
    )
    data = backend.load(verify=False)
    queue = data["queue"]

    desk_tasks = [t for t in queue if current_state(t) == "awaiting_merge"]
    rows: list[dict[str, object]] = []

    for task in desk_tasks:
        plan_path = _plan_path(task, args.plans_dir)
        plan_data = (
            plan_parser.parse_frontmatter(plan_path)
            if plan_path.exists()
            else {}
        )
        required = plan_parser.required_verdict_kinds(plan_data)
        bundle, failed_verdicts, missing_verdicts = _build_evidence_bundle(
            task["id"], required
        )
        latest_stage, telemetry_tests_failed = _telemetry_signals(task["id"])
        signals = _signals_for_task(
            task, plan_data, bundle, latest_stage, telemetry_tests_failed
        )
        score, factors = risk.score(signals)
        gaps = missing_verdicts + failed_verdicts

        rows.append(
            {
                "task": task,
                "plan_data": plan_data,
                "bundle": bundle,
                "score": score,
                "factors": factors,
                "gaps": gaps,
            }
        )

    # Deterministic ordering: risk descending, then task id for stable ties.
    rows.sort(key=lambda r: (-r["score"], r["task"].get("id", "")))

    if args.json:
        print(json.dumps(_json_projection(rows), indent=2, default=str))
        return 0

    _render_human(rows)
    return 0


def main(argv: list[str] | None = None):
    args = build_parser().parse_args(argv)
    if args.command == "merge":
        return _run_merge(args)
    if args.command == "abandon":
        return _run_abandon(args)
    if args.eligibility:
        return _run_eligibility(args)
    return _run_risk_view(args)


app = typer.Typer(
    name="desk",
    help="Review cockpit for awaiting_merge tasks.",
)


@app.callback(invoke_without_command=True)
def desk_callback(
    ctx: typer.Context,
    eligibility: bool = typer.Option(
        False,
        "--eligibility",
        help="Show per-class clean-merge counts and zero-review eligibility.",
    ),
    policy: str = typer.Option(
        track_record.DEFAULT_POLICY_PATH,
        "--policy",
        help="Path to the zero-review policy JSON.",
    ),
    queue_file: str = typer.Option(
        ".agents/work-queue.json",
        "--queue-file",
        help="Path to work-queue.json",
    ),
    history_file: str = typer.Option(
        ".agents/work-history.jsonl",
        "--history-file",
        help="Path to the settled work-history JSONL (also used for eligibility).",
    ),
    plans_dir: str = typer.Option(
        "docs/plans",
        "--plans-dir",
        help="Directory containing atomic plan markdown files",
    ),
    json: bool = typer.Option(
        False,
        "--json",
        help="Emit a machine-readable JSON projection.",
    ),
) -> None:
    """Review cockpit for awaiting_merge tasks."""
    if ctx.invoked_subcommand is not None:
        return
    args = argparse.Namespace(
        eligibility=eligibility,
        policy=policy,
        queue_file=queue_file,
        history_file=history_file,
        plans_dir=plans_dir,
        json=json,
    )
    if eligibility:
        raise typer.Exit(_run_eligibility(args))
    raise typer.Exit(_run_risk_view(args))


@app.command(name="merge")
def desk_merge(
    task_id: str = typer.Argument(..., help="Task ID to merge."),
    queue_file: str = typer.Option(
        ".agents/work-queue.json",
        "--queue-file",
        help="Path to work-queue.json",
    ),
    history_file: str = typer.Option(
        ".agents/work-history.jsonl",
        "--history-file",
        help="Path to the settled work-history JSONL.",
    ),
) -> None:
    """Merge a PR and record the task as merged."""
    args = argparse.Namespace(
        task_id=task_id,
        queue_file=queue_file,
        history_file=history_file,
    )
    raise typer.Exit(_run_merge(args))


@app.command(name="abandon")
def desk_abandon(
    task_id: str = typer.Argument(..., help="Task ID to abandon."),
    reason: str = typer.Option(
        ...,
        "--reason",
        help="Required reason for abandoning the task.",
    ),
    queue_file: str = typer.Option(
        ".agents/work-queue.json",
        "--queue-file",
        help="Path to work-queue.json",
    ),
    history_file: str = typer.Option(
        ".agents/work-history.jsonl",
        "--history-file",
        help="Path to the settled work-history JSONL.",
    ),
) -> None:
    """Abandon a task with a recorded reason."""
    args = argparse.Namespace(
        task_id=task_id,
        reason=reason,
        queue_file=queue_file,
        history_file=history_file,
    )
    raise typer.Exit(_run_abandon(args))


if __name__ == "__main__":
    app()
