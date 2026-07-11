"""Guard tests: the pytest suite must not write to the real telemetry archive.

The autouse ``_isolate_telemetry_archive`` fixture in ``tests/conftest.py``
points ``AET_TELEMETRY_ARCHIVE_DIR`` at a per-test tmp dir, so any orchestrator
spawn that inherits the environment lands outside ``~/.aet/telemetry``.
"""

from __future__ import annotations

import os
from pathlib import Path

import telemetry


def test_default_env_points_into_pytest_tmp(tmp_path):
    archive = os.environ.get("AET_TELEMETRY_ARCHIVE_DIR")
    assert archive is not None, "autouse fixture must set AET_TELEMETRY_ARCHIVE_DIR"
    archive_path = Path(archive)
    assert archive_path.is_relative_to(tmp_path)
    assert not archive_path.is_relative_to(Path.home() / ".aet")


def test_runlogger_defaults_under_isolated_archive(tmp_path):
    real_archive = Path.home() / ".aet" / "telemetry"
    before = set(real_archive.iterdir()) if real_archive.exists() else set()

    logger = telemetry.RunLogger(repo_root=tmp_path, run_id="isolation-guard")

    assert logger.run_dir.exists()
    assert logger.run_dir.is_relative_to(
        Path(os.environ["AET_TELEMETRY_ARCHIVE_DIR"])
    )

    after = set(real_archive.iterdir()) if real_archive.exists() else set()
    assert before == after, "RunLogger must not add entries to the real archive"
