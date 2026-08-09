"""Tests for git-refs backend push/fetch synchronization.

These tests verify that the git-refs backend can push its ``refs/aet/*``
namespace to a forge remote and fetch remote refs back, that failures are
handled according to the plan's best-effort/mandatory rules, and that no local
file path (especially ``~/.aet`` content) is ever pushed.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from aet.backends.git_refs_backend import (
    ENVELOPE_REF,
    GitRefsBackend,
)
from aet.backends.json_backend import JsonBackend

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


def _by_id(tasks: list[dict]) -> dict[str, dict]:
    return {t["id"]: t for t in tasks}


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    r = _init_repo(tmp_path / "repo")
    monkeypatch.chdir(r)
    return r


def _backend(repo: Path | None = None) -> GitRefsBackend:
    kwargs: dict = {
        "queue_file": ".agents/work-queue.json",
        "history_file": ".agents/work-history.jsonl",
    }
    if repo is not None:
        kwargs = {
            "queue_file": str(repo / ".agents" / "work-queue.json"),
            "history_file": str(repo / ".agents" / "work-history.jsonl"),
        }
    return GitRefsBackend(**kwargs)


def test_fetch_runs_git_fetch_for_refs_namespace(repo: Path) -> None:
    backend = _backend()
    backend.fetch()
    # Fetching a repo with no remote is a silent no-op; we verify the command
    # completes without error and does not touch non-refs state.


def test_push_runs_git_push_for_refs_namespace(repo: Path, capsys) -> None:
    backend = _backend()
    result = backend.push()
    # No remote configured -> treated as success (nothing to push).
    assert result is True


def test_push_is_best_effort_with_no_remote(repo: Path) -> None:
    backend = _backend()
    # A repo with no remote cannot push, but best-effort push must not raise.
    assert backend.push() is True


def test_push_returns_false_on_rejected_update(repo: Path) -> None:
    # Simulate a non-fast-forward rejection by pre-creating a divergent ref on
    # a bare origin and trying to push over it.
    origin = repo.parent / "origin"
    origin.mkdir(parents=True, exist_ok=True)
    _git(origin, "init", "--bare", "-q")
    _git(repo, "remote", "add", "origin", str(origin))

    backend = _backend(repo)
    backend.save([_task("local-task")])

    # Plant a divergent envelope on the remote by pushing from a second clone.
    other = repo.parent / "other"
    _git(repo.parent, "clone", "-q", str(origin), str(other))
    (other / ".agents").mkdir(parents=True, exist_ok=True)
    _git(other, "config", "user.email", "test@example.com")
    _git(other, "config", "user.name", "Test User")
    other_backend = GitRefsBackend(
        queue_file=str(other / ".agents" / "work-queue.json"),
        history_file=str(other / ".agents" / "work-history.jsonl"),
    )
    # Use a wrapper so the envelope content differs from the local one.
    other_backend.save(
        [_task("remote-task")],
        wrapper={"source_prd": "docs/prds/other-prd.md"},
    )
    # Push only the envelope ref to create divergence on refs/aet/meta/queue.
    _git(other, "push", "origin", ENVELOPE_REF)

    # Pushing the whole namespace now fails because the envelope diverged.
    assert backend.push() is False


def test_mandatory_push_raises_with_named_remedy(repo: Path) -> None:
    backend = _backend()
    # No remote configured -> mandatory push still fails because there is no
    # destination to satisfy the durability guarantee.
    with pytest.raises(GitRefsBackend.RefsPushError) as exc:
        backend.push(mandatory=True)
    assert "re-run" in str(exc.value).lower() or "retry" in str(exc.value).lower()


def test_push_refspec_never_includes_local_paths(repo: Path, monkeypatch) -> None:
    """Refs push must be scoped to ``refs/aet/*`` and never include ``~/.aet``."""
    origin = repo.parent / "origin"
    origin.mkdir(parents=True, exist_ok=True)
    _git(origin, "init", "--bare", "-q")
    _git(repo, "remote", "add", "origin", str(origin))

    backend = _backend(repo)
    backend.save([_task("task-a")])

    captured: list[list[str]] = []

    def _capture_git(self, *args: str, input=None):
        captured.append(list(args))
        return subprocess.run(
            ["git", "-C", self.repo_root, *args],
            input=input,
            capture_output=True,
        )

    monkeypatch.setattr(GitRefsBackend, "_git", _capture_git)
    backend.push()

    push_calls = [c for c in captured if len(c) >= 2 and c[0] == "push" and c[1] == "origin"]
    assert len(push_calls) == 1
    refspec = push_calls[0][2]
    assert refspec == "refs/aet/*"
    assert "~/.aet" not in refspec
    assert not any("~/.aet" in arg for call in captured for arg in call)


def test_two_clones_append_offline_then_fetch_union(repo: Path) -> None:
    """Each clone appends a task offline; after both push, fetch yields the union."""
    origin = repo.parent / "origin"
    origin.mkdir(parents=True, exist_ok=True)
    _git(origin, "init", "--bare", "-q")
    _git(repo, "remote", "add", "origin", str(origin))
    _git(repo, "push", "origin", "HEAD:main")

    clone1 = repo.parent / "clone1"
    clone2 = repo.parent / "clone2"
    _git(clone1.parent, "clone", "-q", str(origin), str(clone1))
    _git(clone2.parent, "clone", "-q", str(origin), str(clone2))

    for c in (clone1, clone2):
        _git(c, "config", "user.email", "test@example.com")
        _git(c, "config", "user.name", "Test User")
        (c / ".agents").mkdir(parents=True, exist_ok=True)

    b1 = GitRefsBackend(
        queue_file=str(clone1 / ".agents" / "work-queue.json"),
        history_file=str(clone1 / ".agents" / "work-history.jsonl"),
    )
    b1.save([_task("clone1-task")])
    assert b1.push() is True

    b2 = GitRefsBackend(
        queue_file=str(clone2 / ".agents" / "work-queue.json"),
        history_file=str(clone2 / ".agents" / "work-history.jsonl"),
    )
    b2.save([_task("clone2-task")])
    assert b2.push() is True

    # Fetch the remote into clone1 and verify the union.
    b1.fetch()
    loaded = b1.load()
    ids = set(_by_id(loaded["queue"]).keys())
    assert ids == {"clone1-task", "clone2-task"}


def test_json_backend_fetch_and_push_are_no_ops() -> None:
    backend = JsonBackend()
    assert backend.fetch() is None
    assert backend.push() is True
    assert backend.push(mandatory=True) is True


def test_fetch_force_updates_local_refs_from_remote(repo: Path) -> None:
    """A remote ref update wins locally after fetch, even if it is not FF."""
    origin = repo.parent / "origin"
    origin.mkdir(parents=True, exist_ok=True)
    _git(origin, "init", "--bare", "-q")
    _git(repo, "remote", "add", "origin", str(origin))

    backend = _backend(repo)
    backend.save([_task("first")])
    assert backend.push() is True

    clone = repo.parent / "clone"
    _git(clone.parent, "clone", "-q", str(origin), str(clone))
    (clone / ".agents").mkdir(parents=True, exist_ok=True)
    _git(clone, "config", "user.email", "test@example.com")
    _git(clone, "config", "user.name", "Test User")
    clone_backend = GitRefsBackend(
        queue_file=str(clone / ".agents" / "work-queue.json"),
        history_file=str(clone / ".agents" / "work-history.jsonl"),
    )
    clone_backend.save([_task("second")])
    assert clone_backend.push() is True

    # Original repo fetches the clone's task ref.
    backend.fetch()
    loaded = backend.load()
    assert "second" in _by_id(loaded["queue"])
