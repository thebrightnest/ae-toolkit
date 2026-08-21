"""Shared helpers for orchestrator tests using the git-refs queue backend."""

from __future__ import annotations

import subprocess
from pathlib import Path

from aet.backends.git_refs_backend import GitRefsBackend

QUEUE_BASENAME = "aet-queue"


def _ensure_git_repo(repo_root: str) -> None:
    """Initialize a git repo when the caller has not done so."""
    if (Path(repo_root) / ".git").exists():
        return
    subprocess.run(["git", "init", "-q", repo_root], check=True)
    subprocess.run(
        ["git", "-C", repo_root, "config", "user.email", "test@example.com"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", repo_root, "config", "user.name", "Test User"],
        check=True,
    )


def queue_path(repo_root: str) -> str:
    """Return the canonical queue file path under ``repo_root``."""
    return str(Path(repo_root) / ".agents" / QUEUE_BASENAME)


def history_path(queue_file: str) -> str:
    """Return the canonical history JSONL path paired with ``queue_file``."""
    return str(Path(queue_file).with_name("work-history.jsonl"))


def write_queue(repo_root: str, tasks: list[dict]) -> str:
    """Seed ``tasks`` into the git-refs backend and return the queue path."""
    _ensure_git_repo(repo_root)
    queue_file = queue_path(repo_root)
    Path(queue_file).parent.mkdir(parents=True, exist_ok=True)
    backend = GitRefsBackend(
        queue_file=queue_file, history_file=history_path(queue_file)
    )
    backend.save(tasks)
    return queue_file


def load_queue(queue_file: str) -> list[dict]:
    """Load the live task queue from the git-refs backend."""
    backend = GitRefsBackend(
        queue_file=queue_file, history_file=history_path(queue_file)
    )
    return backend.load()["queue"]
