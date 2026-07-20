"""Tests for git-refs tamper-evidence (ewl-05).

frh-17 gave the JSON backend a tamper-evident envelope (a monotonic revision +
content hash over the tasks); this suite covers the git-refs equivalent. Each
save recomputes a chained ``content_hash`` over the prior hash plus the current
task-ref set (task ids + their blob OIDs) and stamps it into the envelope blob
at ``refs/aet/meta/queue``. The read path recomputes the expected hash from the
live refs and compares: mutating paths fail closed, read-only paths warn and
continue, and legacy unstamped data is accepted and stamped on the next write.

These tests exercise the backend against real (temporary) git repositories,
matching the style of ``tests/test_git_refs_backend.py``. Out-of-band edits are
performed with raw ``git`` plumbing, exactly as a hand-edit would be.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

from aet.backends.git_refs_backend import (
    ENVELOPE_REF,
    TASKS_REF_PREFIX,
    GitRefsBackend,
    GitRefsIntegrityError,
)

_AET_STATE_PY = Path(__file__).parent.parent / "aet-work" / "bin" / "aet-state"
_spec = importlib.util.spec_from_loader(
    "aet_state_tamper",
    importlib.machinery.SourceFileLoader("aet_state_tamper", str(_AET_STATE_PY)),
)
aet_state = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(aet_state)

_STATUS_PY = Path(__file__).parent.parent / "aet-work" / "bin" / "status"
_status_spec = importlib.util.spec_from_loader(
    "aet_status_tamper",
    importlib.machinery.SourceFileLoader("aet_status_tamper", str(_STATUS_PY)),
)
status_bin = importlib.util.module_from_spec(_status_spec)
_status_spec.loader.exec_module(status_bin)


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


def _read_envelope(repo: Path) -> dict:
    """Read the envelope blob at the meta ref via raw git plumbing."""
    sha = _git(repo, "rev-parse", "--verify", "-q", ENVELOPE_REF).stdout.strip()
    if not sha:
        return {}
    return json.loads(_git(repo, "cat-file", "-p", sha).stdout)


def _write_blob(repo: Path, data: bytes) -> str:
    """Write a blob out-of-band and return its OID (raw git plumbing)."""
    result = subprocess.run(
        ["git", "-C", str(repo), "hash-object", "-w", "--stdin"],
        input=data,
        capture_output=True,
    )
    result.check_returncode()
    return result.stdout.decode().strip()


def _rewrite_task_ref(repo: Path, task_id: str, new_task: dict) -> None:
    """Hand-edit a task ref out-of-band: point it at a new blob via raw git."""
    oid = _write_blob(repo, json.dumps(new_task).encode("utf-8"))
    _git(repo, "update-ref", TASKS_REF_PREFIX + task_id, oid)


def _rewrite_envelope(repo: Path, new_envelope: dict) -> None:
    """Hand-edit the envelope blob out-of-band via raw git plumbing."""
    oid = _write_blob(repo, json.dumps(new_envelope).encode("utf-8"))
    _git(repo, "update-ref", ENVELOPE_REF, oid)


def _write_git_refs_config(repo: Path) -> None:
    (repo / ".agents" / "aet-work.json").write_text(
        json.dumps({"task_backend": "git-refs"}), encoding="utf-8"
    )


def test_clean_chain_round_trip_no_false_positive(repo: Path) -> None:
    """A clean save/load round trip verifies without a false positive."""
    backend = _backend()
    backend.save([_task("task-a"), _task("task-b")])

    # The first save stamps the envelope with a chained content_hash.
    env = _read_envelope(repo)
    assert "content_hash" in env

    # A fresh load verifies the chain and does not raise.
    again = _backend()
    data = again.load()
    assert _by_id(data["queue"]).keys() == {"task-a", "task-b"}

    # A second save advances the chain; the next load still verifies cleanly.
    again.save([_task("task-a"), _task("task-b"), _task("task-c")])
    third = _backend()
    data = third.load()
    assert _by_id(data["queue"]).keys() == {"task-a", "task-b", "task-c"}


def test_hand_edited_task_ref_detected_on_next_read(repo: Path) -> None:
    """A task ref repointed out-of-band is detected on the next verified read."""
    backend = _backend()
    backend.save([_task("task-a"), _task("task-b")])

    # Hand-edit a task ref: point it at a different blob outside the backend.
    _rewrite_task_ref(
        repo, "task-a", {"id": "task-a", "state": "in_progress", "tampered": True}
    )

    with pytest.raises(GitRefsIntegrityError):
        _backend().load()


def test_hand_edited_envelope_blob_detected_on_next_read(repo: Path) -> None:
    """An envelope blob rewritten out-of-band is detected on the next read."""
    backend = _backend()
    backend.save([_task("task-a")])

    # Hand-edit the envelope: replace the stamped hash with a bogus one while
    # leaving the (now-stale) prev pointer in place.
    env = _read_envelope(repo)
    env["content_hash"] = "0" * 64
    _rewrite_envelope(repo, env)

    with pytest.raises(GitRefsIntegrityError):
        _backend().load()


def test_legacy_unstamped_data_accepted_and_stamped_on_next_write(
    repo: Path,
) -> None:
    """Legacy git-refs data (no stamp) is accepted, then stamped on next write."""
    backend = _backend()
    backend.save([_task("task-a")])

    # Simulate pre-ewl-05 data: strip the stamp from the envelope out-of-band.
    env = _read_envelope(repo)
    env.pop("content_hash", None)
    env.pop("prev_content_hash", None)
    _rewrite_envelope(repo, env)

    # A verified read accepts the unstamped envelope (nothing to verify).
    data = _backend().load()
    assert _by_id(data["queue"]).keys() == {"task-a"}

    # The next write stamps the envelope.
    writer = _backend()
    writer.load()
    writer.save([_task("task-a")])
    assert "content_hash" in _read_envelope(repo)


def test_seal_restamps_envelope_no_false_positive(repo: Path) -> None:
    """Sealing a task drops its ref and restamps, so the next read is clean."""
    backend = _backend()
    backend.save([_task("task-a"), _task("task-b")])

    backend.seal("task-a", ".agents/work-history.jsonl")

    # The sealed task's ref is gone and the envelope was restamped to cover the
    # reduced manifest, so a fresh verified read does not raise.
    loaded = _backend().load()
    assert _by_id(loaded["queue"]).keys() == {"task-b"}


# ---------------------------------------------------------------------------
# Routing: mutating paths fail closed, read-only paths warn and continue.
# Both go through the shared ``aet-state`` fail-closed/warn-and-continue
# routing, which catches the integrity error without any aet-state change
# because ``GitRefsIntegrityError`` subclasses ``QueueIntegrityError``.
# ---------------------------------------------------------------------------


def _seed_git_refs_queue(repo: Path, task: dict) -> str:
    """Configure the repo for the git-refs backend and seed one task."""
    _write_git_refs_config(repo)
    _backend().save([task])
    return str(repo / ".agents" / "work-queue.json")


def test_mutating_path_fails_closed_on_integrity_mismatch(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """A mutating command refuses cleanly (no traceback) on a tampered queue."""
    queue_file = _seed_git_refs_queue(repo, _task("task-a", state="ready"))
    _rewrite_task_ref(repo, "task-a", {"id": "task-a", "state": "in_progress"})

    monkeypatch.setattr(
        sys,
        "argv",
        ["aet-state", "transition", "task-a", "ready", "in_progress", queue_file],
    )
    rc = aet_state.main()

    err = capsys.readouterr().err
    assert rc == 1
    assert "modified outside aet state" in err
    assert "aet state audit" in err
    assert "Traceback" not in err


def test_read_only_path_warns_and_continues_on_integrity_mismatch(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """A read-only command warns but still reports from the unverified data."""
    plan = repo / "docs" / "plans" / "task-a.md"
    plan.parent.mkdir(parents=True, exist_ok=True)
    plan.write_text("# task-a\n", encoding="utf-8")
    queue_file = _seed_git_refs_queue(
        repo, _task("task-a", state="ready", plan_file=str(plan))
    )
    _rewrite_task_ref(
        repo, "task-a", {"id": "task-a", "state": "in_progress", "plan_file": str(plan)}
    )

    monkeypatch.setattr(sys, "argv", ["aet-state", "audit", queue_file])
    rc = aet_state.main()

    captured = capsys.readouterr()
    assert rc == 0
    assert "integrity check failed" in captured.err
    results = json.loads(captured.out)
    assert "task-a" in results


def test_status_read_only_warns_and_reports_tampered_data(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """`aet status` warns and still surfaces the compromised task, not an empty queue.

    The git-refs backend keeps no ``work-queue.json``; recovering through the
    JSON reader would return ``[]`` and hide the very tasks status exists to
    show. The recovery must go through the backend abstraction so the tampered
    task is reported with its (unverified) state.
    """
    plan = repo / "docs" / "plans" / "task-a.md"
    plan.parent.mkdir(parents=True, exist_ok=True)
    plan.write_text("# task-a\n", encoding="utf-8")
    queue_file = _seed_git_refs_queue(
        repo, _task("task-a", state="ready", plan_file=str(plan))
    )
    _rewrite_task_ref(
        repo, "task-a", {"id": "task-a", "state": "in_progress", "plan_file": str(plan)}
    )

    monkeypatch.setattr(
        sys,
        "argv",
        ["status", "--queue-file", queue_file, "--plans-dir", "docs/plans", "--json"],
    )
    rc = status_bin.main()

    captured = capsys.readouterr()
    assert rc == 0
    assert "read-only status continues with unverified data" in captured.err
    projection = json.loads(captured.out)
    tasks = {t["id"]: t for t in projection["tasks"]}
    assert tasks["task-a"]["state"] == "in_progress"
    assert projection["summary"] == {"in_progress": 1}
