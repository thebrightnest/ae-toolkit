"""pytest configuration for orchestrator tests."""


import pytest


@pytest.fixture(autouse=True)
def _isolate_telemetry_archive(monkeypatch, tmp_path):
    """Point the telemetry archive at a per-test tmp dir.

    The suite spawns the real orchestrator, and env vars are inherited by every
    subprocess, so one autouse fixture keeps all spawn sites out of the real
    ``~/.aet/telemetry``. Tests that need an explicit archive override this by
    setting ``AET_TELEMETRY_ARCHIVE_DIR`` themselves.

    ``DEFAULT_ARCHIVE_DIR`` is patched as well: several tests run orchestrator
    code in-process under ``patch.dict(os.environ, ..., clear=True)``, which
    wipes the env var; without the module-level patch those calls fall back to
    the real archive.
    """
    from aet import telemetry

    archive = tmp_path / "telemetry-archive"
    monkeypatch.setenv("AET_TELEMETRY_ARCHIVE_DIR", str(archive))
    monkeypatch.setattr(telemetry, "DEFAULT_ARCHIVE_DIR", archive)


@pytest.fixture(autouse=True)
def _isolate_aet_bin_dir(monkeypatch, tmp_path):
    """Point ``AET_BIN_DIR`` at a per-test tmp dir.

    The ``aet`` dispatcher self-repairs its PATH symlink on every
    invocation; without isolation, in-process ``main()`` calls and spawned
    subprocesses would rewrite the real ``~/.local/bin/aet``. Env vars are
    inherited by subprocesses, so one autouse fixture covers both.
    """
    monkeypatch.setenv("AET_BIN_DIR", str(tmp_path / "aet-bin"))
