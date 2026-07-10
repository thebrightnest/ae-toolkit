"""Verification utilities for commits and stage advancement."""

from __future__ import annotations

import os
import re
import subprocess


def verify_branch_has_commits(worktree_dir: str) -> tuple[bool, str]:
    """Verify the branch has at least one commit ahead of main."""
    if not os.path.isdir(worktree_dir):
        return False, "Worktree does not exist"

    result = subprocess.run(
        ["git", "-C", worktree_dir, "rev-list", "--count", "main..HEAD"],
        capture_output=True,
        text=True,
    )
    ahead = int(result.stdout.strip() or 0)
    if ahead > 0:
        return True, ""

    # Check for uncommitted changes
    result = subprocess.run(
        ["git", "-C", worktree_dir, "status", "--short"],
        capture_output=True,
        text=True,
    )
    if result.stdout.strip():
        return False, "Branch has uncommitted changes but no commits"

    return False, "Branch has 0 commits and no changes"


def read_plan_stage(plan_file: str) -> str | None:
    """Read the *Stage:* value from a plan.md footer.

    The stage line lives in the trailing footer, after the final separator.
    Body text may mention other stages (e.g. "set fods-06 footer to
    _Stage: superseded_"), so we take the last match rather than the first.
    """
    if not os.path.exists(plan_file):
        return None

    with open(plan_file, "r", encoding="utf-8") as f:
        content = f.read()

    matches = re.findall(r"[*_]Stage:\s*([\w-]+)[*_]", content)
    if matches:
        return matches[-1]
    return None


def verify_stage_advancement(
    recorded_stage: str | None,
    worktree_dir: str,
    expected_stage: str,
) -> tuple[bool, str]:
    """Verify the recorded pipeline stage advanced to the expected stage.

    Performs a single comparison of the recorded stage against the expected
    stage, then confirms the branch has commits. ``read_plan_stage`` is kept
    only for the advisory footer breadcrumb; it is not used to make scheduling
    decisions.
    """
    if recorded_stage != expected_stage:
        return (
            False,
            f"Stage did not advance: expected '{expected_stage}',"
            f" got '{recorded_stage}'",
        )

    ok, msg = verify_branch_has_commits(worktree_dir)
    if ok:
        return True, ""
    return False, msg
