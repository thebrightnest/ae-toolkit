"""Tests for the queue mutation guard (run lease + tamper-evident writes)."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "aet-work" / "lib"))

from queue import (  # noqa: E402
    QueueIntegrityError,
    acquire_lease,
    check_lease,
    lease_path,
    read_queue,
    release_lease,
    write_queue,
)


def _load_bin(name: str):
    """Load an extension-less aet-work bin script as a module."""
    path = REPO_ROOT / "aet-work" / "bin" / name
    loader = SourceFileLoader(f"aet_bin_{name}", str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def _write_plan(plans_dir: Path, stem: str) -> Path:
    """Write a minimal valid plan file and return its path."""
    plans_dir.mkdir(parents=True, exist_ok=True)
    plan = plans_dir / f"{stem}.md"
    plan.write_text(
        f"---\nid: {stem}\nsize: S\n---\n\n# {stem}\n\n_Stage: plan-approved_\n",
        encoding="utf-8",
    )
    return plan


def _dead_pid() -> int:
    """Return a PID that is guaranteed not to be alive anymore."""
    proc = subprocess.Popen([sys.executable, "-c", "import sys; sys.exit(0)"])
    proc.wait()
    return proc.pid


def _clear_run_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AET_RUN_ID", raising=False)


# ---------------------------------------------------------------------------
# Run lease
# ---------------------------------------------------------------------------


def test_add_refused_while_lease_held_by_live_run(tmp_path, monkeypatch, capsys):
    """A foreign live lease makes `aet-work add` refuse before writing."""
    _clear_run_env(monkeypatch)
    qf = tmp_path / ".agents" / "work-queue.json"
    hf = tmp_path / ".agents" / "work-history.jsonl"
    qf.parent.mkdir(parents=True, exist_ok=True)
    hf.touch()
    plan = _write_plan(tmp_path / "docs" / "plans", "feat-add")

    # A live lease owned by a different run (our PID is alive, run_id is foreign).
    acquire_lease(str(qf), "foreign-run")

    add = _load_bin("add")
    rc = add.main([
        str(plan),
        "--queue-file", str(qf),
        "--history-file", str(hf),
        "--plans-dir", str(plan.parent),
        "--config", str(tmp_path / "missing-config.json"),
    ])

    assert rc == 1
    captured = capsys.readouterr()
    assert "foreign-run" in captured.err
    assert not qf.exists()  # refused before writing the queue


def test_child_with_matching_run_id_allowed(tmp_path, monkeypatch):
    """A caller whose AET_RUN_ID matches the live lease may mutate."""
    qf = tmp_path / ".agents" / "work-queue.json"
    qf.parent.mkdir(parents=True, exist_ok=True)

    acquire_lease(str(qf), "run-X")
    monkeypatch.setenv("AET_RUN_ID", "run-X")

    # Should not raise.
    check_lease(str(qf))


def test_stale_lease_dead_pid_reclaimed_with_warning(tmp_path, monkeypatch, capsys):
    """A lease whose PID is dead is reclaimed with a warning."""
    _clear_run_env(monkeypatch)
    qf = tmp_path / ".agents" / "work-queue.json"
    qf.parent.mkdir(parents=True, exist_ok=True)
    lp = lease_path(str(qf))
    Path(lp).write_text(
        json.dumps({"run_id": "dead-run", "pid": _dead_pid(), "started_at": "x"}),
        encoding="utf-8",
    )

    check_lease(str(qf))

    captured = capsys.readouterr()
    assert "stale" in captured.err.lower()
    assert not Path(lp).exists()  # reclaimed


def test_force_overrides_lease_with_warning(tmp_path, monkeypatch, capsys):
    """--force lets a mutation proceed despite a foreign live lease."""
    _clear_run_env(monkeypatch)
    qf = tmp_path / ".agents" / "work-queue.json"
    hf = tmp_path / ".agents" / "work-history.jsonl"
    qf.parent.mkdir(parents=True, exist_ok=True)
    hf.touch()
    plan = _write_plan(tmp_path / "docs" / "plans", "feat-force")

    acquire_lease(str(qf), "foreign-run")

    add = _load_bin("add")
    rc = add.main([
        str(plan),
        "--queue-file", str(qf),
        "--history-file", str(hf),
        "--plans-dir", str(plan.parent),
        "--config", str(tmp_path / "missing-config.json"),
        "--force",
    ])

    assert rc == 0
    captured = capsys.readouterr()
    assert "foreign-run" in captured.err
    assert qf.exists()  # write proceeded


def test_lease_released_on_batch_crash(tmp_path):
    """The finally path releases a held lease even when the run crashes."""
    qf = tmp_path / ".agents" / "work-queue.json"
    qf.parent.mkdir(parents=True, exist_ok=True)
    lp = lease_path(str(qf))

    acquire_lease(str(qf), "run-crash")
    assert Path(lp).exists()

    with pytest.raises(RuntimeError):
        try:
            raise RuntimeError("simulated batch crash")
        finally:
            release_lease(str(qf), "run-crash")

    assert not Path(lp).exists()


# ---------------------------------------------------------------------------
# Tamper-evident writes
# ---------------------------------------------------------------------------


def test_read_fails_closed_on_content_hash_mismatch(tmp_path):
    """Hand-editing a stamped queue makes read_queue raise QueueIntegrityError."""
    qf = tmp_path / "work-queue.json"
    write_queue(str(qf), [{"id": "t1", "state": "ready"}], wrapper={"source_prd": "x"})

    data = json.loads(qf.read_text(encoding="utf-8"))
    data["tasks"][0]["state"] = "in_progress"  # tamper
    qf.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(QueueIntegrityError):
        read_queue(str(qf))


def test_revision_increments_monotonically(tmp_path):
    """Each wrapper write bumps revision by exactly one."""
    qf = tmp_path / "work-queue.json"
    write_queue(str(qf), [{"id": "t1", "state": "ready"}], wrapper={"source_prd": "x"})
    assert json.loads(qf.read_text(encoding="utf-8"))["revision"] == 1

    queue = read_queue(str(qf))
    write_queue(str(qf), queue, wrapper={"source_prd": "x"})
    assert json.loads(qf.read_text(encoding="utf-8"))["revision"] == 2


def test_legacy_queue_without_stamp_accepted_then_stamped(tmp_path):
    """A legacy wrapper without revision/hash is read, then stamped on write."""
    qf = tmp_path / "work-queue.json"
    legacy = {"source_prd": "x", "tasks": [{"id": "t1", "state": "ready"}]}
    qf.write_text(json.dumps(legacy), encoding="utf-8")

    queue = read_queue(str(qf))  # accepted: no stamp to verify
    assert queue[0]["id"] == "t1"

    write_queue(str(qf), queue)
    data = json.loads(qf.read_text(encoding="utf-8"))
    assert data["revision"] == 1
    assert "content_hash" in data
