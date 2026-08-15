"""Backfill the portable plan spec into task records that predate R-19.

R-19 moved a task's spec out of ``docs/plans/<id>.md`` and into the task
record so a task planned on one machine is executable on another.  Records
created before that change carry only ``plan_file`` — a path — and the plan
files were deleted in the same commit that introduced the spec.  This module
recovers each record's plan from the git revision that still has the file and
writes it into the record.

Git is the source rather than a machine-local copy so the migration is
reproducible in any clone.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aet import plan_parser

# The commit that introduced the spec deleted the plan files in the same
# breath, so the last revision that still has them is its parent. This is the
# default source for the migration; ``--rev`` overrides it.
DEFAULT_SOURCE_REV = "b95538dd~1"


def plan_text_at_rev(rev: str, rel_path: str, repo_root: str | Path) -> str | None:
    """Return the text of ``rel_path`` at *rev*, or None when it is not there.

    A missing blob is an ordinary outcome — a plan added after *rev* is not in
    it — so it returns None rather than raising.
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "show", f"{rev}:{rel_path}"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def _carries_spec(task: dict[str, Any]) -> bool:
    """Return True when *task* carries a usable portable spec.

    The check is for a mapping, not mere presence: a leftover string would pass
    a truthiness test and then fail at render time.
    """
    return isinstance(task.get("spec"), dict)


def records_missing_spec(queue: list[dict[str, Any]]) -> list[str]:
    """Return the ids of records that carry no usable portable spec.

    A record without one names a plan file that may not exist on this machine,
    which is the failure R-19 exists to remove.
    """
    return [task.get("id") or "<unknown>" for task in queue if not _carries_spec(task)]


@dataclass
class BackfillResult:
    """What the migration did, per task id.

    ``skipped`` carries a reason per task so a record whose plan is nowhere is
    reported rather than silently passed over.
    """

    filled: list[str] = field(default_factory=list)
    already: list[str] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)


def backfill_specs(
    queue: list[dict[str, Any]], *, rev: str, repo_root: str | Path
) -> BackfillResult:
    """Fill in the missing ``spec`` on every record in *queue*, in place.

    Each record without a spec is resolved from the plan at *rev* first, then
    from the working tree — a plan added after *rev* exists only on disk.  A
    record whose plan is in neither place is reported as skipped and the
    migration continues.
    """
    result = BackfillResult()
    root = Path(repo_root)

    for task in queue:
        task_id = task.get("id") or "<unknown>"
        if _carries_spec(task):
            result.already.append(task_id)
            continue

        rel_path = task.get("plan_file") or f"docs/plans/{task_id}.md"
        text = plan_text_at_rev(rev, rel_path, root)
        if text is None:
            on_disk = Path(rel_path)
            if not on_disk.is_absolute():
                on_disk = root / rel_path
            if on_disk.exists():
                text = on_disk.read_text(encoding="utf-8", errors="ignore")

        if text is None:
            result.skipped.append((task_id, f"no plan at {rev} or on disk: {rel_path}"))
            continue

        task["spec"] = plan_parser.extract_plan_spec_from_text(text, Path(rel_path).stem)
        result.filled.append(task_id)

    return result
