"""pytest configuration for orchestrator tests."""

import os
import sys
import unittest
from pathlib import Path

import pytest

# Python < 3.11 compatibility: backport enterClassContext to unittest.TestCase.
if not hasattr(unittest.TestCase, "enterClassContext"):

    @classmethod
    def _enterClassContext(cls, cm):
        result = cm.__enter__()
        cls.addClassCleanup(cm.__exit__, None, None, None)
        return result

    unittest.TestCase.enterClassContext = _enterClassContext

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
def _isolate_aet_home(request, monkeypatch, tmp_path):
    """Point ``AET_HOME`` at a per-test tmp dir and patch user_paths fallback.

    The suite spawns the real orchestrator, and env vars are inherited by every
    subprocess, so one autouse fixture keeps all spawn sites out of the real
    ``~/.aet``. Tests that need an explicit archive or reports dir override
    ``AET_TELEMETRY_ARCHIVE_DIR`` or ``AET_REPORTS_DIR`` themselves.

    The fallback home in ``user_paths`` is patched as well: several tests run
    code in-process under ``patch.dict(os.environ, ..., clear=True)``, which
    wipes the env var; without the fallback patch those calls fall back to
    the real ``~/.aet``.
    """
    if request.cls is not None:
        return

    from aet import user_paths

    home = tmp_path / "aet-home"
    monkeypatch.setenv("AET_HOME", str(home))
    monkeypatch.setattr(user_paths, "_FALLBACK_AET_HOME", home)


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


@pytest.fixture(scope="class", autouse=True)
def _isolate_class_scoped_setup(request, tmp_path_factory):
    """Extend the isolation above over ``unittest``'s ``setUpClass``.

    Every fixture in this file depends on ``monkeypatch``/``tmp_path``, which
    are function-scoped, so pytest establishes them only once unittest has
    already run ``setUpClass``. A class that does real work there does it
    against the developer's own stores: both orchestrator rehearsals run a
    full ``run_batch`` in ``setUpClass``, which is how 384 ``nsr-*``
    directories reached the real ``~/.aet/telemetry`` and 317 fixture events
    reached the real ``.agents/ledger.jsonl`` — including 115 written *after*
    ``3ad3c4cd`` added ``_isolate_ledger`` to prevent exactly that.

    This runs one scope earlier and re-establishes the same redirections, so
    the window is closed by construction rather than per test class. The
    function-scoped fixtures still run afterwards and narrow each test to its
    own ``tmp_path``; this one only has to cover class setup.

    Scoped to classes on purpose. A bare test function is already covered by
    the fixtures above, and the ledger resolver's own tests
    (``@pytest.mark.real_ledger_resolution``) are bare functions that assert
    on the unset-env path — ``request.cls is None`` leaves them untouched.
    """
    if request.cls is None:
        yield
        return

    from aet import ledger, user_paths
    from aet.backends import git_refs_backend

    root = tmp_path_factory.mktemp("class-isolation")
    aet_home = root / "aet-home"
    ledger_root = root / "ledger-root"
    (ledger_root / ".agents").mkdir(parents=True, exist_ok=True)

    real_has_remote = git_refs_backend._has_remote

    def guarded(repo_root):
        if Path(repo_root).resolve() == _REPO_ROOT.resolve():
            return False
        return real_has_remote(repo_root)

    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("AET_HOME", str(aet_home))
        mp.setenv("AET_BIN_DIR", str(root / "aet-bin"))
        mp.setenv("AET_LEDGER_PATH", str(ledger_root / ".agents" / "ledger.jsonl"))
        mp.delenv("AET_REPO_ROOT", raising=False)
        mp.delenv("AET_TASK_ID", raising=False)
        mp.delenv("AET_RUN_ID", raising=False)
        mp.delenv("AET_WORKTREE", raising=False)
        mp.delenv("AET_EVIDENCE_PATH", raising=False)
        for k in list(os.environ):
            if k.startswith("AET_EVIDENCE_PATH_"):
                mp.delenv(k, raising=False)
        mp.setattr(user_paths, "_FALLBACK_AET_HOME", aet_home)
        mp.setattr(ledger, "_resolve_ledger_repo_root", lambda: ledger_root)
        mp.setattr(git_refs_backend, "_has_remote", guarded)
        yield


@pytest.fixture(autouse=True)
def _isolate_aet_repo_root(monkeypatch):
    """Remove orchestration environment variables from the inherited environment.

    The orchestrator that launches the test suite sets ``AET_REPO_ROOT``,
    ``AET_TASK_ID``, ``AET_RUN_ID``, ``AET_WORKTREE``, and ``AET_EVIDENCE_PATH``.
    Tests must resolve their own repository roots and verdict destinations
    (or set the variables explicitly) so they do not accidentally read or write
    the developer's live stores or inherited paths.
    """
    monkeypatch.delenv("AET_REPO_ROOT", raising=False)
    monkeypatch.delenv("AET_TASK_ID", raising=False)
    monkeypatch.delenv("AET_RUN_ID", raising=False)
    monkeypatch.delenv("AET_WORKTREE", raising=False)
    monkeypatch.delenv("AET_EVIDENCE_PATH", raising=False)
    for k in list(os.environ):
        if k.startswith("AET_EVIDENCE_PATH_"):
            monkeypatch.delenv(k, raising=False)


@pytest.fixture(autouse=True)
def _no_real_remote(monkeypatch):
    """Never let a test reach the real repository's remote.

    Tests that run backend code under ``patch.dict(os.environ, ..., clear=True)``
    resolve this checkout — the queue path is relative, so it anchors on the
    process cwd — and then stall for minutes on ``git fetch origin`` with
    ``HOME``/``SSH_AUTH_SOCK`` wiped. Worse, the fetch refspec is forced, so on a
    machine whose git auth survives a cleared env it would overwrite the
    developer's own ``refs/aet/*`` from origin.

    Patching the module attribute is what survives ``clear=True``; an env var
    would not. The guard is scoped to this checkout so that tests which
    legitimately exercise fetch/push against a tmpdir fixture remote are
    unaffected.
    """
    from aet.backends import git_refs_backend

    real = git_refs_backend._has_remote

    def guarded(repo_root):
        if Path(repo_root).resolve() == _REPO_ROOT.resolve():
            return False
        return real(repo_root)

    monkeypatch.setattr(git_refs_backend, "_has_remote", guarded)
