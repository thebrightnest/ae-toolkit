#!/usr/bin/env python3
"""aet plans — corpus-level commands for the plan directory.

``aet plans lint`` classifies every plan under ``docs/plans/`` as settled or
live and reports any file whose classification disagrees with its committed
frontmatter ``status`` (R-5).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="plans",
        description="Corpus-level commands for the plan directory.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    lint = sub.add_parser(
        "lint",
        help="Lint the docs/plans corpus for settled/live misclassification.",
    )
    lint.add_argument(
        "--plans-dir",
        default=None,
        help="Plans directory to lint (default: docs/plans under repo root)",
    )
    return parser


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

    print(f"✓ all {len(plan_files)} plans classified correctly")
    return 0


def main(argv: list[str] | None = None):
    args = build_parser().parse_args(argv)
    if args.command == "lint":
        return cmd_lint(args)
    return _fail(f"unknown command: {args.command}")


if __name__ == "__main__":
    sys.exit(main())
