"""Git worktree management."""

from __future__ import annotations

import json
import os
import shutil
import subprocess


def _run_git(args: list[str], **kwargs) -> subprocess.CompletedProcess:
    """Run a git command and return the completed process."""
    return subprocess.run(["git", *args], **kwargs)


def create_worktree(repo_root: str, task_id: str, base_branch: str = "origin/main") -> str:
    """Create or refresh a git worktree for the task. Return the worktree path.

    New branches are based on ``base_branch`` (default ``origin/main``) so that
    worktrees do not accidentally inherit commits from the parent session's
    current branch. Existing worktrees are refreshed: ``base_branch`` is fetched
    and the branch is rebased onto it when it has advanced.
    """
    worktree_dir = os.path.join(repo_root, ".worktrees", task_id)
    branch_name = task_id
    base = base_branch

    # Parse remote/ref from a remote-tracking base branch (e.g. origin/main).
    fetch_remote = fetch_ref = ""
    if "/" in base:
        fetch_remote, _, fetch_ref = base.partition("/")

    # Refresh the base branch in the main repo.
    if fetch_remote and fetch_ref:
        _run_git(["-C", repo_root, "fetch", fetch_remote, fetch_ref], capture_output=True)

    base_oid = _run_git(
        ["-C", repo_root, "rev-parse", base], capture_output=True, text=True
    )
    base_sha = base_oid.stdout.strip() if base_oid.returncode == 0 else ""

    # If the worktree already exists, refresh it in place rather than deleting
    # the branch from under it.
    if os.path.isdir(worktree_dir):
        if base_sha and fetch_remote and fetch_ref:
            _run_git(
                ["-C", worktree_dir, "fetch", fetch_remote, fetch_ref],
                capture_output=True,
            )
            local_oid = _run_git(
                ["-C", worktree_dir, "rev-parse", branch_name],
                capture_output=True,
                text=True,
            )
            local_sha = local_oid.stdout.strip() if local_oid.returncode == 0 else ""
            if local_sha and local_sha != base_sha:
                # If the worktree has uncommitted changes, leave it as-is for the
                # agent to handle. Rebase refuses to run with a dirty worktree,
                # and removing it would discard in-progress work.
                dirty = _run_git(
                    ["-C", worktree_dir, "status", "--porcelain"],
                    capture_output=True,
                    text=True,
                )
                if dirty.stdout.strip():
                    return worktree_dir

                rebase = _run_git(
                    ["-C", worktree_dir, "rebase", base],
                    capture_output=True,
                    text=True,
                )
                if rebase.returncode != 0:
                    _run_git(["-C", worktree_dir, "rebase", "--abort"], capture_output=True)
                    # Fall through to recreate the worktree from the current base.
                    remove_worktree(repo_root, task_id)
                else:
                    return worktree_dir
            else:
                # Worktree is already on the current base; nothing to refresh.
                return worktree_dir
        else:
            return worktree_dir

    # Ensure a clean branch to build the worktree from.
    branch_exists = (
        _run_git(
            ["-C", repo_root, "show-ref", "--verify", f"refs/heads/{branch_name}"],
            capture_output=True,
        ).returncode
        == 0
    )

    if branch_exists and base_sha:
        mb_result = _run_git(
            ["-C", repo_root, "merge-base", branch_name, base],
            capture_output=True,
            text=True,
        )
        branch_base_sha = mb_result.stdout.strip() if mb_result.returncode == 0 else ""
        if branch_base_sha != base_sha:
            diverged = _run_git(
                ["-C", repo_root, "rev-list", "--count", f"{base}..{branch_name}"],
                capture_output=True,
                text=True,
            )
            diverged_count = (
                int(diverged.stdout.strip() or 0) if diverged.returncode == 0 else 0
            )
            if diverged_count == 0:
                # No local commits: reset the branch to the current base.
                _run_git(
                    ["-C", repo_root, "branch", "-f", branch_name, base],
                    check=True,
                    capture_output=True,
                )
            else:
                # Has local commits: rebase inside a worktree dedicated to this
                # branch. Never run a HEAD-changing git command in repo_root.
                _run_git(
                    ["-C", repo_root, "worktree", "add", worktree_dir, branch_name],
                    check=True,
                )
                rebase = _run_git(
                    ["-C", worktree_dir, "rebase", base],
                    capture_output=True,
                    text=True,
                )
                if rebase.returncode == 0:
                    return worktree_dir
                _run_git(["-C", worktree_dir, "rebase", "--abort"], capture_output=True)
                _run_git(
                    ["-C", repo_root, "worktree", "remove", worktree_dir],
                    check=True,
                    capture_output=True,
                )
                _run_git(
                    ["-C", repo_root, "branch", "-D", branch_name],
                    check=True,
                    capture_output=True,
                )
                branch_exists = False

    if branch_exists:
        _run_git(
            ["-C", repo_root, "worktree", "add", worktree_dir, branch_name],
            check=True,
        )
    else:
        _run_git(
            ["-C", repo_root, "worktree", "add", worktree_dir, "-b", branch_name, base],
            check=True,
        )
    return worktree_dir


def remove_worktree(repo_root: str, task_id: str, base_branch: str = "origin/main") -> bool:
    """Remove a worktree if it exists and has no uncommitted changes."""
    worktree_dir = os.path.join(repo_root, ".worktrees", task_id)
    if not os.path.isdir(worktree_dir):
        return True

    # Check for commits ahead of the configured base branch.
    result = subprocess.run(
        ["git", "-C", worktree_dir, "rev-list", "--count", f"{base_branch}..HEAD"],
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


def run_git_plain(args: list[str], **kwargs) -> tuple[int, str, str]:
    """Run a git command and return (returncode, stdout, stderr)."""
    result = subprocess.run(["git", *args], capture_output=True, text=True, **kwargs)
    return result.returncode, result.stdout, result.stderr


def squash_merge_task_branch(
    repo_root: str, task_id: str, integration_branch: str
) -> tuple[bool, str]:
    """Squash-merge a task branch into the integration branch.

    Runs in ``repo_root`` and leaves HEAD on ``integration_branch``. Returns
    ``(True, merge_commit)`` on success, ``(False, message)`` on failure.
    """
    branch_name = task_id

    # Ensure the integration branch exists locally and we are on it.
    checkout = _run_git(
        ["-C", repo_root, "checkout", integration_branch],
        capture_output=True,
        text=True,
    )
    if checkout.returncode != 0:
        return False, f"checkout {integration_branch} failed: {checkout.stderr.strip()}"

    merge = _run_git(
        ["-C", repo_root, "merge", "--squash", branch_name],
        capture_output=True,
        text=True,
    )
    if merge.returncode != 0:
        _run_git(["-C", repo_root, "merge", "--abort"], capture_output=True)
        return False, f"squash merge of {branch_name} failed: {merge.stderr.strip()}"

    commit = _run_git(
        ["-C", repo_root, "commit", "-m", f"Integrate {task_id}"],
        capture_output=True,
        text=True,
    )
    if commit.returncode != 0:
        return False, f"commit after squash merge failed: {commit.stderr.strip()}"

    rc, out, _ = run_git_plain(["-C", repo_root, "rev-parse", "HEAD"])
    if rc != 0:
        return False, "could not resolve merge commit"
    return True, out.strip()


def delete_local_branch(repo_root: str, task_id: str) -> bool:
    """Delete a local branch, ignoring it if it does not exist."""
    result = _run_git(
        ["-C", repo_root, "branch", "-D", task_id],
        capture_output=True,
        text=True,
    )
    # returncode 0 is success; nonzero usually means the branch did not exist.
    return result.returncode == 0


def push_branch(repo_root: str, branch: str) -> tuple[bool, str]:
    """Push ``branch`` to ``origin``. Returns ``(True, "")`` on success."""
    result = _run_git(
        ["-C", repo_root, "push", "origin", branch],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return False, result.stderr.strip()
    return True, ""


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


def dependency_warmup_required(repo_root: str, worktree_dir: str) -> list[dict]:
    """Return configured dependencies that are missing inside the worktree.

    Reads ``.agents/aet-config.json`` for a ``symlink_dependencies`` array. Each
    entry is expected to have ``name``, ``source``, and ``target`` keys. Targets
    are checked relative to ``worktree_dir``. An empty list means no warmup is
    required (or no config exists).
    """
    config_path = os.path.join(repo_root, ".agents", "aet-config.json")
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

    Reads ``.agents/aet-config.json`` for a ``symlink_dependencies`` array. Each
    entry must have ``name``, ``source``, and ``target`` keys. The source is
    resolved relative to ``repo_root`` and the target relative to
    ``worktree_dir``. Missing parent directories are created automatically.

    Returns a list of result dicts with keys ``name``, ``target``, ``status``
    (``created``, ``skipped``, or ``failed``), and ``message``.
    """
    config_path = os.path.join(repo_root, ".agents", "aet-config.json")
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


AET_IGNORED_PATHS = {
    ".agents/work-queue.json",
    ".agents/work-queue.json.lock",
    ".agents/work-queue.lease",
    ".agents/work-history.jsonl",
    ".agents/integration.lock",
    ".agents/runs/",
    ".worktrees/",
}


# Paths whose durability is deferred until the PR closure writes a terminal
# status. Mid-sprint mutations to these paths do not block base hygiene or
# intake (ADR-054).
DEFERRED_PATH_PREFIXES = ("docs/plans/",)


def _is_deferred_path(path: str) -> bool:
    """Return True when ``path`` is inside the deferred durability set.

    The deferred set covers ``docs/plans/`` and any nested path. The directory
    itself (``docs/plans``) is also treated as deferred so callers can reason
    about the prefix without trailing slash ambiguity.
    """
    if path == "docs/plans":
        return True
    for prefix in DEFERRED_PATH_PREFIXES:
        if path.startswith(prefix):
            return True
    return False


# Public alias used by consumers that should not reach into the private name.
is_deferred_path = _is_deferred_path


def _is_ignored_path(path: str) -> bool:
    """Return True when ``path`` matches an AET ignored path or directory.

    Directory entries in ``AET_IGNORED_PATHS`` end with ``/`` and match both
    the directory itself and any nested path.
    """
    for ignored in AET_IGNORED_PATHS:
        if ignored.endswith("/"):
            prefix = ignored
            dir_only = ignored.rstrip("/")
            if path == dir_only or path.startswith(prefix):
                return True
        elif path == ignored:
            return True
    return False


def check_base_hygiene(
    repo_root: str, integration_branch: str = "main", trunk_branch: str = "main"
) -> tuple[bool, str]:
    """Check if the integration branch is clean and synced with origin.

    AET-generated paths are excluded from the dirty check because the
    orchestrator mutates them as part of normal operation and they must be
    gitignored in projects using the toolkit. Plan files under ``docs/plans/``
    are also excluded: their mid-sprint lifecycle status is local-only until
    a terminal transition commits them (ADR-054). The ahead-of-origin check
    still halts when any diverging path is outside the deferred set.
    """
    # Check working tree, ignoring AET-generated paths and deferred plan
    # paths. Use --untracked-files=all so untracked paths are listed
    # individually rather than collapsed into parent directories.
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
        if not _is_ignored_path(path) and not _is_deferred_path(path):
            dirty_lines.append(line)
    if dirty_lines:
        return False, "Working tree is dirty"

    # No remote tracking branch means there is nothing to be ahead of or
    # behind; projects without an origin must not be falsely halted.
    origin_ref = f"refs/remotes/origin/{integration_branch}"
    has_origin = (
        subprocess.run(
            ["git", "-C", repo_root, "show-ref", "--quiet", "--verify", origin_ref],
            capture_output=True,
        ).returncode
        == 0
    )
    if not has_origin:
        return True, ""

    # Check unpushed commits against the integration branch. Plan-only
    # divergences are allowed; mixed plan+code divergences still halt.
    diff = subprocess.run(
        [
            "git",
            "-C",
            repo_root,
            "diff",
            "--name-only",
            f"origin/{integration_branch}..{integration_branch}",
        ],
        capture_output=True,
        text=True,
    )
    if diff.returncode == 0:
        diverging = [p for p in diff.stdout.splitlines() if p.strip()]
        if diverging and not all(_is_deferred_path(p) for p in diverging):
            msg = f"Local {integration_branch} is ahead of origin/{integration_branch}"
            if integration_branch != trunk_branch:
                msg += f" (trunk: {trunk_branch})"
            return False, msg
    else:
        # Cannot resolve the divergence; fail closed to preserve ADR-027.
        msg = f"Local {integration_branch} is ahead of origin/{integration_branch}"
        if integration_branch != trunk_branch:
            msg += f" (trunk: {trunk_branch})"
        return False, msg

    # Check unpulled commits against the integration branch.
    result = subprocess.run(
        [
            "git",
            "-C",
            repo_root,
            "rev-list",
            "--count",
            f"{integration_branch}..origin/{integration_branch}",
        ],
        capture_output=True,
        text=True,
    )
    if int(result.stdout.strip() or 0) > 0:
        msg = f"Local {integration_branch} is behind origin/{integration_branch}"
        if integration_branch != trunk_branch:
            msg += f" (trunk: {trunk_branch})"
        return False, msg

    return True, ""
