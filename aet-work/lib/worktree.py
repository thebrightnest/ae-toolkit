"""Git worktree management."""

from __future__ import annotations

import json
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
    """Copy untracked plan/PRD and referenced docs into the worktree."""
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
            "docs/adr/",
            "docs/audits/",
            "docs/retros/",
            "docs/product-briefs/",
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


def dependency_warmup_required(repo_root: str, worktree_dir: str) -> list[dict]:
    """Return configured dependencies that are missing inside the worktree.

    Reads ``.agents/aet-work.json`` for a ``symlink_dependencies`` array. Each
    entry is expected to have ``name``, ``source``, and ``target`` keys. Targets
    are checked relative to ``worktree_dir``. An empty list means no warmup is
    required (or no config exists).
    """
    config_path = os.path.join(repo_root, ".agents", "aet-work.json")
    if not os.path.isfile(config_path):
        return []

    try:
        with open(config_path, encoding="utf-8") as f:
            config = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []

    dependencies = config.get("symlink_dependencies", [])
    if not isinstance(dependencies, list):
        return []

    missing: list[dict] = []
    for dep in dependencies:
        if not isinstance(dep, dict):
            continue
        target = dep.get("target")
        if not target:
            continue
        target_path = os.path.join(worktree_dir, target)
        if not os.path.exists(target_path):
            missing.append(dep)

    return missing


def prepare_worktree_dependencies(repo_root: str, worktree_dir: str) -> list[dict]:
    """Create symlink dependencies inside a new worktree.

    Reads ``.agents/aet-work.json`` for a ``symlink_dependencies`` array. Each
    entry must have ``name``, ``source``, and ``target`` keys. The source is
    resolved relative to ``repo_root`` and the target relative to
    ``worktree_dir``. Missing parent directories are created automatically.

    Returns a list of result dicts with keys ``name``, ``target``, ``status``
    (``created``, ``skipped``, or ``failed``), and ``message``.
    """
    config_path = os.path.join(repo_root, ".agents", "aet-work.json")
    if not os.path.isfile(config_path):
        return []

    try:
        with open(config_path, encoding="utf-8") as f:
            config = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []

    dependencies = config.get("symlink_dependencies", [])
    if not isinstance(dependencies, list):
        return []

    results: list[dict] = []
    for dep in dependencies:
        if not isinstance(dep, dict):
            continue
        name = dep.get("name")
        source = dep.get("source")
        target = dep.get("target")
        if not name or not source or not target:
            results.append(
                {
                    "name": name or "unknown",
                    "target": target or "unknown",
                    "status": "failed",
                    "message": "missing name, source, or target field",
                }
            )
            continue

        source_path = os.path.join(repo_root, source)
        target_path = os.path.join(worktree_dir, target)

        if os.path.islink(target_path):
            results.append(
                {
                    "name": name,
                    "target": target,
                    "status": "skipped",
                    "message": "target already exists as symlink",
                }
            )
            continue
        if os.path.exists(target_path):
            results.append(
                {
                    "name": name,
                    "target": target,
                    "status": "skipped",
                    "message": "target already exists",
                }
            )
            continue
        if not os.path.exists(source_path):
            results.append(
                {
                    "name": name,
                    "target": target,
                    "status": "failed",
                    "message": f"source does not exist: {source}",
                }
            )
            continue

        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        rel_source = os.path.relpath(source_path, os.path.dirname(target_path))
        os.symlink(rel_source, target_path)
        results.append(
            {
                "name": name,
                "target": target,
                "status": "created",
                "message": f"symlinked {source} -> {target}",
            }
        )

    return results


def check_main_hygiene(repo_root: str) -> tuple[bool, str]:
    """Check if main is clean and synced with origin.

    Queue files are excluded from the dirty check because the orchestrator
    mutates them as part of normal operation and they are gitignored in
    projects using the toolkit.
    """
    ignored_paths = {
        ".agents/work-queue.json",
        ".agents/work-history.jsonl",
    }

    # Check working tree, ignoring queue-mutation artifacts. Use
    # --untracked-files=all so untracked paths are listed individually rather
    # than collapsed into parent directories.
    result = subprocess.run(
        ["git", "-C", repo_root, "status", "--short", "--untracked-files=all"],
        capture_output=True,
        text=True,
    )
    dirty_lines = []
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        parts = stripped.split(maxsplit=1)
        if len(parts) < 2:
            continue
        path = parts[1]
        if path not in ignored_paths:
            dirty_lines.append(line)
    if dirty_lines:
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
