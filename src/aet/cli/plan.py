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
from aet.backends.factory import (  # noqa: E402
    QueueOutsideRepositoryError,
    create_backend,
)


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
        if start.name in ("active", "archive") and start.parent.name == "plans" and start.parent.parent.name == "docs":
            return start.parent.parent.parent
        if start.name == "plans" and start.parent.name == "docs":
            return start.parent.parent
        return start.parent


def _expand_plan_args(plans: list[str]) -> list[Path]:
    """Resolve plan arguments, expanding a directory to its ``*.md`` children.

    ``docs/plans/*.md`` and ``docs/plans/active/*.md`` are the canonical locations.
    If a directory is named, its active and root markdown children are included
    (excluding archive). Order follows the arguments; duplicates collapse.
    """
    paths: list[Path] = []
    for raw in plans:
        path = Path(raw).resolve()
        if path.is_dir():
            active_dir = path / "active"
            active_candidates = sorted(active_dir.glob("*.md")) if active_dir.is_dir() else []
            root_candidates = [p for p in sorted(path.glob("*.md")) if p.parent.name != "archive"]
            candidates = sorted(set(active_candidates + root_candidates))
        else:
            candidates = [path]
        for candidate in candidates:
            if candidate not in paths:
                paths.append(candidate)
    return paths


def _record_coverage(repo_root: Path) -> plan_validate.RecordCoverage:
    """R-trace coverage contributed by the task record, or an empty result.

    A settled sibling has left ``docs/plans/`` but its record still carries the
    requirements it delivered (ADR-061). Reading it is what stops a plan being
    asked to trace requirements another plan already covered.
    """
    try:
        backend = create_backend(
            config_path=str(repo_root / ".agents" / "aet-config.json"),
            queue_file=str(repo_root / ".agents" / "aet-queue"),
            history_file=str(repo_root / ".agents" / "work-history.jsonl"),
        )
    except (QueueOutsideRepositoryError, OSError) as exc:
        # No store here — validate the authoring corpus alone and say so. A
        # config error is not caught: it names a remedy and the CLI boundary
        # already prints it without a traceback.
        return plan_validate.RecordCoverage({}, (), f"{type(exc).__name__}: {exc}")
    try:
        return plan_validate.coverage_from_backend(backend, repo_root)
    finally:
        backend.close()


def _scope_note(repo_root: Path, record: plan_validate.RecordCoverage) -> str:
    """Name which r-trace sources the run could see.

    A requirement is covered when any plan sharing the PRD traces it, and the
    plans that already delivered one have usually left the authoring corpus for
    the record. A run missing either source reports fewer uncovered
    requirements than one with both, and the two results are identical in form
    unless the output says which ran.
    """
    corpus = plan_validate.corpus_dir(repo_root)
    if corpus is None:
        sources = ["each plan's own traces"]
    else:
        try:
            where = corpus.relative_to(repo_root)
        except ValueError:
            where = corpus
        sources = [f"the plan set in {where}/"]
    if record.source_error:
        sources.append(f"no task record ({record.source_error})")
    else:
        sources.append(f"{len(record.coverage)} PRD(s) from the task record")
    return "r-trace coverage judged against " + " and ".join(sources)


def _report_unreadable(record: plan_validate.RecordCoverage) -> None:
    """Name the records whose coverage could not be counted (ADR-059).

    An uncovered requirement caused by an unreadable record is not the plan's
    fault, and the two are indistinguishable in the findings.
    """
    for task_id in record.unreadable:
        print(
            f"note: task record {task_id} carries no readable spec; "
            "its requirement coverage is not counted",
            file=sys.stderr,
        )


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
        active_dir = plans_dir / "active"
        active_plans = sorted(active_dir.glob("*.md")) if active_dir.is_dir() else []
        root_plans = sorted(plans_dir.glob("*.md")) if plans_dir.is_dir() else []
        plan_paths = sorted(set(active_plans + root_plans))

    live_paths = [p for p in plan_paths if not plan_parser.is_settled_plan(p)]

    if not live_paths:
        print("✓ no live plans to validate")
        return 0

    missing = [p for p in live_paths if not p.exists()]
    if missing:
        return _fail(f"plan file not found: {missing[0]}")

    record = _record_coverage(repo_root)
    findings = plan_validate.validate(
        live_paths, repo_root=repo_root, extra_coverage=record.coverage
    )
    plan_texts = {p: p.read_text(errors="ignore") for p in live_paths}
    findings = plan_validate.apply_acks(findings, plan_texts)

    unacked = [f for f in findings if not f.acked]

    for finding in findings:
        if finding.acked:
            print(
                f"{finding.plan.name}: {finding.check_id}: "
                f"acked — {finding.ack_reason}"
            )

    scope = _scope_note(repo_root, record)

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
        _report_unreadable(record)
        return 1

    noun = "plan" if len(live_paths) == 1 else "plans"
    print(f"✓ {len(live_paths)} {noun} passed validation — {scope}")
    _report_unreadable(record)
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
