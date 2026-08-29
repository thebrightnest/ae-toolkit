"""Tests for the hybrid liveness probes and run liveness predicate (R-1, R-2)."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from aet.liveness import (
    HybridLiveness,
    ProcessTreeLiveness,
    RunLogLiveness,
    is_run_alive,
    process_start_time,
)

_SLEEP_HELPER = (Path(__file__).parents[1] / "fixtures" / "sleep_until_signaled.py").resolve()


def _parent_with_child_script(duration: float) -> str:
    """Return Python source that spawns a sleeper child and then waits."""
    return (
        "import subprocess, sys, time\n"
        f"child = subprocess.Popen([sys.executable, '{_SLEEP_HELPER}', '{duration}'])\n"
        f"time.sleep({duration})\n"
    )


class TestProcessTreeLiveness:
    """ProcessTreeLiveness reports whether a pid has active descendants."""

    def test_alive_when_descendant_running(self):
        """A process with a live child is process-tree alive."""
        with subprocess.Popen(
            [sys.executable, "-c", _parent_with_child_script(10.0)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ) as parent:
            # Give the parent a moment to spawn its child.
            time.sleep(0.5)
            probe = ProcessTreeLiveness(parent.pid)
            assert probe.is_alive() is True

    def test_not_alive_after_process_exits(self):
        """A dead pid is not process-tree alive, even if its child still runs."""
        with subprocess.Popen(
            [sys.executable, "-c", _parent_with_child_script(1.0)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ) as parent:
            parent.wait(timeout=5)

        # The child may outlive the parent, but the probe is keyed on the parent.
        assert ProcessTreeLiveness(parent.pid).is_alive() is False

    def test_not_alive_for_nonexistent_pid(self):
        """A pid that never existed is not alive."""
        # PIDs are capped at a system max; this value is extremely unlikely to exist.
        probe = ProcessTreeLiveness(9999999)
        assert probe.is_alive() is False


class TestRunLogLiveness:
    """RunLogLiveness reports whether watched files have been written recently."""

    def test_alive_after_file_write(self, tmp_path: Path):
        """A watched file that grows or changes mtime keeps the probe alive."""
        log = tmp_path / "run.log"
        log.write_text("initial", encoding="utf-8")
        probe = RunLogLiveness(log)

        # First observation establishes the baseline and reports alive.
        assert probe.is_alive() is True

        # No further writes means the signal goes stale.
        time.sleep(0.05)
        assert probe.is_alive() is False

        log.write_text("updated", encoding="utf-8")
        assert probe.is_alive() is True


class TestHybridLiveness:
    """HybridLiveness is alive when either process-tree or run-log is alive."""

    def test_alive_when_run_log_alive(self, tmp_path: Path):
        """A dead process tree is kept alive by fresh file writes."""
        log = tmp_path / "run.log"
        log.write_text("x", encoding="utf-8")
        probe = HybridLiveness(9999999, [log])
        assert probe.is_alive() is True

    def test_dead_when_both_signals_stale(self, tmp_path: Path):
        """When the process tree is gone and files are stale, the probe is dead."""
        log = tmp_path / "run.log"
        log.write_text("x", encoding="utf-8")
        probe = HybridLiveness(9999999, [log])
        probe.is_alive()  # establish baseline
        time.sleep(0.05)
        assert probe.is_alive() is False

    def test_alive_when_process_tree_alive(self):
        """A live process tree keeps the probe alive even with no run-log files."""
        with subprocess.Popen(
            [sys.executable, "-c", _parent_with_child_script(10.0)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ) as parent:
            time.sleep(0.5)
            probe = HybridLiveness(parent.pid, [])
            assert probe.is_alive() is True


class TestProcessStartTime:
    """Tests for process_start_time reader."""

    def test_process_start_time_current_process(self):
        """Current process start time is readable and precedes current time."""
        st = process_start_time(os.getpid())
        assert st is not None
        assert isinstance(st, float)
        assert st <= time.time() + 1.0

    def test_process_start_time_nonexistent_pid(self):
        """Nonexistent PID returns None."""
        assert process_start_time(99999999) is None

    def test_process_start_time_invalid_pid(self):
        """Invalid PID returns None."""
        assert process_start_time(-1) is None
        assert process_start_time(0) is None

    def test_process_start_time_ps_fallback(self):
        """When /proc is not available, ps fallback parses correctly."""
        with patch("os.path.isdir", return_value=False):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value.returncode = 0
                mock_run.return_value.stdout = "Sat Aug 29 15:20:46 2026\n"
                st = process_start_time(1234)
                assert st is not None
                expected_dt = datetime.strptime("Sat Aug 29 15:20:46 2026", "%a %b %d %H:%M:%S %Y")
                assert st == expected_dt.astimezone().timestamp()

    def test_process_start_time_unreadable(self):
        """When both /proc and ps fail, returns None."""
        with patch("os.path.isdir", return_value=False):
            with patch("subprocess.run", side_effect=OSError):
                assert process_start_time(1234) is None


class TestRunLivenessPredicate:
    """Unit tests for the run-liveness predicate (R-1, R-2)."""

    def test_returncode_present_settles_dead(self, tmp_path: Path):
        """A recorded returncode means the run is not alive."""
        # Directly passed returncode
        assert is_run_alive(pid=os.getpid(), returncode=0) is False
        assert is_run_alive(pid=os.getpid(), returncode=1) is False

        # Returncode file in run_dir
        rdir = tmp_path / "run-1"
        rdir.mkdir()
        (rdir / "pid").write_text(str(os.getpid()), encoding="utf-8")
        (rdir / "returncode").write_text("0", encoding="utf-8")
        assert is_run_alive(rdir) is False

    def test_pid_absent_is_dead(self, tmp_path: Path):
        """A nonexistent or dead PID is not alive."""
        assert is_run_alive(pid=99999999) is False
        assert is_run_alive(pid=None) is False

        rdir = tmp_path / "run-no-pid"
        rdir.mkdir()
        assert is_run_alive(rdir) is False

    def test_pid_held_by_recorded_process_is_alive(self, tmp_path: Path):
        """PID held by process whose start time <= started is alive."""
        started = datetime.now(timezone.utc).isoformat()
        current_pid = os.getpid()

        assert is_run_alive(pid=current_pid, started=started) is True

        rdir = tmp_path / "run-live"
        rdir.mkdir()
        (rdir / "pid").write_text(str(current_pid), encoding="utf-8")
        (rdir / "started").write_text(started, encoding="utf-8")
        assert is_run_alive(rdir) is True

    def test_pid_held_by_later_started_process_is_dead(self, tmp_path: Path):
        """PID held by a process started later than recorded started timestamp is not alive."""
        # A past timestamp from 2020 means current process started much later
        past_started = "2020-01-01T00:00:00Z"
        current_pid = os.getpid()

        assert is_run_alive(pid=current_pid, started=past_started) is False

        rdir = tmp_path / "run-recycled"
        rdir.mkdir()
        (rdir / "pid").write_text(str(current_pid), encoding="utf-8")
        (rdir / "started").write_text(past_started, encoding="utf-8")
        assert is_run_alive(rdir) is False

    def test_unreadable_start_time_resolves_live_with_diagnostic(self, capsys):
        """When start time is unreadable, predicate resolves live and emits diagnostic."""
        current_pid = os.getpid()
        with patch("aet.liveness.process_start_time", return_value=None):
            assert is_run_alive(pid=current_pid, started="2020-01-01T00:00:00Z") is True

        captured = capsys.readouterr()
        assert f"Could not read start time for PID {current_pid}" in captured.err
