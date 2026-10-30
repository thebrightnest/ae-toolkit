"""Tests for ``aet run stop`` (PRD R-1, R-2, R-3, R-23)."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import pytest

from aet.cli.main import app
from tests.cli._helpers import run_typer


def _create_settling_process(run_dir: Path) -> subprocess.Popen:
    """Start a process that traps SIGTERM, writes returncode and settlement summary, then exits."""
    run_dir.mkdir(parents=True, exist_ok=True)
    log_file = run_dir / "output.log"
    pid_file = run_dir / "pid"
    started_file = run_dir / "started"

    script = f"""
import signal
import sys
import time
from pathlib import Path

run_dir = Path({str(run_dir)!r})
log_file = run_dir / "output.log"
rc_file = run_dir / "returncode"

def handle_term(signum, frame):
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(
            "\\n📋 Batch Settlement Summary:\\n"
            "   Auto-merged (0): none\\n"
            "📊 Batch complete: 0 succeeded, 0 failed (0.5s)\\n"
        )
    rc_file.write_text("0", encoding="utf-8")
    sys.exit(0)

signal.signal(signal.SIGTERM, handle_term)
while True:
    time.sleep(0.05)
"""
    proc = subprocess.Popen([sys.executable, "-c", script])
    pid_file.write_text(str(proc.pid), encoding="utf-8")
    log_file.write_text("🚀 Run started\n", encoding="utf-8")
    time.sleep(0.05)
    started_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + 5))
    started_file.write_text(started_iso, encoding="utf-8")
    return proc


def _create_stubborn_process(run_dir: Path) -> subprocess.Popen:
    """Start a process that ignores SIGTERM so it does not settle."""
    run_dir.mkdir(parents=True, exist_ok=True)
    pid_file = run_dir / "pid"
    started_file = run_dir / "started"

    script = """
import signal
import time
signal.signal(signal.SIGTERM, signal.SIG_IGN)
while True:
    time.sleep(0.05)
"""
    proc = subprocess.Popen([sys.executable, "-c", script])
    pid_file.write_text(str(proc.pid), encoding="utf-8")
    started_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + 5))
    started_file.write_text(started_iso, encoding="utf-8")
    return proc


@pytest.fixture
def repo_dir(tmp_path: Path, monkeypatch) -> Path:
    runs_dir = tmp_path / ".agents" / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(tmp_path)
    return tmp_path


class TestRunStopIntegration:
    """Integration: stopping a live run traps SIGTERM, waits for returncode, prints summary."""

    def test_stop_live_run_explicit_id(self, repo_dir: Path) -> None:
        run_id = "run-test-stop-01"
        run_dir = repo_dir / ".agents" / "runs" / run_id
        proc = _create_settling_process(run_dir)
        try:
            result = run_typer(app, ["run", "stop", run_id, "--timeout", "10"], cwd=repo_dir)
            assert result.exit_code == 0, result.output
            assert "Batch Settlement Summary" in result.output
            assert "Batch complete" in result.output
            assert (run_dir / "returncode").is_file()
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()


class TestRunStopResolution:
    """Resolution: defaults to single live run; 0 or >1 live runs exit 1 and list them."""

    def test_stop_defaults_to_single_live_run(self, repo_dir: Path) -> None:
        run_id = "run-test-single-02"
        run_dir = repo_dir / ".agents" / "runs" / run_id
        proc = _create_settling_process(run_dir)
        try:
            result = run_typer(app, ["run", "stop", "--timeout", "10"], cwd=repo_dir)
            assert result.exit_code == 0, result.output
            assert "Batch Settlement Summary" in result.output
            assert (run_dir / "returncode").is_file()
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()

    def test_stop_zero_live_runs_exits_1(self, repo_dir: Path) -> None:
        result = run_typer(app, ["run", "stop"], cwd=repo_dir)
        assert result.exit_code == 1, result.output
        assert "no live runs" in result.output.lower()

    def test_stop_multiple_live_runs_exits_1_and_lists_them(self, repo_dir: Path) -> None:
        run1 = "run-test-multi-01"
        run2 = "run-test-multi-02"
        dir1 = repo_dir / ".agents" / "runs" / run1
        dir2 = repo_dir / ".agents" / "runs" / run2
        proc1 = _create_settling_process(dir1)
        proc2 = _create_settling_process(dir2)
        try:
            result = run_typer(app, ["run", "stop"], cwd=repo_dir)
            assert result.exit_code == 1, result.output
            assert run1 in result.output
            assert run2 in result.output
        finally:
            for p in (proc1, proc2):
                if p.poll() is None:
                    p.kill()
                    p.wait()


class TestRunStopErrorConditions:
    """Error cases: unknown id, ended run, and timeout."""

    def test_unknown_run_id_exits_1(self, repo_dir: Path) -> None:
        result = run_typer(app, ["run", "stop", "run-nonexistent"], cwd=repo_dir)
        assert result.exit_code == 1, result.output
        assert "unknown run" in result.output.lower()

    def test_ended_run_exits_1(self, repo_dir: Path) -> None:
        run_id = "run-already-ended"
        run_dir = repo_dir / ".agents" / "runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "returncode").write_text("0", encoding="utf-8")
        (run_dir / "pid").write_text("99999", encoding="utf-8")

        result = run_typer(app, ["run", "stop", run_id], cwd=repo_dir)
        assert result.exit_code == 1, result.output
        assert "not alive" in result.output.lower()

    def test_stubborn_run_timeout_exits_1_with_still_live(self, repo_dir: Path) -> None:
        run_id = "run-stubborn-01"
        run_dir = repo_dir / ".agents" / "runs" / run_id
        proc = _create_stubborn_process(run_dir)
        try:
            result = run_typer(app, ["run", "stop", run_id, "--timeout", "1"], cwd=repo_dir)
            assert result.exit_code == 1, result.output
            assert "still live" in result.output.lower()
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
