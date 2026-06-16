"""Git worktree management."""

from __future__ import annotations

import os
import shutil
import subprocess


def create_worktree(repo_root: str, task_id: str) -> str:
    """Create a git worktree for the task. Return the worktree path.

    New branches are always based on ``origin/main`` so that worktrees do not
    accidentally inherit commits from the parent session's current branch.
    """
    worktree_dir = os.path.join(repo_root, ".worktrees", task_id)
    branch_name = task_id

    if os.path.isdir(worktree_dir):
        return worktree_dir

    # Ensure origin/main is up to date; failures are non-fatal.
    subprocess.run(
        ["git", "-C", repo_root, "fetch", "origin", "main"],
        capture_output=True,
    )
    base = "origin/main"

    # Check if branch already exists
    result = subprocess.run(
        ["git", "-C", repo_root, "show-ref", "--verify", f"refs/heads/{branch_name}"],
        capture_output=True,
    )
    if result.returncode == 0:
        # If the existing branch is not based on origin/main, recreate it so the
        # worktree starts from a clean base.
        mb_result = subprocess.run(
            ["git", "-C", repo_root, "merge-base", branch_name, base],
            capture_output=True,
            text=True,
        )
        base_oid = subprocess.run(
            ["git", "-C", repo_root, "rev-parse", base],
            capture_output=True,
            text=True,
        )
        if mb_result.returncode != 0 or mb_result.stdout.strip() != base_oid.stdout.strip():
            subprocess.run(
                ["git", "-C", repo_root, "branch", "-D", branch_name],
                check=True,
                capture_output=True,
            )
        else:
            subprocess.run(
                ["git", "-C", repo_root, "worktree", "add", worktree_dir, branch_name],
                check=True,
            )
            return worktree_dir

    subprocess.run(
        ["git", "-C", repo_root, "worktree", "add", worktree_dir, "-b", branch_name, base],
        check=True,
    )
    return worktree_dir


def remove_worktree(repo_root: str, task_id: str) -> bool:
    """Remove a worktree if it exists and has no uncommitted changes."""
    worktree_dir = os.path.join(repo_root, ".worktrees", task_id)
    if not os.path.isdir(worktree_dir):
        return True

    # Check for commits ahead of main
    result = subprocess.run(
        ["git", "-C", worktree_dir, "rev-list", "--count", "main..HEAD"],
        capture_output=True,
        text=True,
    )
    ahead = int(result.stdout.strip() or 0)

    if ahead == 0:
        try:
            subprocess.run(
                ["git", "-C", repo_root, "worktree", "remove", worktree_dir],
                check=True,
            )
            return True
        except subprocess.CalledProcessError:
            # Has uncommitted changes; leave for inspection
            return False
    return False


def copy_untracked_files(repo_root: str, worktree_dir: str) -> None:
    """Copy untracked plan/PRD files into the worktree."""
    result = subprocess.run(
        [
            "git",
            "-C",
            repo_root,
            "ls-files",
            "--others",
            "--exclude-standard",
            "docs/plans/",
            "docs/prds/",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    for untracked in result.stdout.strip().split("\n"):
        if not untracked:
            continue
        src = os.path.join(repo_root, untracked)
        dest = os.path.join(worktree_dir, untracked)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        # If the destination exists and is read-only from a previous copy,
        # temporarily make it writable so copy2 can overwrite it.
        if os.path.exists(dest) and not os.access(dest, os.W_OK):
            os.chmod(dest, 0o644)
        shutil.copy2(src, dest)


def estimate_repo_size(repo_root: str) -> int:
    """Estimate repo size in bytes using du."""
    result = subprocess.run(
        ["du", "-sb", repo_root],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return int(result.stdout.split()[0])
    return 0


def check_main_hygiene(repo_root: str) -> tuple[bool, str]:
    """Check if main is clean and synced with origin."""
    # Check working tree
    result = subprocess.run(
        ["git", "-C", repo_root, "status", "--short"],
        capture_output=True,
        text=True,
    )
    if result.stdout.strip():
        return False, "Working tree is dirty"

    # Check unpushed commits
    result = subprocess.run(
        ["git", "-C", repo_root, "rev-list", "--count", "origin/main..main"],
        capture_output=True,
        text=True,
    )
    if int(result.stdout.strip() or 0) > 0:
        return False, "Local main is ahead of origin/main"

    # Check unpulled commits
    result = subprocess.run(
        ["git", "-C", repo_root, "rev-list", "--count", "main..origin/main"],
        capture_output=True,
        text=True,
    )
    if int(result.stdout.strip() or 0) > 0:
        return False, "Local main is behind origin/main"

    return True, ""
