"""Resolve trunk and integration branch refs with provenance."""

from __future__ import annotations

import os
import subprocess
from typing import NamedTuple


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

    This mirrors ``worktree.check_base_hygiene``, which already skips its
    ahead/behind comparison when the remote-tracking ref is absent so that
    projects without an origin are not falsely halted.
    """
    if _ref_exists(repo_root, f"refs/remotes/{ref}"):
        return ref
    if _ref_exists(repo_root, f"refs/remotes/origin/{ref}"):
        return f"origin/{ref}"
    return ref


def _ref_exists(repo_root, ref: str) -> bool:
    """Return True when ``ref`` resolves in ``repo_root``."""
    return (
        subprocess.run(
            ["git", "-C", str(repo_root), "show-ref", "--quiet", "--verify", ref],
            capture_output=True,
        ).returncode
        == 0
    )


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
