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
    """Resolve the repository root via git, falling back to layout heuristics.

    ``path`` is either a plan file or a directory; git runs in the nearest
    directory either way. Resolving a directory against its own parent is what
    made the no-argument invocation resolve the repository's parent and find
    no plans.
    """
    start = path if path.is_dir() else path.parent
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=start,
            capture_output=True,
            text=True,
            check=True,
        )
        return Path(result.stdout.strip())
    except (OSError, subprocess.CalledProcessError):
        if start.name == "plans" and start.parent.name == "docs":
            return start.parent.parent
        return start.parent


def _expand_plan_args(plans: list[str]) -> list[Path]:
    """Resolve plan arguments, expanding a directory to its ``*.md`` children.

    ``docs/plans/*.md`` is the documented default, so naming the directory is
    the first shape a caller tries. Unexpanded it reaches ``read_text`` as a
    directory. Order follows the arguments; duplicates collapse.
    """
    paths: list[Path] = []
    for raw in plans:
        path = Path(raw).resolve()
        candidates = sorted(path.glob("*.md")) if path.is_dir() else [path]
        for candidate in candidates:
            if candidate not in paths:
                paths.append(candidate)
    return paths


def _scope_note(repo_root: Path) -> str:
    """Name which r-trace mode ran, per the plan set the run could see.

    A requirement is covered when any plan sharing the PRD traces it, so a run
    that cannot locate the plan set reports fewer uncovered requirements than
    one that can. The two results are otherwise identical in form.
    """
    corpus = plan_validate.corpus_dir(repo_root)
    if corpus is None:
        return "r-trace coverage judged against each plan's own traces only"
    try:
        where = corpus.relative_to(repo_root)
    except ValueError:
        where = corpus
    return f"r-trace coverage judged against the plan set in {where}/"


def _fail(message: str) -> int:
    print(f"error: {message}", file=sys.stderr)
    return 1


def cmd_validate(args: argparse.Namespace) -> int:
    if args.plans:
        plan_paths = _expand_plan_args(args.plans)
        repo_root = _repo_root_from(Path(args.plans[0]).resolve())
    else:
        repo_root = _repo_root_from(Path.cwd())
        plans_dir = repo_root / "docs" / "plans"
        plan_paths = sorted(plans_dir.glob("*.md")) if plans_dir.is_dir() else []

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

    scope = _scope_note(repo_root)

    if unacked:
        for finding in unacked:
            print(
                f"{finding.plan.name}: {finding.check_id}: {finding.message}",
                file=sys.stderr,
            )
        affected = len({f.plan for f in unacked})
        print(
            f"{len(unacked)} finding(s) across {affected} of "
            f"{len(live_paths)} plan(s) — {scope}",
            file=sys.stderr,
        )
        print(
            "Override a check that does not apply by adding a line to the plan:",
            file=sys.stderr,
        )
        print("  ⚠️ VALIDATE ACK: <check-id> — <reason>", file=sys.stderr)
        return 1

    noun = "plan" if len(live_paths) == 1 else "plans"
    print(f"✓ {len(live_paths)} {noun} passed validation — {scope}")
    return 0


app = typer.Typer()


@app.command("validate")
def validate(
    plans: Optional[list[str]] = typer.Argument(
        None,
        help="Plan files or directories to validate (default: docs/plans/*.md)",
    ),
) -> None:
    """Validate plan files for intake quality."""
    if plans is None:
        plans = []
    args = argparse.Namespace(plans=plans)
    rc = cmd_validate(args)
    raise typer.Exit(rc)


if __name__ == "__main__":
    app()
