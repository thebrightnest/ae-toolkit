"""Local advisory lock for the single-pr integration step.

The lock covers the integration step only: rebase onto current tip,
re-validate, squash-merge. It is deliberately the same shape as the queue
lock in `aet.queue` — local, single-operator, advisory. It orders one
operator's own concurrent pipelines; it is not a claim-check, not a lease,
and not visible to anyone else (ADR-045, decision 5).
"""

from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from filelock import FileLock


def integration_lock_path(repo_root: str | Path) -> Path:
    """Return the sidecar lock path for the integration step."""
    return Path(repo_root) / ".agents" / "integration.lock"


def _log_lock_event(log_path: str, event: str, pid: int) -> None:
    """Append one ordered lock event to the shared log.

    Used by orchestrator tests to prove serialization without sleeps. The log
    is written outside the lock so it does not itself serialize callers; the
    ordering evidence comes from the lock acquisition order.
    """
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            json.dump(
                {"event": event, "pid": pid, "time": time.monotonic()},
                f,
            )
            f.write("\n")
    except OSError:
        pass


@contextmanager
def integration_lock(repo_root: str | Path) -> Iterator[None]:
    """Acquire an exclusive advisory lock on the integration sidecar.

    The lock is blocking and process-scoped. It is released on exit even when
    the integration step raises or crashes.
    """
    path = integration_lock_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = FileLock(str(path))
    log_path = os.environ.get("AET_INTEGRATION_LOCK_LOG")
    pid = os.getpid()

    lock.acquire()
    try:
        if log_path:
            _log_lock_event(log_path, "acquired", pid)
        yield
    finally:
        if log_path:
            _log_lock_event(log_path, "releasing", pid)
        lock.release()


class IntegrationFailureError(Exception):
    """Raised when the single-pr integration step fails.

    This covers rebase conflicts and post-rebase validation failures. It is an
    engine-level outcome, not a member of the ADR-030 agent-session failure
    class menu.
    """
