"""Git worktree management."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any


class WorktreeBlockedError(Exception):
    """Raised when an existing worktree cannot be refreshed or safely rebuilt.

    Signals a clean halt: the task branch conflicts with the base and the
    worktree still holds work that ``remove_worktree`` refuses to discard.
    """

    def __init__(self, task_id: str, worktree_dir: str, base: str) -> None:
        self.task_id = task_id
        self.worktree_dir = worktree_dir
        self.base = base
        super().__init__(
            f"⛔ Worktree for `{task_id}` conflicts with `{base}` and holds "
            f"unmerged work at `{worktree_dir}`. Rebase or remove it manually, "
            f"then re-run."
        )


def _run_git(args: list[str], **kwargs) -> subprocess.CompletedProcess:
    """Run a git command and return the completed process."""
    return subprocess.run(["git", *args], **kwargs)


def _configured_remotes(repo_root: str) -> set[str]:
    """Return the names of remotes configured in ``repo_root``."""
    result = _run_git(["-C", repo_root, "remote"], capture_output=True, text=True)
    if result.returncode != 0:
        return set()
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def create_worktree(repo_root: str, task_id: str, base_branch: str = "origin/main") -> str:
    """Create or refresh a git worktree for the task. Return the worktree path.

    New branches are based on ``base_branch`` (default ``origin/main``) so that
    worktrees do not accidentally inherit commits from the parent session's
    current branch. Existing worktrees are refreshed: ``base_branch`` is fetched
    and the branch is rebased onto it when it has advanced.

    ``base_branch`` may also be a local ref — a project with no remote, or an
    integration branch that has not been pushed. Local bases are used as-is;
    there is nothing to fetch. See ``branch_ref.resolve_base_ref``.
    """
    worktree_dir = os.path.join(repo_root, ".worktrees", task_id)
    branch_name = task_id
    base = base_branch

    # Parse remote/ref from a remote-tracking base branch (e.g. origin/main).
    # The leading segment must name a configured remote: branch names contain
    # slashes too (``fix/catalog-job-runtime``), and treating one as a remote
    # would issue a bogus fetch and mis-drive the refresh path below.
    fetch_remote = fetch_ref = ""
    if "/" in base:
        candidate_remote, _, candidate_ref = base.partition("/")
        if candidate_remote in _configured_remotes(repo_root):
            fetch_remote, fetch_ref = candidate_remote, candidate_ref

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
                    # Fall through to recreate the worktree from the current
                    # base. remove_worktree refuses when the branch still holds
                    # non-deferred work; recreating over a surviving directory
                    # would either crash or discard that work, so halt instead.
                    if not remove_worktree(repo_root, task_id, base_branch=base):
                        raise WorktreeBlockedError(task_id, worktree_dir, base)
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


def _worktree_has_non_deferred_changes(worktree_dir: str, base_branch: str) -> bool:
    """Return True when the worktree branch differs from base outside deferred paths."""
    result = subprocess.run(
        ["git", "-C", worktree_dir, "diff", "--name-only", f"{base_branch}..HEAD"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        # Fail closed: if we cannot resolve the diff, assume real work is present.
        return True
    for line in result.stdout.splitlines():
        path = line.strip()
        if path and not _is_deferred_path(path):
            return True
    return False


def remove_worktree(repo_root: str, task_id: str, base_branch: str = "origin/main") -> bool:
    """Remove a worktree if it has no non-deferred changes."""
    worktree_dir = os.path.join(repo_root, ".worktrees", task_id)
    if not os.path.isdir(worktree_dir):
        return True

    if _worktree_has_non_deferred_changes(worktree_dir, base_branch):
        return False

    try:
        subprocess.run(
            ["git", "-C", repo_root, "worktree", "remove", worktree_dir],
            check=True,
        )
        return True
    except subprocess.CalledProcessError:
        # Has uncommitted changes or another obstruction; leave for inspection.
        return False


def _untracked_paths(worktree_dir: str) -> list[str]:
    """Return repo-relative paths of untracked files in the worktree."""
    result = subprocess.run(
        ["git", "-C", worktree_dir, "status", "--porcelain", "--untracked-files=all"],
        capture_output=True,
        text=True,
    )
    paths: list[str] = []
    if result.returncode != 0:
        return paths
    for line in result.stdout.splitlines():
        if line.startswith("??"):
            path = line[3:].strip()
            if path:
                paths.append(path)
    return paths


def _remove_deferred_untracked(worktree_dir: str) -> tuple[bool, list[str]]:
    """Remove untracked files that live in deferred durability paths.

    These are AET-generated artifacts (rendered plan docs) and are safe to
    discard because their source of truth is the task record / queue state.
    """
    errors: list[str] = []
    for path in _untracked_paths(worktree_dir):
        if not _is_deferred_path(path):
            continue
        full = os.path.join(worktree_dir, path)
        try:
            if os.path.isdir(full) and not os.path.islink(full):
                shutil.rmtree(full)
            else:
                os.remove(full)
        except OSError as exc:
            errors.append(f"{path}: {exc}")
    return (not errors), errors


def _worktree_obstructions(worktree_dir: str) -> list[str]:
    """Return uncommitted non-deferred paths that should block teardown.

    Only *uncommitted* work is at risk here: ``git worktree remove`` does not
    touch branch refs, so anything already committed survives removal on the
    branch. Unioning in the ``base..HEAD`` diff — as this did until 2026-08-27 —
    made end-of-run teardown fail by construction, because that set is non-empty
    for every task that did anything.

    The diff-based risk model still applies to the refresh path, which recreates
    the worktree and rebuilds the branch from base; that caller keeps its own
    predicate in ``_worktree_has_non_deferred_changes``.
    """
    obstructions: set[str] = set()

    status = subprocess.run(
        ["git", "-C", worktree_dir, "status", "--porcelain", "--untracked-files=all"],
        capture_output=True,
        text=True,
    )
    if status.returncode == 0:
        for line in status.stdout.splitlines():
            if not line:
                continue
            code = line[:2]
            path = line[3:].strip()
            if not path:
                continue
            if code == "??":
                if not _is_deferred_path(path) and not _is_ignored_path(path):
                    obstructions.add(path)
            elif code.strip():
                # Tracked modification (index or working tree).
                if not _is_deferred_path(path):
                    obstructions.add(path)

    return sorted(obstructions)


def teardown_worktree(repo_root: str, task_id: str) -> dict[str, Any]:
    """Tear down a task worktree, cleaning AET artifacts but refusing real work.

    Returns a dict with keys ``removed`` (bool), ``reason`` (str), and
    ``obstructions`` (list[str]). The removal is reported, not printed: callers
    decide whether the failure is fatal and how to surface it in the run result.
    """
    worktree_dir = os.path.join(repo_root, ".worktrees", task_id)
    result: dict[str, Any] = {"removed": False, "reason": "", "obstructions": []}
    if not os.path.isdir(worktree_dir):
        result["removed"] = True
        return result

    ok, errors = _remove_deferred_untracked(worktree_dir)
    if not ok:
        result["reason"] = "could not clean deferred files"
        result["obstructions"] = errors
        return result

    obstructions = _worktree_obstructions(worktree_dir)
    if obstructions:
        result["reason"] = "worktree has uncommitted changes"
        result["obstructions"] = obstructions
        return result

    try:
        subprocess.run(
            ["git", "-C", repo_root, "worktree", "remove", worktree_dir],
            check=True,
            capture_output=True,
            text=True,
        )
        result["removed"] = True
    except subprocess.CalledProcessError as exc:
        result["reason"] = exc.stderr.strip() or "git worktree remove failed"
        result["obstructions"] = _worktree_obstructions(worktree_dir)

    return result


def run_git_plain(args: list[str], **kwargs) -> tuple[int, str, str]:
    """Run a git command and return (returncode, stdout, stderr)."""
    result = subprocess.run(["git", *args], capture_output=True, text=True, **kwargs)
    return result.returncode, result.stdout, result.stderr


def delete_local_branch(repo_root: str, task_id: str) -> bool:
    """Delete a local branch, ignoring it if it does not exist."""
    result = _run_git(
        ["-C", repo_root, "branch", "-D", task_id],
        capture_output=True,
        text=True,
    )
    # returncode 0 is success; nonzero usually means the branch did not exist.
    return result.returncode == 0


def push_branch(repo_root: str, branch: str, commit: str | None = None) -> tuple[bool, str]:
    """Push ``branch`` to ``origin`` without force. Returns ``(True, "")`` on success.

    With ``commit``, push that commit to ``origin/<branch>`` and leave the local branch alone.
    """
    refspec = f"{commit}:refs/heads/{branch}" if commit else branch
    result = _run_git(
        ["-C", repo_root, "push", "origin", refspec],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return False, result.stderr.strip()
    return True, ""


def branch_checked_out_worktrees(repo_root: str | Path, branch: str) -> list[str]:
    """Return the paths of every worktree that has ``branch`` checked out."""
    result = _run_git(
        ["-C", str(repo_root), "worktree", "list", "--porcelain"],
        capture_output=True,
        text=True,
        check=True,
    )
    target = f"branch refs/heads/{branch}"
    paths: list[str] = []
    current = ""
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            current = line[len("worktree ") :]
        elif line == target:
            paths.append(current)
    return paths


def _copy_file(src: str, dest: str) -> None:
    """Copy ``src`` to ``dest``, creating parents and handling read-only targets."""
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    # If the destination exists and is read-only from a previous copy,
    # temporarily make it writable so copy2 can overwrite it.
    if os.path.exists(dest) and not os.access(dest, os.W_OK):
        os.chmod(dest, 0o644)
    shutil.copy2(src, dest)


def render_task_plan(repo_root: str, worktree_dir: str, task: dict[str, Any]) -> bool:
    """Render the task's working plan into the worktree.

    When the task record carries a portable spec (R-19), the plan is written
    from the record to ``docs/plans/<task-id>.md`` inside the worktree.  Legacy
    records without a spec fall back to copying the plan file referenced by
    ``plan_file``.
    """
    from aet import plan_parser  # local import avoids cycle with queue

    task_id = task.get("id")
    if not task_id:
        return False
    canonical = os.path.join(worktree_dir, "docs", "plans", f"{task_id}.md")
    if plan_parser.render_plan(Path(canonical), task):
        return True
    plan_file = task.get("plan_file")
    if plan_file:
        src = plan_file if os.path.isabs(plan_file) else os.path.join(repo_root, plan_file)
        if os.path.exists(src):
            os.makedirs(os.path.dirname(canonical), exist_ok=True)
            shutil.copy2(src, canonical)
            return True
    return False


def mirror_linked_prd(repo_root: str, worktree_dir: str, task: dict[str, Any]) -> str | None:
    """Copy the task's linked PRD into the worktree when it is untracked in the root.

    Returns:
        The repo-relative path of the mirrored PRD, or None when nothing is mirrored.
    """
    from aet.branch_ref import _task_prd_path

    prd = _task_prd_path(task, repo_root)
    if prd is None or not prd.is_file():
        return None
    try:
        rel = prd.resolve().relative_to(Path(repo_root).resolve()).as_posix()
    except ValueError:
        return None
    untracked = _run_git(
        ["-C", repo_root, "ls-files", "--others", "--exclude-standard", "--", rel],
        capture_output=True,
        text=True,
        check=True,
    )
    if not untracked.stdout.strip():
        return None
    _copy_file(str(prd), os.path.join(worktree_dir, rel))
    _exclude_in_worktree(worktree_dir, rel)
    return rel


MIRROR_EXCLUDE_FILE = "aet-mirror-exclude"


def _user_excludes_file(worktree_dir: str) -> str:
    """Return the excludes file git applies when ``core.excludesFile`` is unset or inherited."""
    configured = _run_git(
        ["-C", worktree_dir, "config", "--path", "core.excludesFile"],
        capture_output=True,
        text=True,
    ).stdout.strip()
    if configured:
        return configured
    xdg = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(xdg, "git", "ignore")


def _exclude_in_worktree(worktree_dir: str, rel: str) -> None:
    """Exclude ``rel`` in ``worktree_dir`` only, through a worktree-scoped ``core.excludesFile``."""
    git_dir = _run_git(
        ["-C", worktree_dir, "rev-parse", "--absolute-git-dir"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    exclude_path = os.path.join(git_dir, MIRROR_EXCLUDE_FILE)
    if not os.path.exists(exclude_path):
        # The worktree value replaces the user's excludes file, so it carries its rules.
        seed = _user_excludes_file(worktree_dir)
        lines = Path(seed).read_text(encoding="utf-8").splitlines() if os.path.isfile(seed) else []
        Path(exclude_path).write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")
    pattern = "/" + "".join(f"\\{c}" if c in "\\*?[" else c for c in rel)
    existing = Path(exclude_path).read_text(encoding="utf-8").splitlines()
    if pattern not in existing:
        with open(exclude_path, "a", encoding="utf-8") as handle:
            handle.write(f"{pattern}\n")

    enabled = _run_git(
        ["-C", worktree_dir, "config", "--bool", "extensions.worktreeConfig"],
        capture_output=True,
        text=True,
    ).stdout.strip()
    if enabled != "true":
        _run_git(["-C", worktree_dir, "config", "extensions.worktreeConfig", "true"], check=True)
    _run_git(
        ["-C", worktree_dir, "config", "--worktree", "core.excludesFile", exclude_path],
        check=True,
    )


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


# Paths the toolkit writes that must never be tracked. It feeds the `.gitignore`
# writer that `aet setup` runs; an entry declares the file machine-local.
AET_IGNORED_PATHS = {
    ".agents/aet-queue",
    ".agents/aet-queue.lock",
    ".agents/aet-queue.lease",
    ".agents/work-queue.lease",
    ".agents/work-history.jsonl",
    ".agents/integration.lock",
    ".agents/ledger.jsonl",
    ".agents/ledger.jsonl.lock",
    ".agents/learnings.jsonl.lock",
    ".agents/runs/",
    ".worktrees/",
    "docs/plans/active/",
}


# Names the toolkit used to write and no longer does. The ignore writer only
# appends, so a rename leaves the old name in every `.gitignore` it has ever
# touched and nothing reports the gap. Recording a retired name here is what
# lets `aet setup` report it; an entry leaves this set only when no project
# could still be carrying it.
AET_RETIRED_IGNORED_PATHS = {
    ".agents/work-queue.json",
    ".agents/work-queue.json.lock",
    ".agents/work-archive.json",
    "scripts/.aet-work-orchestrator.log",
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


def _matches_declaration(path: str, declaration: set[str]) -> bool:
    """Return True when ``path`` matches an entry in a path declaration.

    Directory entries end with ``/`` and match both the directory itself and
    any nested path; every other entry matches exactly.
    """
    for entry in declaration:
        if entry.endswith("/"):
            if path == entry.rstrip("/") or path.startswith(entry):
                return True
        elif path == entry:
            return True
    return False


def _is_ignored_path(path: str) -> bool:
    """Return True when ``path`` is declared as never-tracked."""
    return _matches_declaration(path, AET_IGNORED_PATHS)


DIRTY_PATHS_IN_MESSAGE = 10


def _format_paths(paths: list[str], limit: int = DIRTY_PATHS_IN_MESSAGE) -> str:
    """Render up to ``limit`` paths, counting the remainder as ``(+N more)``."""
    listed = ", ".join(paths[:limit])
    remainder = len(paths) - limit
    if remainder > 0:
        return f"{listed} (+{remainder} more)"
    return listed


def check_base_hygiene(
    repo_root: str, integration_branch: str = "main", trunk_branch: str = "main"
) -> tuple[bool, str]:
    """Check that the local integration branch carries no unpushed code.

    Halts only when the branch is ahead of origin with a path outside
    ``docs/plans/`` (ADR-054). The root working tree is operator-owned (ADR-082).
    """
    # No remote tracking branch means there is nothing to be ahead of.
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

    # Three-dot diff: only local commits count, so behind origin never halts.
    # Plan-only divergences are allowed; mixed plan+code divergences still halt.
    diff = subprocess.run(
        [
            "git",
            "-C",
            repo_root,
            "diff",
            "--name-only",
            f"origin/{integration_branch}...{integration_branch}",
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

    return True, ""
