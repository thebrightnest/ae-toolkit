"""Hybrid liveness probes and run-liveness predicate (R-1, R-2, R-3).

The module provides:
1. Run-liveness predicate (`is_run_alive`): verifies whether a recorded run is
   actively alive by checking returncode, PID existence, and process start time
   against recorded run start time to detect PID reuse (R-1, R-2).
2. Process start-time reader (`process_start_time`): extracts start timestamp
   via `/proc/<pid>/stat` or `ps -p <pid> -o lstart=`.
3. Orchestrator session watchdog probes (`HybridLiveness`, `ProcessTreeLiveness`,
   `RunLogLiveness`, `LivenessMonitor`): distinguishes slow-but-alive sessions
   from wedged ones (R-3).
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


def process_start_time(pid: int) -> float | None:
    """Return the process start time as UTC epoch seconds, or None if unreadable.

    Follows ``_all_processes``'s fallback shape: reads ``/proc/<pid>/stat`` field 22
    against system boot time (from ``/proc/stat``) when available, falls back to
    ``ps -p <pid> -o lstart=`` otherwise, and returns None when neither answers.
    """
    if not isinstance(pid, int) or pid <= 0:
        return None

    if os.path.isdir("/proc"):
        try:
            btime: int | None = None
            if os.path.isfile("/proc/stat"):
                with open("/proc/stat", "r", encoding="utf-8") as f:
                    for line in f:
                        if line.startswith("btime "):
                            btime = int(line.split()[1])
                            break
            if btime is not None:
                with open(f"/proc/{pid}/stat", "r", encoding="utf-8") as f:
                    content = f.read()
                rparen = content.rfind(")")
                if rparen != -1:
                    fields = content[rparen + 1 :].split()
                    starttime_ticks = int(fields[19])
                    clk_tck = (
                        os.sysconf("SC_CLK_TCK")
                        if hasattr(os, "sysconf") and "SC_CLK_TCK" in os.sysconf_names
                        else 100
                    )
                    return btime + (starttime_ticks / clk_tck)
        except (OSError, ValueError, IndexError, ZeroDivisionError):
            pass

    try:
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "lstart="],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            raw = " ".join(result.stdout.strip().split())
            dt = datetime.strptime(raw, "%a %b %d %H:%M:%S %Y")
            return dt.astimezone().timestamp()
    except (OSError, ValueError, subprocess.TimeoutExpired):
        pass

    return None


def is_run_alive(
    run_dir: str | Path | None = None,
    *,
    pid: int | None = None,
    started: str | datetime | float | int | None = None,
    returncode: int | None = None,
) -> bool:
    """Return True if a run is actively alive (R-1, R-2).

    Rules:
      1. If a returncode is recorded (either passed or in run_dir/returncode),
         the run has terminated -> return False.
      2. If pid is absent or not alive (process gone) -> return False.
      3. If the process is alive and a started timestamp is available:
         - If process start time is later than the recorded started timestamp,
           the PID has been recycled by an unrelated process -> return False.
         - If process start time is <= recorded started timestamp, the PID is
           held by the original process -> return True.
      4. If process start time is unreadable, resolve live (True) and emit a diagnostic.
    """
    if run_dir is not None:
        rdir = Path(run_dir)
        if rdir.is_dir():
            rc_file = rdir / "returncode"
            if returncode is None and rc_file.is_file():
                try:
                    returncode = int(rc_file.read_text(encoding="utf-8").strip() or "0")
                except (ValueError, OSError):
                    returncode = 0
            if pid is None:
                pid_file = rdir / "pid"
                if pid_file.is_file():
                    try:
                        pid = int(pid_file.read_text(encoding="utf-8").strip())
                    except (ValueError, OSError):
                        pid = None
            if started is None:
                started_file = rdir / "started"
                if started_file.is_file():
                    try:
                        started = started_file.read_text(encoding="utf-8").strip()
                    except OSError:
                        started = None

    if returncode is not None:
        return False

    if pid is None or not isinstance(pid, int) or pid <= 0:
        return False

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        pass

    started_ts: float | None = None
    if started is not None and started != "":
        if isinstance(started, (int, float)):
            started_ts = float(started)
        elif isinstance(started, datetime):
            dt = started if started.tzinfo is not None else started.replace(tzinfo=timezone.utc)
            started_ts = dt.timestamp()
        elif isinstance(started, str):
            try:
                raw_ts = started.strip().replace("Z", "+00:00")
                dt = datetime.fromisoformat(raw_ts)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                started_ts = dt.timestamp()
            except (ValueError, TypeError):
                started_ts = None

    if started_ts is None:
        return True

    proc_start = process_start_time(pid)
    if proc_start is None:
        print(
            f"⚠️  Could not read start time for PID {pid}; assuming process is live.",
            file=sys.stderr,
        )
        return True

    if proc_start > started_ts:
        return False

    return True


def _all_processes() -> dict[int, int]:
    """Return a mapping of ``{pid: ppid}`` for all observable processes.

    Falls back to an empty map when ``ps`` is unavailable or produces unexpected
    output, so a missing tool never crashes the watchdog.
    """
    if os.path.isdir("/proc"):
        mapping: dict[int, int] = {}
        try:
            for entry in os.scandir("/proc"):
                if not entry.name.isdigit():
                    continue
                try:
                    with open(f"/proc/{entry.name}/stat", "r") as f:
                        content = f.read()
                    rparen = content.rfind(")")
                    if rparen != -1:
                        ppid = int(content[rparen + 1 :].split()[1])
                        mapping[int(entry.name)] = ppid
                except (OSError, ValueError, IndexError):
                    continue
            if mapping:
                return mapping
        except OSError:
            pass

    try:
        result = subprocess.run(
            ["ps", "-ax", "-o", "pid=", "-o", "ppid="],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {}

    mapping = {}
    for line in result.stdout.splitlines():
        parts = line.strip().split()
        if len(parts) != 2:
            continue
        try:
            pid = int(parts[0])
            ppid = int(parts[1])
        except ValueError:
            continue
        mapping[pid] = ppid
    return mapping


def _descendant_pids(pid: int, mapping: dict[int, int] | None = None) -> set[int]:
    """Return every descendant of ``pid`` (not including ``pid`` itself)."""
    if mapping is None:
        mapping = _all_processes()
    if not mapping or pid not in mapping:
        return set()

    children: dict[int, list[int]] = {}
    for child, parent in mapping.items():
        children.setdefault(parent, []).append(child)

    descendants: set[int] = set()
    queue = list(children.get(pid, []))
    while queue:
        current = queue.pop()
        if current in descendants:
            continue
        descendants.add(current)
        queue.extend(children.get(current, []))
    return descendants


class ProcessTreeLiveness:
    """Probe that reports whether ``pid`` has active descendants."""

    def __init__(self, pid: int) -> None:
        self.pid = pid

    def is_alive(self) -> bool:
        """Return True when ``pid`` exists and has at least one descendant."""
        mapping = _all_processes()
        if self.pid not in mapping:
            return False
        return bool(_descendant_pids(self.pid, mapping))


class RunLogLiveness:
    """Probe that reports whether any watched file has been written recently.

    ``is_alive`` returns True on the first call for an existing file (the
    baseline is established) and on subsequent calls only when a file's size or
    mtime has changed since the previous observation.
    """

    def __init__(self, *paths: str | Path) -> None:
        self.paths = [Path(p) for p in paths]
        self._last: dict[Path, tuple[int, float]] = {}

    def is_alive(self) -> bool:
        """Return True when at least one watched file has changed."""
        changed = False
        for path in self.paths:
            try:
                stat = path.stat()
            except OSError:
                continue
            key = (stat.st_size, stat.st_mtime)
            previous = self._last.get(path)
            if previous is None:
                self._last[path] = key
                changed = True
            elif previous != key:
                self._last[path] = key
                changed = True
        return changed


class HybridLiveness:
    """Probe that is alive when either process-tree or run-log is alive."""

    def __init__(
        self,
        pid: int,
        watched_paths: Iterable[str | Path],
    ) -> None:
        self.process_tree = ProcessTreeLiveness(pid)
        self.run_log = RunLogLiveness(*watched_paths)

    def is_alive(self) -> bool:
        """Return True when either signal reports liveness."""
        return self.process_tree.is_alive() or self.run_log.is_alive()


class LivenessMonitor:
    """Background monitor that periodically samples hybrid liveness.

    The monitor keeps a shared ``last_sign_of_life`` timestamp that the
    watchdog thread consults. It is initialized to the creation time so a
    session is not killed before the first poll completes.
    """

    def __init__(
        self,
        pid: int,
        watched_paths: Iterable[str | Path],
        poll_interval: float,
    ) -> None:
        self._liveness = HybridLiveness(pid, watched_paths)
        self._poll_interval = poll_interval
        self._lock = threading.Lock()
        self._last_sign_of_life = time.monotonic()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def last_sign_of_life(self) -> float:
        """Return the most recent liveness timestamp."""
        with self._lock:
            return self._last_sign_of_life

    def mark_alive(self) -> None:
        """Record a liveness signal observed by the caller."""
        with self._lock:
            self._last_sign_of_life = time.monotonic()

    def start(self) -> None:
        """Start the background polling thread."""
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Signal the polling thread to stop."""
        self._stop_event.set()

    def join(self, timeout: float | None = None) -> None:
        """Wait for the polling thread to exit."""
        if self._thread is not None:
            self._thread.join(timeout=timeout)

    def _run(self) -> None:
        while not self._stop_event.wait(timeout=self._poll_interval):
            if self._liveness.is_alive():
                self.mark_alive()
