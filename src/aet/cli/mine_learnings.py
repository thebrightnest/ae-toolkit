#!/usr/bin/env python3
"""mine-learnings — Scan archived telemetry for recurring patterns.

Reads both structured JSONL records and narrative markdown reports so it can
surface patterns the toolkit authors did not explicitly instrument.

Archive layout (as written by src/aet/telemetry.py; the project slug is
<main-worktree-dir>/<worktree-label>):
    ~/.aet/telemetry/{project-dir}/{worktree-label}/{date}/{run-id}/
        ├── last-run.json
        ├── {task-id}.jsonl
        └── ... reports and evidence
"""

from __future__ import annotations

import json
import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import typer

DEFAULT_ARCHIVE_DIR = Path.home() / ".aet" / "telemetry"

# Per-stage anomaly thresholds. Revisit after one week of data.
SLOW_STAGE_THRESHOLD_S = 1800
TOKEN_BURN_THRESHOLD = 5_000_000


@dataclass
class PatternBucket:
    count: int = 0
    examples: list[str] = field(default_factory=list)

    def add(self, example: str) -> None:
        self.count += 1
        if len(self.examples) < 5:
            self.examples.append(example)


# Heuristic signals mined from narrative markdown reports.
# Each pattern is a (category, list-of-keywords) pair. A match is recorded when
# any keyword appears in a sentence.
NARRATIVE_PATTERNS: list[tuple[str, list[str]]] = [
    (
        "dependency_issues",
        [
            "node_modules",
            "api/vendor",
            "vendor",
            "npm install",
            "pip install",
            "composer install",
            "missing dependency",
            "dependency gap",
            "environment issue",
            "worktree dependency",
            "symlink",
            "module not found",
            "cannot find module",
        ],
    ),
    (
        "repeated_loops",
        [
            "retry",
            "re-run",
            "rerun",
            "loop",
            "attempt",
            "attempts",
            "failed and re-ran",
            "prettier failed",
            "format failed",
            "test failed",
            "lint failed",
            "failed 1/",
            "initially failed",
        ],
    ),
    (
        "stage_failures",
        [
            "failed",
            "failure",
            "exit code",
            "halting",
            "halted",
            "error:",
        ],
    ),
    (
        "review_noise",
        [
            "project-level diff",
            "diff noise",
            "noise",
            "AGENTS.md",
            ".gitignore",
            "unrelated changes",
            "not in scope",
            "mock-boundary",
        ],
    ),
]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read and parse a JSONL file, skipping malformed lines."""
    records: list[dict[str, Any]] = []
    if not path.exists():
        return records

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def read_json(path: Path) -> dict[str, Any] | None:
    """Read a single JSON object, returning None on error."""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def read_markdown_reports(run_dir: Path) -> list[tuple[Path, str]]:
    """Read all markdown files under a run archive directory."""
    results: list[tuple[Path, str]] = []
    if not run_dir.is_dir():
        return results
    for path in sorted(run_dir.rglob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        results.append((path, text))
    return results


def sanitize_excerpt(sentence: str, max_length: int = 160) -> str:
    """Collapse whitespace and truncate a sentence for reporting."""
    cleaned = " ".join(sentence.split())
    if len(cleaned) > max_length:
        cleaned = cleaned[: max_length - 1] + "…"
    return cleaned


def mine_narrative(text: str) -> dict[str, PatternBucket]:
    """Mine a markdown report for heuristic patterns."""
    buckets: dict[str, PatternBucket] = {category: PatternBucket() for category, _ in NARRATIVE_PATTERNS}
    lower_text = text.lower()

    for category, keywords in NARRATIVE_PATTERNS:
        for keyword in keywords:
            for match in re.finditer(re.escape(keyword.lower()), lower_text):
                # Extract the surrounding sentence from the original text.
                start = max(0, match.start() - 120)
                end = min(len(text), match.end() + 120)
                snippet = text[start:end]
                sentence = sanitize_excerpt(snippet)
                buckets[category].add(sentence)

    return buckets


def _is_date_dir(path: Path) -> bool:
    """Return True if the directory name parses as a YYYY-MM-DD date."""
    try:
        datetime.strptime(path.name, "%Y-%m-%d")
    except ValueError:
        return False
    return True


def mine_archive(archive_dir: Path) -> dict[str, Any]:
    """Scan the archive and return aggregated pattern counts.

    Walks the writer's layout
    ``{project-dir}/{worktree-label}/{date}/{run-id}/*.jsonl``. Directories at
    the date level whose names do not parse as ``%Y-%m-%d`` are skipped, never
    treated as runs; "runs scanned" counts actual run-id dirs.
    """
    archive_dir = archive_dir.expanduser()
    counts: Counter = Counter()
    examples: dict[str, list[str]] = defaultdict(list)
    files_scanned = 0
    runs_scanned = 0
    reports_scanned = 0
    task_full_suite_counts: Counter = Counter()

    for project_dir in sorted(archive_dir.glob("*")):
        if not project_dir.is_dir():
            continue
        for label_dir in sorted(project_dir.glob("*")):
            if not label_dir.is_dir():
                continue
            for date_dir in sorted(label_dir.glob("*")):
                if not date_dir.is_dir() or not _is_date_dir(date_dir):
                    continue
                for run_dir in sorted(date_dir.glob("*")):
                    if not run_dir.is_dir():
                        continue
                    runs_scanned += 1

                    for task_log in sorted(run_dir.glob("*.jsonl")):
                        records = read_jsonl(task_log)
                        files_scanned += 1

                        for record in records:
                            rtype = record.get("type")
                            if rtype == "environment_issue":
                                counts["dependency_issues"] += 1
                            elif rtype == "stage":
                                if record.get("exit_code", 0) != 0:
                                    counts["stage_failures"] += 1
                                if record.get("stage") == "review":
                                    counts["review_noise"] += 1
                                duration_seconds = record.get("duration_seconds")
                                if duration_seconds is not None and duration_seconds > SLOW_STAGE_THRESHOLD_S:
                                    counts["slow_stage"] += 1
                                token_count = record.get("token_count")
                                if token_count is not None and token_count > TOKEN_BURN_THRESHOLD:
                                    counts["token_burn"] += 1
                            elif rtype == "test_run":
                                scope = record.get("scope")
                                if scope == "full-suite":
                                    counts["full_suite_runs"] += 1
                                    task_full_suite_counts[record.get("task_id", "unknown")] += 1
                                elif scope == "impact":
                                    counts["impact_runs"] += 1
                            elif rtype == "learning_candidate":
                                counts["learning_candidates"] += 1
                                description = record.get("description")
                                if description:
                                    examples["learning_candidates"].append(str(description))

                    last_run = read_json(run_dir / "last-run.json")
                    if last_run:
                        files_scanned += 1

                    # Mine narrative markdown reports for patterns that were never
                    # explicitly instrumented.
                    for _path, text in read_markdown_reports(run_dir):
                        reports_scanned += 1
                        buckets = mine_narrative(text)
                        for category, bucket in buckets.items():
                            counts[category] += bucket.count
                            examples[category].extend(bucket.examples)

    repeated_test_invocations = sum(max(0, count - 1) for count in task_full_suite_counts.values())

    return {
        "dependency_issues": counts.get("dependency_issues", 0),
        "repeated_loops": counts.get("repeated_loops", 0),
        "full_suite_runs": counts.get("full_suite_runs", 0),
        "impact_runs": counts.get("impact_runs", 0),
        "repeated_test_invocations": repeated_test_invocations,
        "stage_failures": counts.get("stage_failures", 0),
        "review_noise": counts.get("review_noise", 0),
        "learning_candidates": counts.get("learning_candidates", 0),
        "slow_stage": counts.get("slow_stage", 0),
        "token_burn": counts.get("token_burn", 0),
        "runs_scanned": runs_scanned,
        "files_scanned": files_scanned,
        "reports_scanned": reports_scanned,
        "examples": {k: v[:5] for k, v in examples.items()},
    }


def format_report(patterns: dict[str, Any]) -> str:
    """Format pattern counts and examples as a ranked markdown report."""
    lines = [
        "# Telemetry Learning Report",
        "",
        f"Runs scanned: {patterns['runs_scanned']}",
        f"Files scanned: {patterns['files_scanned']}",
        f"Reports scanned: {patterns['reports_scanned']}",
        "",
        "## Recurring Patterns",
        "",
        f"- Dependency issues: {patterns['dependency_issues']}",
        f"- Repeated loops: {patterns['repeated_loops']}",
        f"- Full-suite runs: {patterns['full_suite_runs']}",
        f"- Impact-scoped runs: {patterns['impact_runs']}",
        "  (before tap-06, every `make` run counted as full-suite regardless of "
        "how much of the suite it ran; records written since carry the scope "
        "`change_scope` actually resolved, so this split shifts toward "
        "impact over time and is not comparable across that boundary)",
        f"- Repeated test invocations: {patterns['repeated_test_invocations']}",
        f"- Slow stages (> {SLOW_STAGE_THRESHOLD_S}s): {patterns['slow_stage']}",
        f"- Token-burn stages (> {TOKEN_BURN_THRESHOLD:,} tokens): {patterns['token_burn']}",
        f"- Stage failures: {patterns['stage_failures']}",
        f"- Review noise: {patterns['review_noise']}",
        "",
        "## Ranked by Frequency",
        "",
    ]

    ranked = sorted(
        (
            (k, v)
            for k, v in patterns.items()
            if k not in ("runs_scanned", "files_scanned", "reports_scanned", "examples")
        ),
        key=lambda item: item[1],
        reverse=True,
    )
    for name, count in ranked:
        label = name.replace("_", " ").title()
        lines.append(f"1. {label}: {count}")

    examples = patterns.get("examples", {})
    if examples:
        lines.extend(["", "## Example Snippets", ""])
        for category, snippets in examples.items():
            if not snippets:
                continue
            label = category.replace("_", " ").title()
            lines.append(f"### {label}")
            for snippet in snippets:
                lines.append(f"- {snippet}")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def propose_edits(patterns: dict[str, Any]) -> str:
    """Return suggested skill edits based on observed patterns."""
    suggestions: list[str] = []

    if patterns["dependency_issues"]:
        suggestions.append(
            "- aet-setup: add a dependency-warmup step that checks for missing "
            "`node_modules`, `vendor`, and other dependency roots before starting work."
        )
    if patterns["repeated_loops"]:
        suggestions.append(
            "- aet-implement: add a 'run validation after every task' guardrail so "
            "format-fix and test-retry loops are caught early."
        )
    if patterns["full_suite_runs"] or patterns["repeated_test_invocations"]:
        suggestions.append(
            "- aet-qa / aet-implement: prefer impact-scoped tests and run the full "
            "suite only once per task unless core framework files changed."
        )
    if patterns["impact_runs"]:
        suggestions.append(
            "- aet-qa / aet-implement: expand impact-scoped test coverage; "
            "validate that the scope boundary matches the files the task touched."
        )
    if patterns["slow_stage"]:
        suggestions.append(
            "- aet-plan / aet-implement: add a stage-time triage guardrail; "
            "break or hand off stages exceeding the slow-stage threshold."
        )
    if patterns["token_burn"]:
        suggestions.append(
            "- aet-plan / aet-implement: trim prompt context and scope for "
            "stages that exceed the token-burn threshold."
        )
    if patterns["stage_failures"]:
        suggestions.append(
            "- aet-qa: add a stage-failure triage checklist so failed stages are "
            "investigated before the next cycle."
        )
    if patterns["review_noise"]:
        suggestions.append(
            "- aet-review: tighten review scope to the PR base diff and ignore "
            "project-level noise (e.g. `.gitignore`, `AGENTS.md`)."
        )
    if not suggestions:
        suggestions.append(
            "- No recurring patterns detected; no skill edits proposed."
        )

    return "\n".join(["## Proposed Skill Edits", ""] + suggestions) + "\n"


def _run(archive_dir: Path | None, propose: bool) -> int:
    archive_dir = (
        archive_dir
        or Path(os.environ.get("AET_TELEMETRY_ARCHIVE_DIR") or DEFAULT_ARCHIVE_DIR)
    ).expanduser()

    patterns = mine_archive(archive_dir)
    print(format_report(patterns))
    if propose:
        print(propose_edits(patterns))
    return 0


app = typer.Typer(invoke_without_command=True)


@app.callback()
def mine_learnings(
    archive_dir: Path | None = typer.Option(
        None,
        "--archive-dir",
        help="Telemetry archive root.",
    ),
    propose: bool = typer.Option(
        False,
        "--propose",
        help="Print suggested skill edits (never writes files).",
    ),
) -> None:
    """Scan archived telemetry for recurring patterns."""
    rc = _run(archive_dir, propose)
    raise typer.Exit(rc)


def main(argv: list[str] | None = None) -> int:
    try:
        return app(argv or [], standalone_mode=False)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 0


if __name__ == "__main__":
    app()
