"""Regression tests for lease reclamation under recycled or dead PIDs (R-2)."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from aet.queue import LeaseHeldError, acquire_lease, check_lease, lease_path, read_lease


def test_lease_reclaimed_when_pid_recycled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
):
    """A lease left by a run whose PID was recycled by a later process is reclaimed without --force."""
    monkeypatch.delenv("AET_RUN_ID", raising=False)
    qf = tmp_path / ".agents" / "aet-queue"
    qf.parent.mkdir(parents=True, exist_ok=True)
    lp = lease_path(str(qf))

    # Record a lease from an earlier time with the current process's PID
    past_time = "2026-08-20T10:00:00+00:00"
    current_pid = os.getpid()
    Path(lp).write_text(
        json.dumps({
            "run_id": "stale-run-recycled-pid",
            "pid": current_pid,
            "started_at": past_time,
        }),
        encoding="utf-8",
    )

    # Current process started after 2026-08-20, so the predicate detects a recycled PID.
    # check_lease must reclaim without raising LeaseHeldError.
    check_lease(str(qf))

    captured = capsys.readouterr()
    assert "stale" in captured.err.lower()
    assert not Path(lp).exists()


def test_lease_reclaimed_when_run_directory_has_returncode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
):
    """A lease whose run directory has recorded a returncode is reclaimed without --force."""
    monkeypatch.delenv("AET_RUN_ID", raising=False)
    qf = tmp_path / ".agents" / "aet-queue"
    runs_dir = tmp_path / ".agents" / "runs" / "finished-run"
    runs_dir.mkdir(parents=True, exist_ok=True)
    (runs_dir / "pid").write_text(str(os.getpid()), encoding="utf-8")
    (runs_dir / "started").write_text(datetime.now(timezone.utc).isoformat(), encoding="utf-8")
    (runs_dir / "returncode").write_text("0\n", encoding="utf-8")

    lp = lease_path(str(qf))
    Path(lp).write_text(
        json.dumps({
            "run_id": "finished-run",
            "pid": os.getpid(),
            "started_at": datetime.now(timezone.utc).isoformat(),
        }),
        encoding="utf-8",
    )

    check_lease(str(qf))

    captured = capsys.readouterr()
    assert "stale" in captured.err.lower()
    assert not Path(lp).exists()


def test_acquire_lease_succeeds_over_recycled_pid_lease(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """acquire_lease without force succeeds when incumbent PID was recycled."""
    monkeypatch.delenv("AET_RUN_ID", raising=False)
    qf = tmp_path / ".agents" / "aet-queue"
    qf.parent.mkdir(parents=True, exist_ok=True)
    lp = lease_path(str(qf))

    # Incumbent lease with past started_at timestamp
    Path(lp).write_text(
        json.dumps({
            "run_id": "old-run",
            "pid": os.getpid(),
            "started_at": "2026-08-01T00:00:00Z",
        }),
        encoding="utf-8",
    )

    new_lease = acquire_lease(str(qf), "new-run", force=False)
    assert new_lease["run_id"] == "new-run"
    assert read_lease(str(qf))["run_id"] == "new-run"


def test_check_lease_refuses_when_owning_run_is_live(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """A truly live lease held by another run is not reclaimed and raises LeaseHeldError."""
    monkeypatch.delenv("AET_RUN_ID", raising=False)
    qf = tmp_path / ".agents" / "aet-queue"
    qf.parent.mkdir(parents=True, exist_ok=True)
    lp = lease_path(str(qf))

    # Far future timestamp means process start time <= recorded started_at
    future_time = "2099-01-01T00:00:00Z"
    Path(lp).write_text(
        json.dumps({
            "run_id": "live-foreign-run",
            "pid": os.getpid(),
            "started_at": future_time,
        }),
        encoding="utf-8",
    )

    with pytest.raises(LeaseHeldError) as exc_info:
        check_lease(str(qf))
    assert exc_info.value.run_id == "live-foreign-run"
    assert Path(lp).exists()
