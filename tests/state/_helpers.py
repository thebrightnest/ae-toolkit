"""Shared helpers for state tests using the git-refs backend."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from aet.backends.git_refs_backend import GitRefsBackend


def init_git_repo(path: Path) -> None:
    """Initialize a git repository with deterministic committer identity."""
    resolved = path.resolve()
    subprocess.run(["git", "init", "-q", str(resolved)], check=True)
    subprocess.run(
        ["git", "-C", str(resolved), "config", "user.email", "test@example.com"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(resolved), "config", "user.name", "Test User"],
        check=True,
    )


def add_bare_origin(repo_root: Path) -> Path:
    """Add a local bare repository as ``origin`` and return its path."""
    origin = repo_root / "origin.git"
    origin.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "--bare", "-q", str(origin)], check=True)
    subprocess.run(
        ["git", "-C", str(repo_root), "remote", "add", "origin", str(origin)],
        check=True,
    )
    return origin


def make_git_backend(queue_path: str | Path) -> GitRefsBackend:
    """Return a GitRefsBackend using the same history path as aet-state."""
    queue_path = Path(queue_path)
    history_file = queue_path.with_name("work-history.jsonl")
    return GitRefsBackend(
        queue_file=str(queue_path),
        history_file=str(history_file),
    )


def seed_git_queue(
    repo_root: Path,
    tasks: list[dict[str, Any]],
    queue_rel: str = ".agents/aet-queue",
    history_rel: str = ".agents/work-history.jsonl",
    wrapper: dict[str, Any] | None = None,
    history: list[dict[str, Any]] | None = None,
) -> tuple[Path, Path]:
    """Create a git-refs queue inside repo_root and seed it with tasks.

    Returns the resolved queue and history paths.
    """
    queue_path = repo_root / queue_rel
    history_path = repo_root / history_rel
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.parent.mkdir(parents=True, exist_ok=True)

    backend = GitRefsBackend(
        queue_file=str(queue_path), history_file=str(history_path)
    )
    backend.load()
    backend.save(tasks, wrapper=wrapper)

    if history:
        with open(history_path, "w", encoding="utf-8") as f:
            for record in history:
                f.write(json.dumps(record) + "\n")

    return queue_path, history_path


def load_git_queue(queue_path: str | Path) -> list[dict[str, Any]]:
    """Read the live task queue via the git-refs backend."""
    return make_git_backend(queue_path).load()["queue"]


def load_git_history(queue_path: str | Path) -> list[dict[str, Any]]:
    """Read the settled history via the git-refs backend."""
    return make_git_backend(queue_path).load()["history"]
