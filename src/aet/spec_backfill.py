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

    Decoding is pinned to UTF-8 rather than left to the process locale: plans
    carry em-dashes and status glyphs, and under a C/POSIX locale (a bare CI
    container, cron) locale decoding raises and takes the whole migration down
    with it. ``errors="replace"`` mirrors the tolerance of the on-disk path.
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "show", f"{rev}:{rel_path}"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def rev_is_available(rev: str, repo_root: str | Path) -> bool:
    """Return True when *rev* resolves to a commit in this clone.

    A revision absent from the clone (a typo, or a shallow fetch that does not
    reach it) makes every lookup miss, which is otherwise indistinguishable
    from each individual plan being absent from a revision that does exist.
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--verify", "-q", f"{rev}^{{commit}}"],
            capture_output=True,
            check=False,
        )
    except OSError:
        return False
    return result.returncode == 0


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
    reported rather than silently passed over.  ``rev_available`` records
    whether the source revision resolved at all, so a bad ``--rev`` is not
    reported as a corpus in which every plan happens to be missing.
    """

    filled: list[str] = field(default_factory=list)
    already: list[str] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)
    rev_available: bool = True


def _plan_text_at_path(path: Path) -> str | None:
    """Return the text of *path* when it exists, or None."""
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8", errors="ignore")


def backfill_specs(
    queue: list[dict[str, Any]], *, rev: str, repo_root: str | Path
) -> BackfillResult:
    """Fill in the missing ``spec`` on every record in *queue*, in place.

    Each record without a spec is resolved from the plan at *rev* first, then
    from the working tree — a plan added after *rev* exists only on disk — and
    finally from ``docs/plans/archive/``, which is the surviving source for
    plans removed before R-19.  A record whose plan is in none of those places
    is reported as skipped and the migration continues.

    An unresolvable *rev* is not fatal — the working tree or archive may still
    hold every plan — but it is recorded, so the caller can say why the
    revision produced nothing instead of blaming each record in turn.
    """
    result = BackfillResult()
    root = Path(repo_root)
    result.rev_available = rev_is_available(rev, root)
    source = rev if result.rev_available else f"{rev} (not in this clone)"

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
            text = _plan_text_at_path(on_disk)
        if text is None:
            archive = root / "docs" / "plans" / "archive" / Path(rel_path).name
            text = _plan_text_at_path(archive)

        if text is None:
            result.skipped.append(
                (
                    task_id,
                    f"no plan at {source}, on disk, or in archive: {rel_path}",
                )
            )
            continue

        task["spec"] = plan_parser.extract_plan_spec_from_text(
            text, Path(rel_path).stem
        )
        result.filled.append(task_id)

    return result
