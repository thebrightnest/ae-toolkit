"""Compute delivered diff size for a settled task.

The measurement is anchored on the task's recorded ``merge_commit`` and uses the
first-parent range ``<merge_commit>^1..<merge_commit>``. This is exact for both
squash and regular merges and needs no trunk ref or branch resolution.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

# Paths excluded from the headline diff. These are the planning-artifact
# directories the size bands are defined against.
PLANNING_ARTIFACT_PATHS: tuple[str, ...] = (
    "docs/",
    ".agents/",
    "content/",
    "reports/",
)

# Calibrated floor diff threshold in headline lines. Measured on this repo's
# settled S tasks via ``delivered_size``, the smallest non-zero delivered
# headline diff was 45 lines (median 262, range 0-465). The threshold is
# rounded to the nearest 10 from that observed minimum; plans expected to
# deliver at or below this level should be scrutinized as floor candidates.
# See ``docs/CONVENTIONS.md`` "Task Size Guardrails" for the full model.
FLOOR_DIFF_THRESHOLD = 50


def _run_git(
    *args: str, cwd: str | Path | None = None
) -> tuple[int, str, str]:
    """Run a git command in list form and return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return (127, "", "git not found")
    return (result.returncode, result.stdout, result.stderr)


def delivered_size(
    repo_root: str | Path, merge_commit: str | None
) -> dict[str, Any]:
    """Return diff statistics for the first-parent range of ``merge_commit``.

    The returned dict has keys:
      - ``headline``: total added + removed lines excluding planning artifacts
      - ``total``: total added + removed lines
      - ``status``: ``"ok"`` on success, ``"failed"`` when the diff cannot be
        computed
      - ``reason``: human-readable explanation when ``status`` is ``"failed"``,
        otherwise ``None``

    A missing ``merge_commit``, an invalid object, a root commit, or any
    non-zero git exit is recorded as a failure rather than raised, so telemetry
    collection can never block a task from settling.
    """
    if not merge_commit:
        return {
            "headline": None,
            "total": None,
            "status": "failed",
            "reason": "no merge_commit recorded",
        }

    repo_root = Path(repo_root)

    # Verify the commit exists and has a first parent.
    rc, _, err = _run_git("rev-parse", f"{merge_commit}^1", cwd=repo_root)
    if rc != 0:
        return {
            "headline": None,
            "total": None,
            "status": "failed",
            "reason": f"no first parent: {err.strip()}",
        }

    rc, out, err = _run_git(
        "diff", "--numstat", f"{merge_commit}^1..{merge_commit}", cwd=repo_root
    )
    if rc != 0:
        return {
            "headline": None,
            "total": None,
            "status": "failed",
            "reason": f"git diff failed: {err.strip()}",
        }

    total_added = 0
    total_removed = 0
    headline_added = 0
    headline_removed = 0

    for line in out.splitlines():
        parts = line.split(maxsplit=2)
        if len(parts) != 3:
            continue
        added_s, removed_s, path = parts
        try:
            added = int(added_s) if added_s != "-" else 0
            removed = int(removed_s) if removed_s != "-" else 0
        except ValueError:
            continue

        total_added += added
        total_removed += removed

        if not any(path.startswith(prefix) for prefix in PLANNING_ARTIFACT_PATHS):
            headline_added += added
            headline_removed += removed

    return {
        "headline": headline_added + headline_removed,
        "total": total_added + total_removed,
        "status": "ok",
        "reason": None,
    }
