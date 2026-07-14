"""Neutral project identity and path resolution.

This module sits below telemetry and backends so that both can resolve the
project slug without creating a layering inversion (e.g. backends importing
telemetry only to derive an identity).
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any


def resolve_repo_root(repo_root: str | Path | None = None) -> Path:
    """Resolve the repository root from args, env, git, or cwd."""
    if repo_root is not None:
        return Path(repo_root).resolve()

    env_root = os.environ.get("AET_REPO_ROOT")
    if env_root:
        return Path(env_root).resolve()

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return Path(result.stdout.strip()).resolve()
    except FileNotFoundError:
        pass

    return Path.cwd().resolve()


def derive_project_slug(repo_root: str | Path | None = None) -> str:
    """Derive a worktree-based slug: ``<main-worktree-dir>/<worktree-label>``.

    The primary worktree is labelled ``main``; a linked worktree contributes
    its own directory name. Env overrides (``AET_PROJECT_ID`` /
    ``AET_REPO_SLUG``) win; non-git directories fall back to the basename.
    """
    env_slug = os.environ.get("AET_PROJECT_ID") or os.environ.get("AET_REPO_SLUG")
    if env_slug:
        return env_slug

    repo_root = resolve_repo_root(repo_root)

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            out = result.stdout.strip()
            common = Path(out) if os.path.isabs(out) else (repo_root / out)
            main_root = common.resolve().parent  # <main>/.git -> <main>
            label = "main" if repo_root == main_root else repo_root.name
            return f"{main_root.name}/{label}"
    except FileNotFoundError:
        pass

    return repo_root.name


# Keep Any import referenced so linters do not complain on re-export usage.
Any = Any
