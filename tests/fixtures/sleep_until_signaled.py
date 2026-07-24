#!/usr/bin/env python3
"""Signal-aware sleep helper for orchestrator test fixtures.

Fake agent CLIs used in the orchestrator test pole used to do ``time.sleep(N)``
with very large ``N``.  Those processes ignored ``SIGTERM``, so the orchestrator's
``_terminate_process_group`` had to wait its full escalation timeout before
``SIGKILL``.  This helper sleeps until it receives ``SIGTERM``/``SIGINT`` or hits
an optional wall-clock timeout, exiting promptly on termination so tests finish
as soon as the orchestrator kills them.
"""

from __future__ import annotations

import signal
import sys
import time


def main() -> None:
    timeout = float(sys.argv[1]) if len(sys.argv) > 1 else 600.0
    # Optional second argument is a marker string so ``pgrep -f <marker>`` can
    # identify this specific sleeper among concurrently running fixtures.
    _ = sys.argv[2] if len(sys.argv) > 2 else ""
    deadline = time.monotonic() + timeout
    shutdown = False

    def _handler(_signum, _frame):
        nonlocal shutdown
        shutdown = True

    signal.signal(signal.SIGTERM, _handler)
    signal.signal(signal.SIGINT, _handler)

    while not shutdown and time.monotonic() < deadline:
        time.sleep(0.05)


if __name__ == "__main__":
    main()
