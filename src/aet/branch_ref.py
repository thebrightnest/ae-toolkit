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
