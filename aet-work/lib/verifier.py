"""Verification utilities for commits and stage advancement."""

from __future__ import annotations

import os
import re
import subprocess
import tempfile


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


def working_tree_hash(worktree_dir: str) -> str:
    """Return a git tree object id fingerprinting the whole working tree.

    Stages every tracked and untracked-but-not-ignored path into a throwaway
    index and writes it out as a tree object. The id is stable for a given set
    of file contents and changes the moment any content does — including
    uncommitted, mid-stage edits, which is exactly the state a validation
    attests to. ``write-tree`` persists the tree and its blobs to the repo's
    real object store, so the id stays diffable later (see :func:`changed_paths`).

    Returns ``""`` when ``worktree_dir`` is not a git repo or git is
    unavailable, so callers can treat an empty hash as "unknown — revalidate".
    The real index is never touched: staging happens in a temporary
    ``GIT_INDEX_FILE`` seeded from ``HEAD`` so only changed paths are rehashed.
    """
    if not os.path.isdir(worktree_dir):
        return ""
    try:
        with tempfile.TemporaryDirectory() as tmp:
            env = {**os.environ, "GIT_INDEX_FILE": os.path.join(tmp, "index")}
            # Seed from HEAD so `add -A` only rehashes what changed; a repo with
            # no commits yet starts from an empty index, which is also valid.
            subprocess.run(
                ["git", "-C", worktree_dir, "read-tree", "HEAD"],
                env=env, capture_output=True, text=True, check=False,
            )
            staged = subprocess.run(
                ["git", "-C", worktree_dir, "add", "-A"],
                env=env, capture_output=True, text=True, check=False,
            )
            if staged.returncode != 0:
                return ""
            tree = subprocess.run(
                ["git", "-C", worktree_dir, "write-tree"],
                env=env, capture_output=True, text=True, check=False,
            )
            if tree.returncode != 0:
                return ""
            return tree.stdout.strip()
    except OSError:
        return ""


def changed_paths(worktree_dir: str, tree_a: str, tree_b: str) -> list[str] | None:
    """Return the repo-relative paths differing between two tree object ids.

    Returns ``None`` when the diff cannot be computed — a missing/garbage tree
    id, or git unavailable — so callers treat it as "unknown — revalidate"
    rather than "nothing changed".
    """
    if not tree_a or not tree_b:
        return None
    try:
        result = subprocess.run(
            ["git", "-C", worktree_dir, "diff", "--name-only", tree_a, tree_b],
            capture_output=True, text=True, check=False,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    return [line for line in result.stdout.splitlines() if line.strip()]
