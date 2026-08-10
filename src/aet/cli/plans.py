#!/usr/bin/env python3
"""aet plans — corpus-level commands for the plan directory.

``aet plans lint`` scans every plan under ``docs/plans/`` and reports any file
that still carries a ``status`` frontmatter field. The field left the plan
contract in ADR-055; settled-ness now lives in the ledger and git ancestry.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Optional

import typer

from aet import plans_lint


def _repo_root_from(path: Path) -> Path:
    """Resolve the repository root via git, falling back to layout heuristics."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=path.parent if path.is_file() else path,
            capture_output=True,
            text=True,
            check=True,
        )
        return Path(result.stdout.strip())
    except (OSError, subprocess.CalledProcessError):
        if path.name == "plans" and path.parent.name == "docs":
            return path.parent.parent
        return path


def _fail(message: str) -> int:
    print(f"error: {message}", file=sys.stderr)
    return 1


def cmd_lint(args: argparse.Namespace) -> int:
    if args.plans_dir:
        plans_dir = Path(args.plans_dir).resolve()
    else:
        repo_root = _repo_root_from(Path.cwd())
        plans_dir = repo_root / "docs" / "plans"

    plan_files = sorted(plans_dir.glob("*.md")) if plans_dir.exists() else []
    if not plan_files:
        print("✓ no plans to lint")
        return 0

    violations = plans_lint.lint_corpus(plans_dir)
    if violations:
        for plan, message in violations:
            print(f"{plan.name}: {message}", file=sys.stderr)
        return 1

    print(f"✓ all {len(plan_files)} plans passed lint")
    return 0


app = typer.Typer()


@app.command("lint")
def lint(
    plans_dir: Optional[str] = typer.Option(
        None,
        "--plans-dir",
        help="Plans directory to lint (default: docs/plans under repo root)",
    ),
) -> None:
    """Lint the docs/plans corpus for settled/live misclassification."""
    args = argparse.Namespace(plans_dir=plans_dir)
    rc = cmd_lint(args)
    raise typer.Exit(rc)


if __name__ == "__main__":
    app()
