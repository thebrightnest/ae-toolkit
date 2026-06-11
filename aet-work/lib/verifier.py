"""Verification utilities for commits and stage advancement."""

from __future__ import annotations

import os
import re
import subprocess
import time


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
    """Read the *Stage:* value from a plan.md footer."""
    if not os.path.exists(plan_file):
        return None

    with open(plan_file, "r", encoding="utf-8") as f:
        content = f.read()

    match = re.search(r"\*Stage:\s*(\w+)\*", content)
    if match:
        return match.group(1)
    return None


def verify_stage_advancement(
    plan_file: str,
    worktree_dir: str,
    expected_stage: str,
    retries: int = 1,
) -> tuple[bool, str]:
    """Verify the plan advanced to the expected stage with optional retry."""
    for attempt in range(retries + 1):
        stage = read_plan_stage(plan_file)
        if stage == expected_stage:
            ok, msg = verify_branch_has_commits(worktree_dir)
            if ok:
                return True, ""
            return False, msg

        if attempt < retries:
            time.sleep(2)

    return False, f"Stage did not advance: expected '{expected_stage}', got '{stage}'"
