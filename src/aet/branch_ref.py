"""Resolve trunk and integration branch refs with provenance."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any, NamedTuple


class BranchRef(NamedTuple):
    """A branch ref plus a description of how it was derived."""

    ref: str
    provenance: str


def resolve_trunk_branch(repo_root, config) -> BranchRef:
    """Resolve the trunk (final merge target) branch ref.

    Precedence: config ``trunk_branch`` →
    ``git symbolic-ref refs/remotes/origin/HEAD`` → ``main`` fallback.
    """
    config_value = config.get("trunk_branch")
    if config_value:
        return BranchRef(config_value, "config")

    result = subprocess.run(
        ["git", "-C", str(repo_root), "symbolic-ref", "refs/remotes/origin/HEAD"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        target = result.stdout.strip()
        prefix = "refs/remotes/origin/"
        if target.startswith(prefix):
            target = target[len(prefix) :]
        return BranchRef(target, "detected")

    return BranchRef("main", "fallback")


def resolve_base_ref(repo_root, ref: str) -> str:
    """Resolve a branch name to the ref a worktree should actually be based on.

    Worktrees prefer the remote-tracking ref so they never inherit unpushed
    commits from the parent session. But a remote-tracking ref only exists when
    there is a remote that carries the branch, and neither is guaranteed: a
    project may have no remote at all, or an integration branch may not be
    pushed yet. Prefixing ``origin/`` unconditionally turns both cases into
    ``fatal: invalid reference`` before any work starts.

    Resolution order:

    1. ``ref`` already names a remote-tracking ref (``origin/main``) → unchanged.
    2. ``refs/remotes/origin/<ref>`` exists → ``origin/<ref>``.
    3. Otherwise the local ``<ref>``.

    This mirrors ``worktree.check_base_hygiene``, which skips its ahead
    comparison when the remote-tracking ref is absent.
    """
    if _ref_exists(repo_root, f"refs/remotes/{ref}"):
        return ref
    if _ref_exists(repo_root, f"refs/remotes/origin/{ref}"):
        return f"origin/{ref}"
    return ref


def ensure_integration_branch(repo_root, branch: str, trunk_ref: str) -> bool:
    """Create ``branch`` at ``trunk_ref`` when it exists neither locally nor on origin.

    Returns True when the branch was created. Never pushes (ADR-045 §4) and
    never moves ``HEAD`` in the root checkout (ADR-082).
    """
    for ref in (f"refs/heads/{branch}", f"refs/remotes/{branch}", f"refs/remotes/origin/{branch}"):
        if _ref_exists(repo_root, ref):
            return False
    subprocess.run(
        ["git", "-C", str(repo_root), "branch", branch, trunk_ref],
        check=True,
        capture_output=True,
        text=True,
    )
    return True


def _ref_exists(repo_root, ref: str) -> bool:
    """Return True when ``ref`` resolves in ``repo_root``."""
    return (
        subprocess.run(
            ["git", "-C", str(repo_root), "show-ref", "--quiet", "--verify", ref],
            capture_output=True,
        ).returncode
        == 0
    )


def derive_integration_branch_from_prd(prd_path: str | Path | None) -> str | None:
    """Return an integration branch name derived from a PRD path.

    The branch name is ``feat/`` plus the PRD file's stem with a trailing
    ``-prd`` removed.  Returns ``None`` when no PRD path is supplied or the
    path has no stem.
    """
    if not prd_path:
        return None
    stem = Path(prd_path).stem.removesuffix("-prd")
    if not stem:
        return None
    return f"feat/{stem}"


def prds_for_branch(repo_root: str | Path, branch: str) -> list[Path]:
    """Return the PRDs under ``docs/prds/`` whose resolved branch equals ``branch``.

    A PRD resolves to its frontmatter ``branch``, else to the name derived from its filename.
    """
    from aet import plan_parser

    wanted = branch.removeprefix("origin/")
    matches = []
    for prd in sorted((Path(repo_root) / "docs" / "prds").glob("*.md")):
        declared = plan_parser.parse_frontmatter(prd).get("branch")
        resolved = str(declared) if declared else derive_integration_branch_from_prd(prd)
        if resolved == wanted:
            matches.append(prd)
    return matches


def resolve_integration_branch(repo_root, config, cli_base=None) -> BranchRef:
    """Resolve the integration (worktree base) branch ref.

    Precedence: ``cli_base`` → ``AET_WORK_BASE_BRANCH`` env → config
    ``integration_branch`` → ``trunk_branch``.
    """
    if cli_base:
        return BranchRef(cli_base, "cli")

    env_base = os.environ.get("AET_WORK_BASE_BRANCH")
    if env_base:
        return BranchRef(env_base, "env")

    config_value = config.get("integration_branch")
    if config_value:
        return BranchRef(config_value, "config")

    trunk = resolve_trunk_branch(repo_root, config)
    return BranchRef(trunk.ref, "trunk")


def _task_prd_path(task: dict[str, Any], repo_root: str | Path) -> Path | None:
    """Return the PRD path for a task, preferring its spec and falling back to the plan file."""
    spec = task.get("spec")
    if isinstance(spec, dict):
        frontmatter = spec.get("frontmatter", {})
        source_prd = frontmatter.get("source_prd")
        if source_prd:
            path = Path(source_prd)
            if not path.is_absolute():
                path = Path(repo_root) / path
            return path
        body = spec.get("body")
        if body:
            from aet import plan_parser

            path = plan_parser.prd_path_from_text(body, repo_root=repo_root)
            if path is not None:
                return path

    plan_file = task.get("plan_file")
    if plan_file:
        from aet import plan_parser

        path = plan_parser.prd_path_for_plan(Path(plan_file), repo_root=repo_root)
        if path is not None:
            return path

    return None


def resolve_integration_branch_for_task(
    repo_root: str | Path,
    config: dict[str, Any],
    task: dict[str, Any],
    integration_mode: str,
    cli_base: str | None = None,
    backend: Any = None,
    ignore_stamp: bool = False,
) -> BranchRef:
    """Resolve the integration branch for a specific task.

    Explicit overrides (CLI, env) always win.  In ``single-pr`` mode the branch
    is resolved using the full resolution order:
    1. CLI override (`cli_base`) -> provenance 'cli'
    2. Environment (`AET_WORK_BASE_BRANCH`) -> provenance 'env'
    3. Task record stamp (`task["integration_branch"]`) -> provenance 'stamp' (skipped if ignore_stamp=True)
    4. Parent document declared branch (`branch` in PRD frontmatter) -> provenance 'document'
    5. Name derived from the PRD filename -> provenance 'prd'
    6. Config `integration_branch` -> provenance 'config'
    7. Trunk fallback -> provenance 'trunk'

    In ``pr-per-task`` mode, steps 3-5 are skipped, preserving ADR-045 Scenario A
    as the degenerate case.
    """
    if cli_base:
        return BranchRef(cli_base, "cli")

    env_base = os.environ.get("AET_WORK_BASE_BRANCH")
    if env_base:
        return BranchRef(env_base, "env")

    if integration_mode == "single-pr":
        # 3. Task record stamp
        if not ignore_stamp:
            stamp = task.get("integration_branch")
            if not stamp and isinstance(task.get("stamp"), dict):
                stamp = task.get("stamp", {}).get("branch")
            if stamp:
                return BranchRef(str(stamp), "stamp")

        # 4. Parent document declared branch
        prd_path = _task_prd_path(task, repo_root)
        if prd_path and Path(prd_path).is_file():
            from aet import plan_parser

            try:
                fm = plan_parser.parse_frontmatter(Path(prd_path))
                declared_branch = fm.get("branch")
                if declared_branch:
                    return BranchRef(str(declared_branch), "document")
            except Exception:
                pass

        # 5. Name derived from the PRD filename
        derived = derive_integration_branch_from_prd(prd_path)
        if derived:
            return BranchRef(derived, "prd")

    config_value = config.get("integration_branch")
    if config_value:
        return BranchRef(config_value, "config")

    trunk = resolve_trunk_branch(repo_root, config)
    return BranchRef(trunk.ref, "trunk")


def check_task_epic_mismatch(
    repo_root: str | Path,
    config: dict[str, Any],
    task: dict[str, Any],
    integration_mode: str,
    cli_base: str | None = None,
    backend: Any = None,
) -> tuple[bool, str | None, str | None]:
    """Check whether a task's stamped integration branch differs from the active chain.

    Returns (has_mismatch, stamped_branch, resolved_branch).
    Mismatch only applies in single-pr mode when the task has a stamped integration_branch.
    """
    if integration_mode != "single-pr":
        return False, None, None
    stamp = task.get("integration_branch")
    if not stamp and isinstance(task.get("stamp"), dict):
        stamp = task.get("stamp", {}).get("branch")
    if not stamp:
        return False, None, None

    active_ref = resolve_integration_branch_for_task(
        repo_root,
        config,
        task,
        integration_mode,
        cli_base=cli_base,
        backend=backend,
        ignore_stamp=True,
    )
    if active_ref.ref.removeprefix("origin/") != str(stamp).removeprefix("origin/"):
        return True, str(stamp), active_ref.ref
    return False, None, None


def format_epic_mismatch_error(
    task_id: str, stamped_branch: str, resolved_branch: str
) -> str:
    """Format the error message for an epic mismatch including remedies."""
    return (
        f"⛔ Epic mismatch for task '{task_id}': task is stamped to integration branch '{stamped_branch}', "
        f"but its PRD now resolves to '{resolved_branch}'.\n"
        f"   Remedies:\n"
        f"   1. Keep the stamped branch: declare `branch: {stamped_branch}` in the task's PRD "
        f"frontmatter (or pass `--base {stamped_branch}`)\n"
        f"   2. Reset the task to target the new epic: `aet state reset {task_id}`"
    )
