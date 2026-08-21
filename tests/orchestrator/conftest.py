"""Shared orchestrator test fixtures."""

from __future__ import annotations

import pytest

from tests.orchestrator._helpers import (
    load_queue,  # noqa: F401
    write_queue,  # noqa: F401
)


@pytest.fixture(autouse=True)
def _reset_orchestrator_shutdown_flag():
    """Prevent a timed-out batch test from killing unrelated stage sessions."""
    # Imported late so the module is already loaded by the test modules.
    import orchestrator

    orchestrator._shutdown_requested = False
    yield
    orchestrator._shutdown_requested = False
