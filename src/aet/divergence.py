"""Mechanical divergence computation at task closure (R-9, R-10, R-11).

Derives the set of files changed in a task's merge commit range
(``<merge_commit>^1..<merge_commit>``) that were not declared in the task's
spec under ``Files to Modify``, plus any recoverable test-count delta.

Adopts the ``delivered_size`` fail-soft contract: any missing input, missing
commit, or non-zero git exit is recorded as ``status: "failed"`` with a reason,
and never raises, ensuring divergence recording never blocks task closure.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any


def _run_git(*args: str, cwd: str | Path | None = None) -> tuple[int, str, str]:
    """Run a git command and return (returncode, stdout, stderr)."""
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except Exception as e:
        return 1, "", str(e)


def extract_declared_files(spec_or_body: dict[str, Any] | str | Path | None) -> set[str]:
    """Extract file paths declared under ``## Files to Modify``.

    Strips list markers, checkboxes, markdown backticks, and ``(new)``
    annotations. Directory entries (trailing ``/``) and empty sections are ignored.
    """
    if spec_or_body is None:
        return set()
    if isinstance(spec_or_body, Path):
        text = spec_or_body.read_text(errors="ignore")
    elif isinstance(spec_or_body, dict):
        text = spec_or_body.get("body", "")
    else:
        text = str(spec_or_body)

    pattern = (
        r"(?m)^##\s+"
        + re.escape("Files to Modify")
        + r"\s*\n(.*?)"
        + r"(?=\n## |\n---|\Z)"
    )
    match = re.search(pattern, text, re.DOTALL)
    section = match.group(1) if match else ""

    files: set[str] = set()
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if not re.match(r"^[\-\*\d]+\.?\s+", stripped):
            continue
        item = re.sub(r"^[\-\*\d]+\.?\s+", "", stripped)
        item = re.sub(r"^\[\s*[xX ]\s*\]\s*", "", item)
        item = item.strip()
        item = re.sub(r"`([^`]+)`", r"\1", item)
        item = re.sub(r"\s*\(new\)\s*$", "", item, flags=re.IGNORECASE)
        item = item.strip("- ")
        if item.endswith("/"):
            continue
        if item:
            files.add(item)
    return files


def compute_divergence(
    repo_root: str | Path,
    merge_commit: str | None,
    spec: dict[str, Any] | None = None,
    *,
    task: dict[str, Any] | None = None,
    test_delta: int | None = None,
) -> dict[str, Any]:
    """Compute mechanical divergence for a task at terminal closure.

    Compares the changed files in ``<merge_commit>^1..<merge_commit>`` against
    the files declared in the task's spec (``## Files to Modify``), and captures
    any test-count delta when recoverable.

    Follows the fail-soft contract: returns ``status: "failed"`` with a reason on
    any failure and never raises, so telemetry/divergence collection never
    blocks task closure.
    """
    try:
        if task is not None:
            if spec is None:
                spec = task.get("spec")
            if merge_commit is None:
                merge_commit = task.get("merge_commit")

        if not merge_commit:
            return {
                "files": None,
                "test_delta": None,
                "status": "failed",
                "reason": "no merge_commit recorded",
            }

        if spec is None or not isinstance(spec, dict):
            return {
                "files": None,
                "test_delta": None,
                "status": "failed",
                "reason": "no spec recorded",
            }

        repo_root = Path(repo_root)

        # Verify the commit exists and has a first parent.
        rc, _, err = _run_git("rev-parse", f"{merge_commit}^1", cwd=repo_root)
        if rc != 0:
            return {
                "files": None,
                "test_delta": None,
                "status": "failed",
                "reason": f"no first parent: {err.strip()}",
            }

        rc, out, err = _run_git(
            "diff", "--name-only", f"{merge_commit}^1..{merge_commit}", cwd=repo_root
        )
        if rc != 0:
            return {
                "files": None,
                "test_delta": None,
                "status": "failed",
                "reason": f"git diff failed: {err.strip()}",
            }

        declared = extract_declared_files(spec)
        changed_files = [line.strip() for line in out.splitlines() if line.strip()]
        surplus_files = sorted(set(changed_files) - declared)

        return {
            "files": surplus_files,
            "test_delta": test_delta,
            "status": "ok",
            "reason": None,
        }
    except Exception as exc:
        return {
            "files": None,
            "test_delta": None,
            "status": "failed",
            "reason": f"divergence computation failed: {exc}",
        }


divergence = compute_divergence
