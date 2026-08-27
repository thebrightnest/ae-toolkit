"""Tests for the hybrid liveness probes (R-1, R-2)."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

from aet.liveness import HybridLiveness, ProcessTreeLiveness, RunLogLiveness

_SLEEP_HELPER = Path(__file__).parents[1] / "fixtures" / "sleep_until_signaled.py"


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
            time.sleep(0.2)
            probe = ProcessTreeLiveness(parent.pid)
            assert probe.is_alive() is True

    def test_not_alive_after_process_exits(self):
        """A dead pid is not process-tree alive, even if its child still runs."""
        with subprocess.Popen(
            [sys.executable, "-c", _parent_with_child_script(1.0)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ) as parent:
            time.sleep(0.2)
            probe = ProcessTreeLiveness(parent.pid)
            assert probe.is_alive() is True
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
            [sys.executable, "-c", _parent_with_child_script(2.0)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ) as parent:
            time.sleep(0.2)
            probe = HybridLiveness(parent.pid, [])
            assert probe.is_alive() is True
