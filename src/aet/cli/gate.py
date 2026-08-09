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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import click
import typer

from aet import evidence, telemetry  # noqa: E402
from aet.ledger import Ledger  # noqa: E402
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

# Map gate kinds to the stage name written in verdict records and plan footers.
KIND_TO_STAGE: dict[str, str] = {
    "qa": "qa-complete",
    "review": "reviewed",
    "cso": "secure",
    "sync-docs": "synced",
}

KIND_TO_SKILL: dict[str, str] = {
    "qa": "aet-qa",
    "review": "aet-review",
    "cso": "aet-cso",
    "sync-docs": "aet-sync-docs",
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


def _parse_pytest_report(path: Path) -> dict[str, Any]:
    """Extract test counts and command from a pytest JSON report.

    Supports the ``pytest-json-report`` shape (``summary.*``) and a minimal
    flat schema used by the builder (``tests_total/passed/failed`` and
    ``test_command``).
    """
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("pytest report must be a JSON object")

    summary = data.get("summary") if isinstance(data.get("summary"), dict) else data

    total = summary.get("total", summary.get("tests_total", 0))
    passed = summary.get("passed", summary.get("tests_passed", 0))
    failed = summary.get("failed", summary.get("tests_failed", 0))

    command = data.get("test_command")
    if not command:
        command = data.get("command", "pytest")

    return {
        "tests_total": int(total or 0),
        "tests_passed": int(passed or 0),
        "tests_failed": int(failed or 0),
        "test_command": str(command),
    }


def _load_divergences(values: list[str]) -> list[str]:
    """Turn divergence options into a list of strings.

    Values that name an existing file have their contents read; inline
    strings are kept as-is.
    """
    items: list[str] = []
    for value in values:
        path = Path(value)
        if path.is_file():
            items.append(path.read_text(encoding="utf-8").strip())
        else:
            items.append(value)
    return items


def _build_payload(
    *,
    stage: str,
    verdict: str,
    summary: str | None,
    from_pytest: Path | None,
    divergences: list[str],
    task_id: str,
    test_command: str | None,
) -> dict[str, Any]:
    """Construct a verdict record from CLI builder options."""
    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    record: dict[str, Any] = {
        "task_id": task_id,
        "stage": KIND_TO_STAGE[stage],
        "skill": KIND_TO_SKILL[stage],
        "verdict": verdict,
        "summary": summary or "",
        "generated_at": generated_at,
    }

    if stage == "qa":
        if from_pytest is None:
            raise ValueError("--from-pytest is required for qa verdicts")
        report = _parse_pytest_report(from_pytest)
        if test_command:
            report["test_command"] = test_command
        record.update(report)
    elif stage in ("review", "cso"):
        record["findings"] = []
    elif stage == "sync-docs":
        record["divergences"] = _load_divergences(divergences)

    return record


def _submit(args: argparse.Namespace) -> int:
    stage = args.stage
    if stage not in evidence.SCHEMAS:
        known = ", ".join(sorted(evidence.SCHEMAS))
        return _fail(f"unknown stage {stage!r} (expected one of: {known})")

    # Builder mode: construct the payload from CLI options when --evidence is
    # omitted. This is the sanctioned replacement for hand-rolled JSON.
    if getattr(args, "evidence", None) is None:
        task_id = os.environ.get("AET_TASK_ID")
        if not task_id:
            return _fail("builder mode requires AET_TASK_ID (or pass --evidence)")

        try:
            record = _build_payload(
                stage=stage,
                verdict=args.verdict,
                summary=getattr(args, "summary", None),
                from_pytest=Path(args.from_pytest) if args.from_pytest else None,
                divergences=list(args.divergence) if args.divergence else [],
                task_id=task_id,
                test_command=getattr(args, "test_command", None),
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            return _fail(f"cannot build {stage!r} verdict: {exc}")
    else:
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
        root = telemetry.resolve_repo_root()
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

    # Record the verdict event in the content-addressed ledger.
    try:
        repo_root = telemetry.resolve_repo_root()
        ledger_path = repo_root / ".agents" / "ledger.jsonl"
        ledger = Ledger(ledger_path)
        ledger.write_event(
            source="aet-gate",
            task=task_id,
            kind="verdict",
            ref=str(written),
            ref_kind="evidence-path",
            payload={"stage": stage, "verdict": record["verdict"]},
        )
    except Exception as exc:
        # A ledger write failure must not roll back the verdict; it is
        # advisory provenance. Surface the error but keep the gate exit clean.
        print(f"warning: ledger verdict event failed: {exc}", file=sys.stderr)

    print(f"✓ {stage} verdict written: {written}")
    return 0


app = typer.Typer()


@app.command("submit")
def submit(
    stage: str = typer.Option(
        ..., "--stage", help="Verdict stage: qa, review, cso, or sync-docs"
    ),
    verdict: str = typer.Option(
        ..., "--verdict", help="Declared verdict; must match the payload's verdict field"
    ),
    evidence_path: str | None = typer.Option(
        None, "--evidence", help="Path to the verdict JSON payload file"
    ),
    from_pytest: str | None = typer.Option(
        None, "--from-pytest", help="Path to a pytest JSON report (qa builder mode)"
    ),
    summary: str | None = typer.Option(
        None, "--summary", help="One-line verdict summary"
    ),
    divergence: list[str] = typer.Option(
        [],
        "--divergence",
        help="Divergence item or file path (sync-docs builder mode; repeatable)",
    ),
    test_command: str | None = typer.Option(
        None, "--test-command", help="Override the test command recorded in qa verdicts"
    ),
) -> None:
    """Validate and write a stage verdict.

    When ``--evidence`` is omitted the command builds the verdict payload
    from the supplied options. In that mode ``AET_TASK_ID`` must be set.
    """
    args = argparse.Namespace(
        stage=stage,
        verdict=verdict,
        evidence=evidence_path,
        from_pytest=from_pytest,
        summary=summary,
        divergence=divergence,
        test_command=test_command,
    )
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
