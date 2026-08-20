"""aet-work reconcile — Report and heal drift between plans and GitHub Issues.

Scans committed live plans and the mirrored ``aet:*`` issues, prints the
computed drift, and optionally applies corrective writes. Dry-run by default;
``--apply`` performs the writes through the fail-open projection dispatcher.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import typer

_SCRIPT_DIR = Path(__file__).resolve().parent
from aet.backends.factory import resolve_config  # noqa: E402
from aet.projections.dispatcher import resolve_projections  # noqa: E402


def _format_report(report: dict[str, Any]) -> str:
    lines: list[str] = []
    if not report.get("apply"):
        lines.append("DRY RUN — no changes applied (pass --apply to write)")
    lines.append(
        f"Live plans: {report.get('live_plans', 0)} | "
        f"Issues scanned: {report.get('issues_scanned', 0)}"
    )
    drift = report.get("drift", [])
    if not drift:
        lines.append("No drift.")
        return "\n".join(lines) + "\n"

    lines.append("Drift:")
    for item in drift:
        kind = item["type"]
        plan_id = item["plan_id"]
        if kind == "missing":
            lines.append(
                f"  missing: {plan_id} (would create {item.get('expected_label')})"
            )
        elif kind == "mislabeled":
            actual = ",".join(item.get("actual_labels") or [])
            lines.append(
                f"  mislabeled: {plan_id} "
                f"(#{item['issue_number']}: expected {item.get('expected_label')}, actual {actual})"
            )
        elif kind == "closed-live":
            lines.append(
                f"  closed-live: {plan_id} "
                f"(#{item['issue_number']} issue closed while plan is live)"
            )
        elif kind == "orphan":
            lines.append(
                f"  orphan: {plan_id} "
                f"(#{item['issue_number']} no live plan; not deleted)"
            )
    return "\n".join(lines) + "\n"


def _run(
    apply: bool,
    config: str,
    plans_dir: Path,
    queue_file: str,
    history_file: str,
    json_output: bool,
) -> int:
    config_data = resolve_config(config)
    dispatcher = resolve_projections(config_data)

    if not dispatcher.projections:
        print(
            "No projections configured; nothing to reconcile.",
            file=sys.stderr,
        )
        return 0

    reports = dispatcher.reconcile(apply=apply)

    if json_output:
        print(json.dumps(reports, indent=2))
        return 0

    for report in reports:
        if report is not None:
            print(_format_report(report), end="")

    return 0


app = typer.Typer(invoke_without_command=True)


@app.callback()
def reconcile(
    apply: bool = typer.Option(
        False,
        "--apply",
        help="Apply corrective writes (default is a dry run)",
    ),
    config: str = typer.Option(
        ".agents/aet-config.json",
        "--config",
        help="Path to AET backend configuration",
    ),
    plans_dir: Path = typer.Option(
        Path("docs/plans"),
        "--plans-dir",
        help="Directory containing atomic plan markdown files",
    ),
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
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Emit the raw reconcile report as JSON",
    ),
) -> None:
    """Reconcile live plans with their GitHub issue mirrors."""
    rc = _run(apply, config, plans_dir, queue_file, history_file, json_output)
    raise typer.Exit(rc)


def main(argv: list[str] | None = None) -> int:
    try:
        return app(argv or [], standalone_mode=False)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 0


if __name__ == "__main__":
    app()
