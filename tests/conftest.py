"""pytest configuration for orchestrator tests."""

import os
import sys
from pathlib import Path

import pytest

# The host shell sets PYTHONPATH to the main checkout, which would make every
# ``import aet`` resolve outside this worktree. Force the repo under test onto
# sys.path first and propagate it to subprocesses before pytest imports tests.
_REPO_ROOT = Path(__file__).parent.parent
_WORKTREE_SRC = _REPO_ROOT / "src"
for _path in (str(_WORKTREE_SRC), str(_REPO_ROOT)):
    if _path in sys.path:
        sys.path.remove(_path)
    sys.path.insert(0, _path)
_prev_pythonpath = os.environ.get("PYTHONPATH", "")
os.environ["PYTHONPATH"] = (
    str(_WORKTREE_SRC)
    + os.pathsep
    + str(_REPO_ROOT)
    + (os.pathsep + _prev_pythonpath if _prev_pythonpath else "")
)


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
def _isolate_plans_archive(monkeypatch, tmp_path):
    """Point the settled-plan archive at a per-test tmp dir.

    Keeps closure and migration tests from writing into the real
    ``~/.aet/<slug>/plans/archive/``.
    """
    monkeypatch.setenv("AET_PLANS_ARCHIVE_DIR", str(tmp_path / "plans-archive"))


@pytest.fixture(autouse=True)
def _isolate_aet_bin_dir(monkeypatch, tmp_path):
    """Point ``AET_BIN_DIR`` at a per-test tmp dir.

    The ``aet`` dispatcher self-repairs its PATH symlink on every
    invocation; without isolation, in-process ``main()`` calls and spawned
    subprocesses would rewrite the real ``~/.local/bin/aet``. Env vars are
    inherited by subprocesses, so one autouse fixture covers both.
    """
    monkeypatch.setenv("AET_BIN_DIR", str(tmp_path / "aet-bin"))


@pytest.fixture(autouse=True)
def _isolate_ledger(request, monkeypatch, tmp_path):
    """Point the provenance ledger at a per-test tmp dir.

    Closure paths (``aet state close``/``record-merge``, desk merge) write a
    ``land`` event through ``resolve_ledger_path``. Without isolation those
    writes land in the developer's real ``.agents/ledger.jsonl`` — the
    append-only provenance store — and cannot be removed afterwards without
    rewriting a file whose whole contract is that nothing rewrites it.

    ``_resolve_ledger_repo_root`` is patched as well: several tests run code
    in-process under ``patch.dict(os.environ, ..., clear=True)``, which wipes
    the env var; without the module-level patch those calls fall back to git
    discovery and find the real repository. Tests needing an explicit ledger
    override ``AET_LEDGER_PATH`` themselves, and tests of the resolver itself
    opt out with ``@pytest.mark.real_ledger_resolution``.
    """
    if request.node.get_closest_marker("real_ledger_resolution"):
        # The resolver's own tests drive _resolve_ledger_repo_root directly and
        # assert on the unset-env path; isolating them would test the fixture.
        return

    from aet import ledger

    root = tmp_path / "ledger-root"
    (root / ".agents").mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("AET_LEDGER_PATH", str(root / ".agents" / "ledger.jsonl"))
    monkeypatch.setattr(ledger, "_resolve_ledger_repo_root", lambda: root)
