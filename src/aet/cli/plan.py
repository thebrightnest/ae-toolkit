"""aet-work plan — plan-quality commands.

``aet plan validate`` runs the four-family check suite and applies the
``⚠️ VALIDATE ACK`` escape hatch. It exits 0 on a clean or fully-acked plan
and exits 1 with named per-check errors otherwise.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Optional

import typer

_SCRIPT_DIR = Path(__file__).resolve().parent
from aet import plan_parser, plan_validate  # noqa: E402


def _repo_root_from(path: Path) -> Path:
    """Resolve the repository root via git, falling back to layout heuristics."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=path.parent,
            capture_output=True,
            text=True,
            check=True,
        )
        return Path(result.stdout.strip())
    except (OSError, subprocess.CalledProcessError):
        if path.parent.name == "plans" and path.parent.parent.name == "docs":
            return path.parent.parent.parent
        return path.parent.parent


def _fail(message: str) -> int:
    print(f"error: {message}", file=sys.stderr)
    return 1


def cmd_validate(args: argparse.Namespace) -> int:
    if args.plans:
        plan_paths = [Path(p).resolve() for p in args.plans]
        repo_root = _repo_root_from(plan_paths[0])
    else:
        repo_root = _repo_root_from(Path.cwd())
        plans_dir = repo_root / "docs" / "plans"
        plan_paths = sorted(plans_dir.glob("*.md")) if plans_dir.exists() else []

    live_paths = [p for p in plan_paths if not plan_parser.is_settled_plan(p)]

    if not live_paths:
        print("✓ no live plans to validate")
        return 0

    missing = [p for p in live_paths if not p.exists()]
    if missing:
        return _fail(f"plan file not found: {missing[0]}")

    findings = plan_validate.validate(live_paths, repo_root=repo_root)
    plan_texts = {p: p.read_text(errors="ignore") for p in live_paths}
    findings = plan_validate.apply_acks(findings, plan_texts)

    unacked = [f for f in findings if not f.acked]

    for finding in findings:
        if finding.acked:
            print(
                f"{finding.plan.name}: {finding.check_id}: "
                f"acked — {finding.ack_reason}"
            )

    if unacked:
        for finding in unacked:
            print(
                f"{finding.plan.name}: {finding.check_id}: {finding.message}",
                file=sys.stderr,
            )
        return 1

    print("✓ all plans passed validation")
    return 0


app = typer.Typer()


@app.command("validate")
def validate(
    plans: Optional[list[str]] = typer.Argument(None, help="Plan files to validate (default: docs/plans/*.md)"),
) -> None:
    """Validate plan files for intake quality."""
    if plans is None:
        plans = []
    args = argparse.Namespace(plans=plans)
    rc = cmd_validate(args)
    raise typer.Exit(rc)


if __name__ == "__main__":
    app()
