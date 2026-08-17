"""Tests for git-refs backend reconcile support.

These tests verify that the backend can compare local ``refs/aet/*`` against
``origin`` without fetching, identify refs that are stranded by the
pre-tombstone scheme, and leave genuinely unpushed local tasks alone.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from aet.backends.git_refs_backend import (
    TASKS_REF_PREFIX,
    GitRefsBackend,
)

pytestmark = pytest.mark.xdist_group("cwd")


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=check,
    )


def _init_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-q")
    _git(path, "config", "user.email", "test@example.com")
    _git(path, "config", "user.name", "Test User")
    (path / ".agents").mkdir(parents=True, exist_ok=True)
    (path / "README.md").write_text("# test\n", encoding="utf-8")
    _git(path, "add", ".")
    _git(path, "commit", "-q", "-m", "initial")
    return path


def _task(task_id: str, **fields) -> dict:
    task = {"id": task_id, "state": "ready", "title": f"task {task_id}"}
    task.update(fields)
    return task


def _backend(repo: Path) -> GitRefsBackend:
    return GitRefsBackend(
        queue_file=str(repo / ".agents" / "work-queue.json"),
        history_file=str(repo / ".agents" / "work-history.jsonl"),
    )


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    r = _init_repo(tmp_path / "repo")
    monkeypatch.chdir(r)
    return r


def _clone_origin(origin: Path, clone: Path) -> None:
    _git(clone.parent, "clone", "-q", str(origin), str(clone))
    (clone / ".agents").mkdir(parents=True, exist_ok=True)
    _git(clone, "config", "user.email", "test@example.com")
    _git(clone, "config", "user.name", "Test User")


def test_reconcile_candidates_finds_stranded_ref(repo: Path) -> None:
    """A local task ref whose sealed counterpart exists on origin is stranded."""
    origin = repo.parent / "origin"
    origin.mkdir(parents=True, exist_ok=True)
    _git(origin, "init", "--bare", "-q")
    _git(repo, "remote", "add", "origin", str(origin))

    backend = _backend(repo)
    backend.save([_task("stranded")])
    assert backend.push() is True

    # Another clone seals the task and pushes the tombstone.
    other = repo.parent / "other"
    _clone_origin(origin, other)
    other_backend = _backend(other)
    other_backend.fetch()
    other_backend.seal("stranded", history_file=str(other / ".agents" / "work-history.jsonl"))
    assert other_backend.push() is True

    # The original clone has not fetched the tombstone; reconcile must detect it.
    candidates = backend.reconcile_candidates()
    assert candidates["stranded"] == {"stranded"}
    assert candidates["unpushed"] == set()


def test_reconcile_candidates_keeps_unpushed_local_task(repo: Path) -> None:
    """A local-only task with no remote counterpart or tombstone is not stranded."""
    origin = repo.parent / "origin"
    origin.mkdir(parents=True, exist_ok=True)
    _git(origin, "init", "--bare", "-q")
    _git(repo, "remote", "add", "origin", str(origin))

    backend = _backend(repo)
    backend.save([_task("pushed")])
    assert backend.push() is True

    # Add a second task locally but do not push it.
    backend.save([_task("pushed"), _task("local-only")])

    candidates = backend.reconcile_candidates()
    assert candidates["stranded"] == set()
    assert candidates["unpushed"] == {"local-only"}


def test_reconcile_candidates_mixed_case(repo: Path) -> None:
    """One stranded ref and one unpushed local task are classified separately."""
    origin = repo.parent / "origin"
    origin.mkdir(parents=True, exist_ok=True)
    _git(origin, "init", "--bare", "-q")
    _git(repo, "remote", "add", "origin", str(origin))

    backend = _backend(repo)
    backend.save([_task("stranded")])
    assert backend.push() is True

    # Add an unpushed local task after the push to origin.
    backend.save([_task("stranded"), _task("local-only")])

    other = repo.parent / "other"
    _clone_origin(origin, other)
    other_backend = _backend(other)
    other_backend.fetch()
    other_backend.seal("stranded", history_file=str(other / ".agents" / "work-history.jsonl"))
    assert other_backend.push() is True

    candidates = backend.reconcile_candidates()
    assert candidates["stranded"] == {"stranded"}
    assert candidates["unpushed"] == {"local-only"}


def test_reconcile_candidates_no_remote_is_empty(repo: Path) -> None:
    """With no remote configured there is nothing to reconcile against."""
    backend = _backend(repo)
    backend.save([_task("offline")])

    candidates = backend.reconcile_candidates()
    assert candidates["stranded"] == set()
    assert candidates["unpushed"] == set()


def test_delete_task_ref_removes_local_ref(repo: Path) -> None:
    """The backend can delete a single local task ref."""
    backend = _backend(repo)
    backend.save([_task("gone")])

    assert backend.delete_task_ref("gone") is True
    result = _git(
        repo, "rev-parse", "--verify", "-q", TASKS_REF_PREFIX + "gone", check=False
    )
    assert result.returncode != 0


def test_delete_task_ref_returns_false_when_missing(repo: Path) -> None:
    """Deleting a non-existent local task ref is a no-op."""
    backend = _backend(repo)
    assert backend.delete_task_ref("missing") is False


def test_reconcile_candidates_sees_local_tombstone_as_known(repo: Path) -> None:
    """A local tombstone means the ref is already reconciled on this clone."""
    origin = repo.parent / "origin"
    origin.mkdir(parents=True, exist_ok=True)
    _git(origin, "init", "--bare", "-q")
    _git(repo, "remote", "add", "origin", str(origin))

    backend = _backend(repo)
    backend.save([_task("already-known")])
    assert backend.push() is True

    # Seal locally, but do not push; the local tombstone exists.
    backend.seal("already-known", history_file=str(repo / ".agents" / "work-history.jsonl"))

    candidates = backend.reconcile_candidates()
    assert candidates["stranded"] == set()
    assert candidates["unpushed"] == set()
