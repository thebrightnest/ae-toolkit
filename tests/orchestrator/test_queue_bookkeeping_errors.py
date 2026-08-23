"""Tests for _record_run_one_in_queue error handling.

Programming errors (broken bookkeeping code) must propagate so they cannot
degrade into silently dropped queue metadata; environmental errors (lock
contention, IO) are tolerated with a warning so they never block a run.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
from pathlib import Path

import pytest

_ORCHESTRATOR_BIN = Path(__file__).parents[2] / "src" / "aet" / "cli" / "orchestrator.py"
_orchestrator_loader = importlib.machinery.SourceFileLoader("orchestrator", str(_ORCHESTRATOR_BIN))
_spec = importlib.util.spec_from_loader("orchestrator", _orchestrator_loader)
orchestrator = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(orchestrator)


class _FailingBackend:
    """Backend whose load() raises a configurable exception."""

    def __init__(self, exc: BaseException) -> None:
        self._exc = exc

    def load(self) -> dict:
        raise self._exc


@pytest.mark.parametrize(
    "exc_type",
    sorted(orchestrator._PROGRAMMING_ERRORS, key=lambda t: t.__name__),
)
def test_programming_errors_propagate(exc_type: type[BaseException]) -> None:
    backend = _FailingBackend(exc_type("boom"))
    with pytest.raises(exc_type):
        orchestrator._record_run_one_in_queue(
            backend, "/tmp/queue", "t1", "/tmp/wt", "branch", "/tmp/repo"
        )


def test_environmental_errors_are_tolerated(capsys: pytest.CaptureFixture) -> None:
    backend = _FailingBackend(OSError("queue busy"))
    result = orchestrator._record_run_one_in_queue(
        backend, "/tmp/queue", "t1", "/tmp/wt", "branch", "/tmp/repo"
    )
    assert result is False
    assert "Queue bookkeeping failed for t1" in capsys.readouterr().out
