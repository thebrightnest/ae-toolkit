#!/usr/bin/env python3
"""aet-retro — Generate a retro from recent AET telemetry.

Distinguishes findings that should improve the current project from findings
that should improve the AET toolkit itself.

Reads:
- ~/.aet/telemetry/<main-worktree-dir>/<worktree-label>/ via mine-learnings --propose
- ~/.aet/telemetry/<main-worktree-dir>/<worktree-label>/{date}/{run-id}/{task-id}.jsonl
  for the current project (per-task structured telemetry, as decided in ADR-012)

The project slug is imported from the installed aet package
(aet.project_id: derive_project_slug) — readers never re-derive it.

Writes a markdown retro to docs/retros/ by default.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

DEFAULT_ARCHIVE_DIR = Path.home() / ".aet" / "telemetry"
DEFAULT_LOOKBACK_DAYS = 7

from aet.project_id import derive_project_slug  # noqa: E402

# Heuristic signals that a finding belongs to the AET toolkit rather than the
# project being built. Keep this list small and project-agnostic.
AET_PATH_PATTERNS = [
    r"\baet-",
    r"\.agents/",
    r"\borchestrator\b",
    r"\bworktree\b",
    r"\bwork-queue\b",
    r"\bmine-learnings\b",
    r"\bskill\b",
    r"\bAGENTS\.md\b",
]


def is_aet_level(text: str) -> bool:
    """Return True if the finding text points at the AET toolkit."""
    return any(re.search(p, text, re.IGNORECASE) for p in AET_PATH_PATTERNS)


def read_jsonl(path: Path) -> list[dict]:
    """Read and parse a JSONL file, skipping malformed lines."""
    records: list[dict] = []
    if not path.exists():
        return records
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return records
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def learning_candidate_record(
    run_id: str,
    task_id: str,
    plan_file: str,
    stage: str,
    pattern_type: str,
    description: str,
    evidence: dict | None = None,
    confidence: float | None = None,
) -> dict:
    """Build a learning-candidate telemetry record for aet-evolve mining."""
    return {
        "type": "learning_candidate",
        "run_id": run_id,
        "task_id": task_id,
        "plan_file": plan_file,
        "stage": stage,
        "pattern_type": pattern_type,
        "description": description,
        "evidence": evidence or {},
        "confidence": confidence,
    }


def archive_task_log_path(
    archive_dir: Path,
    project_slug: str,
    run_id: str,
    task_id: str,
) -> Path:
    """Return the task JSONL path for the current date, creating parents."""
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = archive_dir.expanduser() / project_slug / date / run_id / f"{task_id}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def append_jsonl(path: Path, records: list[dict]) -> None:
    """Append records to a JSONL file, creating it if necessary."""
    if not records:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, sort_keys=True) + "\n")


def emit_learning_candidates(
    archive_dir: Path,
    project_slug: str,
    run_id: str,
    task_id: str,
    plan_file: str,
    project_findings: list[str],
    aet_findings: list[str],
) -> Path:
    """Append one learning_candidate record per retro finding."""
    records: list[dict] = []
    for description in project_findings:
        records.append(
            learning_candidate_record(
                run_id=run_id,
                task_id=task_id,
                plan_file=plan_file,
                stage="retro",
                pattern_type="project_finding",
                description=description,
                evidence={"source": "project_finding"},
                confidence=0.5,
            )
        )
    for description in aet_findings:
        records.append(
            learning_candidate_record(
                run_id=run_id,
                task_id=task_id,
                plan_file=plan_file,
                stage="retro",
                pattern_type="aet_finding",
                description=description,
                evidence={"source": "aet_finding"},
                confidence=0.5,
            )
        )
    log_path = archive_task_log_path(archive_dir, project_slug, run_id, task_id)
    append_jsonl(log_path, records)
    return log_path


def recent_project_records(
    archive_dir: Path,
    project_slug: str,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> list[dict]:
    """Read all telemetry records for the project within the lookback window.

    The archive layout is:
        ~/.aet/telemetry/{project-slug}/{date}/{run-id}/{task-id}.jsonl
    where {project-slug} is the writer's <main-worktree-dir>/<worktree-label>.
    """
    project_dir = archive_dir.expanduser() / project_slug
    if not project_dir.is_dir():
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    records: list[dict] = []

    for date_dir in sorted(project_dir.glob("*")):
        if not date_dir.is_dir():
            continue
        try:
            date = datetime.strptime(date_dir.name, "%Y-%m-%d").replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            continue
        if date < cutoff:
            continue

        for run_dir in sorted(date_dir.glob("*")):
            if not run_dir.is_dir():
                continue
            for task_log in sorted(run_dir.glob("*.jsonl")):
                records.extend(read_jsonl(task_log))

    return records


def run_mine_learnings(archive_dir: Path) -> str:
    """Run mine-learnings --propose against the telemetry archive."""
    # Resolve the sibling package binary directly: the legacy `mine-learnings`
    # PATH name is pruned by `aet install`, so a PATH lookup is no longer safe.
    mine_learnings_bin = Path(__file__).resolve().parent / "mine-learnings.py"
    cmd = [str(mine_learnings_bin), "--propose"]
    env = os.environ.copy()
    env["AET_TELEMETRY_ARCHIVE_DIR"] = str(archive_dir)
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if result.returncode != 0:
        return f"mine-learnings failed (exit {result.returncode}): {result.stderr.strip()}"
    return result.stdout


# Record fields that carry explicit human-readable finding text. Records with
# none of these (queue snapshots, bare stage telemetry, ...) are skipped —
# never rendered as findings.
_FINDING_TEXT_KEYS = ("message", "error", "summary")


def extract_message(record: dict) -> str | None:
    """Extract finding text from a telemetry record, or None if it has none.

    Only typed findings are eligible: ``learning_candidate`` records (which
    carry ``description``) or records with an explicit
    ``message``/``error``/``summary`` field. Bare stage names and dict reprs
    are never returned.
    """
    if not isinstance(record, dict):
        return None
    if record.get("type") == "learning_candidate":
        description = record.get("description")
        return str(description) if description else None
    for key in _FINDING_TEXT_KEYS:
        value = record.get(key)
        if value:
            return str(value)
    return None


def categorize_records(records: list[dict]) -> tuple[list[str], list[str]]:
    """Split telemetry records into AET-level and project-level findings.

    Only records with usable finding text (see ``extract_message``) are
    considered; everything else is skipped, never rendered.
    """
    aet: list[str] = []
    project: list[str] = []
    seen: set[str] = set()
    for record in records:
        msg = extract_message(record)
        if not msg or msg in seen:
            continue
        seen.add(msg)
        if is_aet_level(msg):
            aet.append(msg)
        else:
            project.append(msg)
    return aet, project


def format_section(title: str, items: list[str]) -> list[str]:
    """Format a retro subsection with deduplicated bullets."""
    lines = [f"### {title}", ""]
    if not items:
        lines.append("- No findings.")
    else:
        for item in items[:20]:
            lines.append(f"- {item}")
    lines.append("")
    return lines


def generate_retro(
    project_slug: str,
    project_findings: list[str],
    aet_findings: list[str],
    telemetry_report: str,
) -> str:
    """Render the retro markdown."""
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines = [
        f"# Retro: AET run review ({date})",
        "",
        f"Project: `{project_slug}`",
        "",
        "## Telemetry Summary",
        "",
        "```",
        telemetry_report.rstrip(),
        "```",
        "",
        "## Findings",
        "",
        "Findings are split by where the fix should land:",
        "",
        "- **Project-level** — fix in the current codebase.",
        "- **AET-level** — fix in the AET toolkit (skills, orchestrator, commands, templates).",
        "",
    ]
    lines.extend(format_section("Project-level findings", project_findings))
    lines.extend(format_section("AET-level findings", aet_findings))
    lines.extend(
        [
            "## Action Items",
            "",
            "- [ ] Review project-level findings and create/queue fixes in the current project.",
            "- [ ] Review AET-level findings and update the toolkit via `aet-evolve system-evolve`.",
            "- [ ] Append the highest-impact finding to `.agents/learnings.jsonl`.",
            "",
        ]
    )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate a retro from AET telemetry, split by project-level and AET-level fixes."
    )
    parser.add_argument(
        "--archive-dir",
        type=Path,
        default=DEFAULT_ARCHIVE_DIR,
        help="Telemetry archive root (default: ~/.aet/telemetry).",
    )
    parser.add_argument(
        "--project-slug",
        type=str,
        default=None,
        help="Project slug in the telemetry archive (default: writer-derived <dir>/<label>).",
    )
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=DEFAULT_LOOKBACK_DAYS,
        help="How many days of telemetry to read for the current project (default: 7).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Retro output path (default: docs/retros/YYYY-MM-DD-aet-retro.md).",
    )
    parser.add_argument(
        "--no-mine",
        action="store_true",
        help="Skip mine-learnings and only use the current project's recent telemetry.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    args = build_parser().parse_args(argv)

    if args.project_slug:
        project_slug = args.project_slug
    elif derive_project_slug is None:
        print(
            "error: cannot derive the project slug — the installed 'aet' package "
            "is missing; install the full AE Toolkit or pass --project-slug explicitly.",
            file=sys.stderr,
        )
        return 1
    else:
        project_slug = derive_project_slug()
    local_records = recent_project_records(
        args.archive_dir, project_slug, lookback_days=args.lookback_days
    )
    aet_findings, project_findings = categorize_records(local_records)

    telemetry_report = "Skipped mine-learnings (--no-mine)."
    if not args.no_mine:
        telemetry_report = run_mine_learnings(args.archive_dir)

    if args.output is None:
        output_dir = Path("docs/retros")
        output_dir.mkdir(parents=True, exist_ok=True)
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        args.output = output_dir / f"{date}-aet-retro.md"

    retro = generate_retro(
        project_slug, project_findings, aet_findings, telemetry_report
    )
    args.output.write_text(retro, encoding="utf-8")

    run_id = os.environ.get("AET_RUN_ID") or uuid.uuid4().hex
    task_id = os.environ.get("AET_TASK_ID") or "aet-retro"
    plan_file = os.environ.get("AET_PLAN_FILE") or "aet-retro"
    emit_learning_candidates(
        archive_dir=args.archive_dir,
        project_slug=project_slug,
        run_id=run_id,
        task_id=task_id,
        plan_file=plan_file,
        project_findings=project_findings,
        aet_findings=aet_findings,
    )

    print(f"Wrote retro to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
