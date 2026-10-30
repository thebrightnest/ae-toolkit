"""Guard tests: the pytest suite must not write to the real telemetry archive.

The autouse ``_isolate_aet_home`` fixture in ``tests/conftest.py``
points ``AET_HOME`` at a per-test tmp dir and patches the fallback, so any
orchestrator spawn that inherits the environment lands outside ``~/.aet``.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

from aet import evidence, telemetry, user_paths


def test_default_env_points_into_pytest_tmp(tmp_path):
    home = os.environ.get("AET_HOME")
    assert home is not None, "autouse fixture must set AET_HOME"
    home_path = Path(home)
    assert home_path.is_relative_to(tmp_path)
    assert not home_path.is_relative_to(Path.home() / ".aet")


def test_runlogger_defaults_under_isolated_archive(tmp_path):
    real_archive = Path.home() / ".aet" / "telemetry"
    before = set(real_archive.iterdir()) if real_archive.exists() else set()

    logger = telemetry.RunLogger(repo_root=tmp_path, run_id="isolation-guard")

    assert logger.run_dir.exists()
    assert logger.run_dir.is_relative_to(telemetry.archive_dir())
    assert not logger.run_dir.is_relative_to(real_archive)

    after = set(real_archive.iterdir()) if real_archive.exists() else set()
    assert before == after, "RunLogger must not add entries to the real archive"


def test_runlogger_stays_isolated_when_env_is_cleared(tmp_path):
    """Tests that wipe os.environ via patch.dict(clear=True) must not escape.

    Several orchestrator tests run in-process under a cleared environment;
    without the fallback patch they would fall back to the real archive.
    """
    real_archive = Path.home() / ".aet" / "telemetry"
    before = set(real_archive.iterdir()) if real_archive.exists() else set()

    with patch.dict(os.environ, {}, clear=True):
        assert "AET_HOME" not in os.environ
        assert "AET_TELEMETRY_ARCHIVE_DIR" not in os.environ
        logger = telemetry.RunLogger(repo_root=tmp_path, run_id="cleared-env")

    assert logger.run_dir.exists()
    assert not logger.run_dir.is_relative_to(real_archive)
    assert logger.run_dir.is_relative_to(tmp_path)

    after = set(real_archive.iterdir()) if real_archive.exists() else set()
    assert before == after, "cleared-env RunLogger must not touch the real archive"


def test_reports_dir_stays_isolated_when_env_is_cleared(tmp_path):
    real_reports = Path.home() / ".aet" / "reports"
    with patch.dict(os.environ, {}, clear=True):
        assert "AET_HOME" not in os.environ
        assert "AET_REPORTS_DIR" not in os.environ
        rep_dir = evidence.reports_dir()

    assert not rep_dir.is_relative_to(real_reports)
    assert rep_dir.is_relative_to(tmp_path)


def test_user_config_path_honors_aet_home(tmp_path):
    slug = "test-project/main"
    config_path = user_paths.user_config_path(slug)
    assert config_path == user_paths.aet_home() / slug / "config.json"
    assert config_path.is_relative_to(tmp_path)
    assert not config_path.is_relative_to(Path.home() / ".aet")
