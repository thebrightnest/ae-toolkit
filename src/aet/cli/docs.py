#!/usr/bin/env python3
"""aet docs — documentation governance commands."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Optional

import typer

from aet import docs_lint


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
        if path.name == ".agents" and path.parent.is_dir():
            return path.parent
        return path


def _fail(message: str) -> int:
    print(f"error: {message}", file=sys.stderr)
    return 1


def cmd_lint(args: argparse.Namespace) -> int:
    if args.repo_root:
        repo_root = Path(args.repo_root).resolve()
    else:
        repo_root = _repo_root_from(Path.cwd())

    if args.rules:
        rules_file = Path(args.rules).resolve()
    else:
        rules_file = repo_root / ".agents" / "doc-rules.yaml"

    if not rules_file.exists():
        return _fail(f"rules file not found: {rules_file}")

    violations = docs_lint.lint_docs(rules_file, repo_root)
    if violations:
        for path, message in violations:
            print(f"{path}: {message}", file=sys.stderr)
        return 1

    print("✓ docs lint passed")
    return 0


app = typer.Typer()


@app.command("lint")
def lint(
    rules: Optional[str] = typer.Option(
        None,
        "--rules",
        help="Rules file (default: .agents/doc-rules.yaml under repo root)",
    ),
    repo_root: Optional[str] = typer.Option(
        None,
        "--repo-root",
        help="Repository root (default: git root or current directory)",
    ),
) -> None:
    """Lint documentation against declarative rules."""
    args = argparse.Namespace(rules=rules, repo_root=repo_root)
    rc = cmd_lint(args)
    raise typer.Exit(rc)


if __name__ == "__main__":
    app()
