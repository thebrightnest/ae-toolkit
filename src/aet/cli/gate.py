"""aet-work gate — fail-closed verdict writer and review board renderer.

``gate submit`` is the sole sanctioned writer of gate evidence verdicts
(G1). It schema-validates the payload against the stage schema, resolves
the destination through the canonical ``resolve_verdict_path`` precedence
(ADR-023), and delegates the write to ``evidence.write_verdict``. Every
failure path prints a named error to stderr and exits 1 — never a silent
or partial write.

``gate review`` prints a human-readable backlog review by scanning
``docs/plans/*.md`` and grouping plans into columns from the loaded
workflow (entry → approved, terminal skill-less → queued, everything
else → in-progress), with legacy footer fallbacks when no workflow is
available.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import click
import typer

_SCRIPT_DIR = Path(__file__).resolve().parent
from aet import evidence  # noqa: E402
from aet.plan_parser import stage_from_plan, title_from_plan  # noqa: E402
from aet.workflow import Workflow, WorkflowError, load_workflow  # noqa: E402

# Footer values that are not workflow stage names (queue states and
# historical stage spellings) keep fixed board columns. Also the fallback
# when no workflow can be loaded.
LEGACY_BUCKETS: dict[str, str] = {
    "plan-approved": "approved",
    "approved": "approved",
    "synced": "queued",
    "queued": "queued",
    "tdd-complete": "in-progress",
    "implemented": "in-progress",
    "qa-complete": "in-progress",
    "reviewed": "in-progress",
    "secure": "in-progress",
    "synced-docs": "in-progress",
    "in-progress": "in-progress",
    "awaiting_merge": "awaiting-merge",
    "merged": "closed",
    "abandoned": "closed",
}


def _fail(message: str) -> int:
    print(f"error: {message}", file=sys.stderr)
    return 1


def category_for_stage(stage: str | None, workflow: Workflow | None = None) -> str:
    """Return the review category for a footer stage value.

    When a workflow is loaded, stage names derive their column positionally:
    entry stage → approved, terminal skill-less stage → queued, every other
    stage (including unknown vocabularies from variant workflows) →
    in-progress. Non-stage footer values and the no-workflow case use
    ``LEGACY_BUCKETS``, with in-progress as the catch-all.
    """
    if not stage:
        return "approved"
    if workflow is not None:
        if stage == workflow.entry_stage:
            return "approved"
        terminal = workflow.stages[-1]
        if stage == terminal.name and not terminal.skills:
            return "queued"
        if stage in workflow.stage_map:
            return "in-progress"
    return LEGACY_BUCKETS.get(stage, "in-progress")


def run_review(plans_dir: Path) -> int:
    """Print a human-readable backlog review grouped by pipeline stage."""
    if not plans_dir.is_dir():
        print(f"❌ Plans directory not found: {plans_dir}", file=sys.stderr)
        return 1

    plan_files = sorted(plans_dir.glob("*.md"))

    # Best-effort: a board renderer stays useful even when the workflow file
    # is unreadable — LEGACY_BUCKETS renders the same board for the software
    # workflow either way.
    workflow = None
    try:
        workflow = load_workflow(Path.cwd())
    except WorkflowError:
        pass

    categories: dict[str, list[tuple[str, str]]] = {
        "approved": [],
        "queued": [],
        "in-progress": [],
        "awaiting-merge": [],
        "closed": [],
    }

    for pf in plan_files:
        stage = stage_from_plan(pf)
        category = category_for_stage(stage, workflow)
        categories[category].append((pf.stem, title_from_plan(pf)))

    for category in categories:
        print(f"\n{category.replace('-', ' ').title()} ({len(categories[category])}):")
        if categories[category]:
            for task_id, title in categories[category]:
                print(f"  - {task_id}: {title}")
        else:
            print("  None.")

    return 0


def _submit(args: argparse.Namespace) -> int:
    stage = args.stage
    if stage not in evidence.SCHEMAS:
        known = ", ".join(sorted(evidence.SCHEMAS))
        return _fail(f"unknown stage {stage!r} (expected one of: {known})")

    evidence_file = Path(args.evidence)
    try:
        raw = evidence_file.read_text(encoding="utf-8")
    except FileNotFoundError:
        return _fail(f"evidence file not found: {evidence_file}")
    except OSError as exc:
        return _fail(f"cannot read evidence file {evidence_file}: {exc}")

    try:
        record = json.loads(raw)
    except json.JSONDecodeError as exc:
        return _fail(f"evidence file is not valid JSON ({evidence_file}): {exc}")

    if not isinstance(record, dict):
        return _fail(f"evidence payload must be a JSON object ({evidence_file})")

    # Stamp tree_hash before validating so the skill writer contract (which
    # does not require tree_hash) stays unchanged — ADR-025.
    if "tree_hash" not in record:
        root = evidence.telemetry.resolve_repo_root()
        record = {**record, "tree_hash": evidence.verifier.working_tree_hash(str(root))}

    try:
        evidence.validate_verdict(record, stage)
    except (evidence.VerdictValidationError, evidence.VerdictValueError) as exc:
        return _fail(f"invalid {stage!r} verdict payload: {exc}")

    if record["verdict"] != args.verdict:
        return _fail(
            f"--verdict {args.verdict!r} does not match payload verdict "
            f"{record['verdict']!r}"
        )

    task_id = os.environ.get("AET_TASK_ID") or record["task_id"]
    try:
        dest = evidence.resolve_verdict_path(task_id=task_id, kind=stage)
        written = evidence.write_verdict(task_id, stage, record, path=dest)
    except OSError as exc:
        return _fail(f"cannot write verdict: {exc}")

    print(f"✓ {stage} verdict written: {written}")
    return 0


app = typer.Typer()


@app.command("submit")
def submit(
    stage: str = typer.Option(..., "--stage", help="Verdict stage: qa, review, cso, or sync-docs"),
    verdict: str = typer.Option(..., "--verdict", help="Declared verdict; must match the payload's verdict field"),
    evidence: str = typer.Option(..., "--evidence", help="Path to the verdict JSON payload file"),
) -> None:
    """Validate and write a stage verdict."""
    args = argparse.Namespace(stage=stage, verdict=verdict, evidence=evidence)
    rc = _submit(args)
    raise typer.Exit(rc)


@app.command("review")
def review(
    plans_dir: str = typer.Option(
        "docs/plans", "--plans-dir", help="Directory containing atomic plan markdown files"
    ),
) -> None:
    """Print a human-readable backlog review grouped by pipeline stage."""
    rc = run_review(Path(plans_dir))
    raise typer.Exit(rc)


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    try:
        return app(argv, standalone_mode=False)
    except (
        click.exceptions.ClickException,
        typer._click.exceptions.ClickException,
    ) as exc:
        exc.show()
        return exc.exit_code
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 0


if __name__ == "__main__":
    app()
