"""Config and store must be anchored to the same repository.

`create_backend` used to resolve the in-tree config against the root discovered
from the process cwd while handing the queue path to whichever backend that
config named. When the two disagreed — a project config in one tree, a queue
outside it — the backend was selected by repository A and rooted in repository B,
and the mismatch escaped as an uncaught RuntimeError from the backend's own
discovery. See docs/bugs/ for the report.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from aet.backends.factory import (
    QueueOutsideRepositoryError,
    _queue_repo_root,
    create_backend,
)
from aet.backends.git_refs_backend import GitRefsBackend
from aet.backends.json_backend import JsonBackend


def _repo(root: Path, backend: str | None = None) -> Path:
    """Create a real git repo at ``root``, optionally with a project config."""
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    agents = root / ".agents"
    agents.mkdir(exist_ok=True)
    if backend is not None:
        (agents / "aet-config.json").write_text(
            json.dumps({"task_backend": backend}), encoding="utf-8"
        )
    return root


def test_out_of_repo_queue_does_not_inherit_another_trees_backend(tmp_path, monkeypatch):
    """The reported bug: a git-refs project config governing a queue elsewhere."""
    repo = _repo(tmp_path / "repo", backend="git-refs")
    outside = tmp_path / "outside"
    outside.mkdir()
    queue = outside / "q.json"
    queue.write_text("[]", encoding="utf-8")

    monkeypatch.chdir(repo)
    backend = create_backend(queue_file=str(queue), history_file=str(outside / "h.jsonl"))

    assert isinstance(backend, JsonBackend), (
        "config must be anchored to the queue's location, not the cwd's repository"
    )


def test_git_refs_for_an_out_of_repo_queue_is_refused_by_name(tmp_path, monkeypatch):
    """An explicit selection that cannot store anything fails with a named error."""
    outside = tmp_path / "outside"
    outside.mkdir()
    queue = outside / "q.json"
    queue.write_text("[]", encoding="utf-8")
    explicit = tmp_path / "explicit.json"
    explicit.write_text(json.dumps({"task_backend": "git-refs"}), encoding="utf-8")
    monkeypatch.setenv("AET_WORK_CONFIG", str(explicit))

    with pytest.raises(QueueOutsideRepositoryError) as excinfo:
        create_backend(queue_file=str(queue), history_file=str(outside / "h.jsonl"))

    assert str(queue) in str(excinfo.value)
    assert "not inside a git repository" in str(excinfo.value)


def test_in_repo_queue_still_selects_the_project_backend(tmp_path, monkeypatch):
    """The positive case: config and queue in one tree resolve to git-refs."""
    repo = _repo(tmp_path / "repo", backend="git-refs")
    queue = repo / ".agents" / "work-queue.json"
    queue.write_text("[]", encoding="utf-8")

    monkeypatch.chdir(repo)
    backend = create_backend(
        queue_file=str(queue), history_file=str(repo / ".agents" / "h.jsonl")
    )

    assert isinstance(backend, GitRefsBackend)


def test_root_discovery_invokes_no_git_subprocess(tmp_path, monkeypatch):
    """Config resolution runs on the read path, which must not shell out to git."""
    repo = _repo(tmp_path / "repo")
    queue = repo / ".agents" / "work-queue.json"
    queue.write_text("[]", encoding="utf-8")

    calls: list[list[str]] = []
    real_run = subprocess.run

    def recording_run(cmd, *args, **kwargs):
        calls.append(list(cmd) if isinstance(cmd, (list, tuple)) else [str(cmd)])
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", recording_run)
    assert _queue_repo_root(str(queue)) == str(repo)
    assert not [c for c in calls if c and c[0] == "git"], (
        f"root discovery shelled out to git: {calls}"
    )


def test_root_discovery_walks_up_from_a_missing_directory(tmp_path):
    """A queue path whose directory does not exist yet still resolves its repo."""
    repo = _repo(tmp_path / "repo")
    queue = repo / "not" / "created" / "yet" / "q.json"

    assert _queue_repo_root(str(queue)) == str(repo)


def test_root_discovery_returns_none_outside_a_repository(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()

    assert _queue_repo_root(str(outside / "q.json")) is None
