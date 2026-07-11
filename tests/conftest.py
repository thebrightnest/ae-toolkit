"""pytest configuration for orchestrator tests."""

import sys
from pathlib import Path

import pytest

# Add aet-work/lib to the import path
sys.path.insert(0, str(Path(__file__).parent.parent / "aet-work" / "lib"))


@pytest.fixture(autouse=True)
def _isolate_telemetry_archive(monkeypatch, tmp_path):
    """Point the telemetry archive at a per-test tmp dir.

    The suite spawns the real orchestrator, and env vars are inherited by every
    subprocess, so one autouse fixture keeps all spawn sites out of the real
    ``~/.aet/telemetry``. Tests that need an explicit archive override this by
    setting ``AET_TELEMETRY_ARCHIVE_DIR`` themselves.
    """
    monkeypatch.setenv(
        "AET_TELEMETRY_ARCHIVE_DIR", str(tmp_path / "telemetry-archive")
    )
