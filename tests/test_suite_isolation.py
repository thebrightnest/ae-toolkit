"""Suite-hygiene invariants: a test must never reach the real repository.

Several tests run backend code under ``patch.dict(os.environ, ..., clear=True)``
with a relative queue path, so the backend resolves this checkout rather than a
tmpdir. Reaching its *remote* from there stalls for minutes on git auth with the
environment wiped, and the forced ``refs/aet/*`` refspec would overwrite the
developer's own refs on a machine whose auth survives the cleared env. The
autouse guard in ``tests/conftest.py`` closes that path; this pins it.
"""

from __future__ import annotations

from pathlib import Path

from aet.backends import git_refs_backend

_REPO_ROOT = Path(__file__).parent.parent


def test_real_repo_remote_is_unreachable_from_tests():
    """The real checkout must look remote-less to every test."""
    assert git_refs_backend._has_remote(str(_REPO_ROOT)) is False, (
        "A test can reach the real repository's remote. The autouse "
        "_no_real_remote guard in tests/conftest.py is missing or no longer "
        "covers this path; git fetch/push against the real repo would run."
    )


def test_guard_does_not_hide_remotes_of_other_repositories(tmp_path):
    """Fixture repositories with a real remote must still be detected."""
    import subprocess

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    assert git_refs_backend._has_remote(str(repo)) is False

    subprocess.run(
        ["git", "-C", str(repo), "remote", "add", "origin", str(tmp_path / "x.git")],
        check=True,
    )
    assert git_refs_backend._has_remote(str(repo)) is True, (
        "The guard must be scoped to this checkout; tests that exercise "
        "fetch/push against a fixture remote depend on real detection."
    )


def test_orchestration_env_vars_are_isolated():
    """Orchestrator session variables must not leak into test environments."""
    import os

    for key in ("AET_REPO_ROOT", "AET_TASK_ID", "AET_RUN_ID", "AET_WORKTREE", "AET_EVIDENCE_PATH"):
        assert key not in os.environ, f"{key} leaked into test environment"
    assert not any(k.startswith("AET_EVIDENCE_PATH_") for k in os.environ)
