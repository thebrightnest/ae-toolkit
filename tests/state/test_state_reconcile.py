"""Tests for the ``aet state reconcile`` command.

The command reports local ``refs/aet/tasks/*`` refs that have a tombstone on
origin but not locally, and removes them only when asked. Genuinely unpushed
local tasks are reported as kept, never removed.
"""

from __future__ import annotations

import argparse
import importlib.machinery
import importlib.util
import io
import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

_AET_STATE_PY = Path(__file__).parents[2] / "src" / "aet" / "cli" / "aet_state.py"
_spec = importlib.util.spec_from_loader(
    "aet_state", importlib.machinery.SourceFileLoader("aet_state", str(_AET_STATE_PY))
)
aet_state = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(aet_state)

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
    (path / ".agents" / "aet-config.json").write_text(
        json.dumps({}), encoding="utf-8"
    )
    (path / "README.md").write_text("# test\n", encoding="utf-8")
    _git(path, "add", ".")
    _git(path, "commit", "-q", "-m", "initial")
    return path


def _task(task_id: str, **fields) -> dict:
    task = {"id": task_id, "state": "ready", "title": f"task {task_id}"}
    task.update(fields)
    return task


def _backend(repo: Path):
    from aet.backends.git_refs_backend import GitRefsBackend

    return GitRefsBackend(
        queue_file=str(repo / ".agents" / "aet-queue"),
        history_file=str(repo / ".agents" / "work-history.jsonl"),
    )


def _clone_origin(origin: Path, clone: Path) -> None:
    _git(clone.parent, "clone", "-q", str(origin), str(clone))
    (clone / ".agents").mkdir(parents=True, exist_ok=True)
    (clone / ".agents" / "aet-config.json").write_text(
        json.dumps({}), encoding="utf-8"
    )
    _git(clone, "config", "user.email", "test@example.com")
    _git(clone, "config", "user.name", "Test User")


def _has_task_ref(repo: Path, task_id: str) -> bool:
    result = _git(
        repo,
        "rev-parse",
        "--verify",
        "-q",
        f"refs/aet/tasks/{task_id}",
        check=False,
    )
    return result.returncode == 0


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    r = _init_repo(tmp_path / "repo")
    monkeypatch.chdir(r)
    return r


def test_reconcile_dry_run_reports_stranded_and_keeps_unpushed(repo: Path) -> None:
    """Dry-run names the stranded ref, names the kept unpushed task, and does not mutate."""
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
    other_backend.seal(
        "stranded", history_file=str(other / ".agents" / "work-history.jsonl")
    )
    assert other_backend.push() is True

    args = argparse.Namespace(
        command="reconcile",
        queue=str(repo / ".agents" / "aet-queue"),
        apply=False,
        force=False,
    )
    stdout = io.StringIO()
    with patch.object(aet_state.sys, "stdout", stdout):
        rc = aet_state.cmd_reconcile(args)

    assert rc == 0
    output = stdout.getvalue()
    assert "stranded" in output
    assert "local-only" in output
    assert _has_task_ref(repo, "stranded") is True
    assert _has_task_ref(repo, "local-only") is True


def test_reconcile_apply_removes_only_stranded_refs(repo: Path) -> None:
    """With --apply, stranded refs are deleted and unpushed local tasks survive."""
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
    other_backend.seal(
        "stranded", history_file=str(other / ".agents" / "work-history.jsonl")
    )
    assert other_backend.push() is True

    args = argparse.Namespace(
        command="reconcile",
        queue=str(repo / ".agents" / "aet-queue"),
        apply=True,
        force=False,
    )
    rc = aet_state.cmd_reconcile(args)

    assert rc == 0
    assert _has_task_ref(repo, "stranded") is False
    assert _has_task_ref(repo, "local-only") is True


def test_reconcile_no_remote_reports_nothing_to_do(repo: Path) -> None:
    """With no remote there are no origin counterparts to compare against."""
    backend = _backend(repo)
    backend.save([_task("offline")])

    args = argparse.Namespace(
        command="reconcile",
        queue=str(repo / ".agents" / "aet-queue"),
        apply=False,
        force=False,
    )
    stdout = io.StringIO()
    with patch.object(aet_state.sys, "stdout", stdout):
        rc = aet_state.cmd_reconcile(args)

    assert rc == 0
    assert "No stranded" in stdout.getvalue() or "nothing" in stdout.getvalue().lower()


def test_reconcile_refuses_non_git_refs_backend() -> None:
    """The command is only meaningful for the git-refs backend."""
    args = argparse.Namespace(
        command="reconcile",
        queue=".agents/aet-queue",
        apply=False,
        force=False,
    )
    stderr = io.StringIO()
    with patch.object(aet_state, "make_backend", return_value=object()):
        with patch.object(aet_state.sys, "stderr", stderr):
            rc = aet_state.cmd_reconcile(args)

    assert rc == 1
    assert "git-refs" in stderr.getvalue()
