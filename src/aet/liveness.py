"""Hybrid liveness probes for the orchestrator's session watchdog.

The watchdog distinguishes a slow-but-alive session from a genuinely wedged
one by combining two signals:

- Process-tree activity: the session's main process has active descendants
  (background tasks, subagents, long-running validations).
- Run-log/file writes: watched log or telemetry files are still growing.

Either signal resets the stall timer. A hard wall-clock backstop remains the
ultimate ceiling for truly stuck sessions (R-3).
"""

from __future__ import annotations

import subprocess
import threading
import time
from pathlib import Path
from typing import Iterable


def _all_processes() -> dict[int, int]:
    """Return a pid -> ppid map for every process visible to ``ps``.

    Falls back to an empty map when ``ps`` is unavailable or produces unexpected
    output, so a missing tool never crashes the watchdog.
    """
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

    mapping: dict[int, int] = {}
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
