"""aet-work reconcile — Report and heal drift between plans and GitHub Issues.

Scans committed live plans and the mirrored ``aet:*`` issues, prints the
computed drift, and optionally applies corrective writes. Dry-run by default;
``--apply`` performs the writes through the fail-open projection dispatcher.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_SCRIPT_DIR = Path(__file__).resolve().parent
from aet.backends.factory import resolve_config  # noqa: E402
from aet.projections.dispatcher import resolve_projections  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Reconcile live plans with their GitHub issue mirrors.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply corrective writes (default is a dry run)",
    )
    parser.add_argument(
        "--config",
        default=".agents/aet-work.json",
        help="Path to aet-work backend configuration",
    )
    parser.add_argument(
        "--plans-dir",
        default="docs/plans",
        help="Directory containing atomic plan markdown files",
    )
    parser.add_argument(
        "--queue-file",
        default=".agents/work-queue.json",
        help="Path to work-queue.json",
    )
    parser.add_argument(
        "--history-file",
        default=".agents/work-history.jsonl",
        help="Path to work-history.jsonl",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Emit the raw reconcile report as JSON",
    )
    return parser


def parse_args(argv) -> argparse.Namespace:
    return build_parser().parse_args(argv)


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


def main(argv: list[str] | None = None):
    args = parse_args(argv)
    config = resolve_config(args.config)
    dispatcher = resolve_projections(config)

    if not dispatcher.projections:
        print(
            "No projections configured; nothing to reconcile.",
            file=sys.stderr,
        )
        return 0

    reports = dispatcher.reconcile(apply=args.apply)

    if args.json_output:
        print(json.dumps(reports, indent=2))
        return 0

    for report in reports:
        if report is not None:
            print(_format_report(report), end="")

    return 0


if __name__ == "__main__":
    sys.exit(main())
