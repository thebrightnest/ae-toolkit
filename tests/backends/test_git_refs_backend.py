"""Integration tests for the git-refs task backend.

These tests exercise the backend against real (temporary) git repositories,
matching the style of ``tests/test_orchestrator_backend.py``. Refs are read
back both through the backend's public interface and, where it proves a
property, through raw ``git`` plumbing.
"""

from __future__ import annotations

import json
import multiprocessing
import subprocess
from pathlib import Path

import pytest

from aet.backends.git_refs_backend import (
    ENVELOPE_REF,
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


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    r = _init_repo(tmp_path / "repo")
    monkeypatch.chdir(r)
    return r


def _backend() -> GitRefsBackend:
    return GitRefsBackend(
        queue_file=".agents/work-queue.json",
        history_file=".agents/work-history.jsonl",
    )


def _task(task_id: str, **fields) -> dict:
    task = {"id": task_id, "state": "ready", "title": f"task {task_id}"}
    task.update(fields)
    return task


def _by_id(tasks: list[dict]) -> dict[str, dict]:
    return {t["id"]: t for t in tasks}


def test_state_roundtrip_via_refs(repo: Path) -> None:
    backend = _backend()
    queue = [
        _task(
            "frh-13-git-refs-backend-core",
            history=[
                {"from": None, "to": "planned", "at": "2026-07-09T00:00:00Z", "by": "test"},
                {"from": "planned", "to": "ready", "at": "2026-07-09T01:00:00Z", "by": "test"},
            ],
        ),
        _task("frh-14-git-refs-wiring", state="planned"),
    ]

    backend.save(queue)
    loaded = backend.load()

    assert _by_id(loaded["queue"]) == _by_id(queue)
    # History entries survive the round trip verbatim.
    assert (
        _by_id(loaded["queue"])["frh-13-git-refs-backend-core"]["history"]
        == queue[0]["history"]
    )
    # Each live task is backed by a ref under refs/aet/tasks/*.
    refs = _git(repo, "for-each-ref", "--format=%(refname)", TASKS_REF_PREFIX).stdout
    assert "refs/aet/tasks/frh-13-git-refs-backend-core" in refs
    assert "refs/aet/tasks/frh-14-git-refs-wiring" in refs


def test_save_prunes_refs_for_sealed_tasks(repo: Path) -> None:
    backend = _backend()
    backend.save([_task("keep-me"), _task("seal-me")])
    assert _by_id(backend.load()["queue"]).keys() == {"keep-me", "seal-me"}

    # ``seal-me`` leaves the live queue -> its ref must be pruned.
    backend.save([_task("keep-me")])

    loaded = backend.load()
    assert _by_id(loaded["queue"]).keys() == {"keep-me"}
    refs = _git(repo, "for-each-ref", "--format=%(refname)", TASKS_REF_PREFIX).stdout
    assert "refs/aet/tasks/keep-me" in refs
    assert "refs/aet/tasks/seal-me" not in refs


def test_wrapper_envelope_roundtrip(repo: Path) -> None:
    backend = _backend()
    wrapper = {
        "source_prd": "docs/prds/fable-review-hardening-prd.md",
        "queue_updated_at": "2026-07-10T00:00:00Z",
    }
    backend.save([_task("frh-13-git-refs-backend-core")], wrapper=wrapper)

    # Envelope is stored as a blob at the meta ref. Alongside the caller
    # metadata it carries the tamper-evidence stamp (chained content hash).
    sha = _git(repo, "rev-parse", "--verify", "-q", ENVELOPE_REF).stdout.strip()
    assert sha
    stored = json.loads(_git(repo, "cat-file", "-p", sha).stdout)
    assert {k: stored[k] for k in wrapper} == wrapper
    assert "content_hash" in stored
    assert "prev_content_hash" in stored

    # A fresh instance re-reads the envelope on load and preserves the caller
    # metadata on save (the stamp keys advance with the chain).
    again = _backend()
    again.load()
    again.save([_task("frh-13-git-refs-backend-core")])
    sha2 = _git(repo, "rev-parse", "--verify", "-q", ENVELOPE_REF).stdout.strip()
    stored2 = json.loads(_git(repo, "cat-file", "-p", sha2).stdout)
    assert {k: stored2[k] for k in wrapper} == wrapper


def test_refs_visible_from_second_worktree(repo: Path) -> None:
    # Second working tree sharing the same object database and ref namespace.
    wt2 = repo.parent / "wt2"
    _git(repo, "worktree", "add", "-q", "-b", "wt2-branch", str(wt2))
    (wt2 / ".agents").mkdir(parents=True, exist_ok=True)

    wt2_backend = GitRefsBackend(
        queue_file=str(wt2 / ".agents" / "work-queue.json"),
        history_file=str(wt2 / ".agents" / "work-history.jsonl"),
    )
    wt2_backend.save([_task("frh-13-git-refs-backend-core", title="from-wt2")])

    # The ref written from wt2 is readable from the original worktree.
    primary = _backend()
    loaded = primary.load()
    assert _by_id(loaded["queue"])["frh-13-git-refs-backend-core"]["title"] == "from-wt2"


def _concurrent_worker(repo_root: str, task_id: str, marker: str) -> None:
    """Load the shared queue, update one disjoint task, and save it back.

    Runs in a child process. Reconstructs the backend from ``repo_root`` so it
    is independent of the parent's interpreter state.
    """
    from aet.backends.git_refs_backend import GitRefsBackend as _Backend  # noqa: E402

    backend = _Backend(
        queue_file=str(Path(repo_root) / ".agents" / "work-queue.json"),
        history_file=str(Path(repo_root) / ".agents" / "work-history.jsonl"),
    )
    data = backend.load()
    queue = data["queue"]
    for task in queue:
        if task.get("id") == task_id:
            task["marker"] = marker
    backend.save(queue)


def test_concurrent_saves_of_different_tasks_lose_nothing(repo: Path) -> None:
    backend = _backend()
    backend.save([_task("task-a"), _task("task-b")])

    ctx = multiprocessing.get_context("fork")
    workers = [
        ctx.Process(target=_concurrent_worker, args=(str(repo), "task-a", "alpha")),
        ctx.Process(target=_concurrent_worker, args=(str(repo), "task-b", "beta")),
    ]
    for w in workers:
        w.start()
    for w in workers:
        w.join(timeout=30)
    for w in workers:
        assert w.exitcode == 0, f"worker exited with {w.exitcode}"

    final = _by_id(_backend().load()["queue"])
    assert final["task-a"]["marker"] == "alpha"
    assert final["task-b"]["marker"] == "beta"


def test_clear_error_outside_git_repo(tmp_path: Path) -> None:
    not_a_repo = tmp_path / "plain"
    (not_a_repo / ".agents").mkdir(parents=True, exist_ok=True)

    with pytest.raises(RuntimeError, match="not inside a git repository|not a git"):
        GitRefsBackend(
            queue_file=str(not_a_repo / ".agents" / "work-queue.json"),
            history_file=str(not_a_repo / ".agents" / "work-history.jsonl"),
        )
