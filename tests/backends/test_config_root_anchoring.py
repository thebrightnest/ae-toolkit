"""Config and store must be anchored to the same repository.

`create_backend` resolves the in-tree config against the root discovered from
``queue_file`` and instantiates the git-refs backend. When the queue path is
outside a git repository, the selection is refused by name rather than
surfacing as a traceback from the backend's own discovery.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from aet.backends.factory import (
    LegacyTaskBackendError,
    QueueOutsideRepositoryError,
    create_backend,
    queue_repo_root,
)
from aet.backends.git_refs_backend import GitRefsBackend


def _repo(root: Path, config: dict | None = None) -> Path:
    """Create a real git repo at ``root``, optionally with a project config."""
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    agents = root / ".agents"
    agents.mkdir(exist_ok=True)
    if config is not None:
        (agents / "aet-config.json").write_text(
            json.dumps(config), encoding="utf-8"
        )
    return root


def test_out_of_repo_queue_is_refused_by_name(tmp_path, monkeypatch):
    """A queue outside any repository cannot use the git-refs store."""
    outside = tmp_path / "outside"
    outside.mkdir()
    queue = outside / "q.json"
    queue.write_text("[]", encoding="utf-8")

    with pytest.raises(QueueOutsideRepositoryError) as excinfo:
        create_backend(queue_file=str(queue), history_file=str(outside / "h.jsonl"))

    assert str(queue) in str(excinfo.value)
    assert "not inside a git repository" in str(excinfo.value)


def test_in_repo_queue_resolves_to_git_refs(tmp_path, monkeypatch):
    """The positive case: config and queue in one tree resolve to git-refs."""
    repo = _repo(tmp_path / "repo")
    queue = repo / ".agents" / "aet-queue"

    monkeypatch.chdir(repo)
    backend = create_backend(
        queue_file=str(queue), history_file=str(repo / ".agents" / "h.jsonl")
    )

    assert isinstance(backend, GitRefsBackend)


def test_task_backend_key_fails_with_migration_message(tmp_path, monkeypatch):
    """A config still carrying the removed key fails closed."""
    repo = _repo(tmp_path / "repo", config={"task_backend": "git-refs"})
    queue = repo / ".agents" / "aet-queue"

    monkeypatch.chdir(repo)
    with pytest.raises(LegacyTaskBackendError) as excinfo:
        create_backend(
            queue_file=str(queue), history_file=str(repo / ".agents" / "h.jsonl")
        )

    assert "migration" in str(excinfo.value).lower()


def test_root_discovery_invokes_no_git_subprocess(tmp_path, monkeypatch):
    """Config resolution runs on the read path, which must not shell out to git."""
    repo = _repo(tmp_path / "repo")
    queue = repo / ".agents" / "aet-queue"
    queue.write_text("[]", encoding="utf-8")

    calls: list[list[str]] = []
    real_run = subprocess.run

    def recording_run(cmd, *args, **kwargs):
        calls.append(list(cmd) if isinstance(cmd, (list, tuple)) else [str(cmd)])
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", recording_run)
    assert queue_repo_root(str(queue)) == str(repo)
    assert not [c for c in calls if c and c[0] == "git"], (
        f"root discovery shelled out to git: {calls}"
    )


def test_root_discovery_walks_up_from_a_missing_directory(tmp_path):
    """A queue path whose directory does not exist yet still resolves its repo."""
    repo = _repo(tmp_path / "repo")
    queue = repo / "not" / "created" / "yet" / "q.json"

    assert queue_repo_root(str(queue)) == str(repo)


def test_root_discovery_returns_none_outside_a_repository(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()

    assert queue_repo_root(str(outside / "q.json")) is None
