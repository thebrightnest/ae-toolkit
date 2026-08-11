"""Tests for branch_ref resolution."""

from __future__ import annotations

import subprocess
from pathlib import Path

from aet.branch_ref import (
    resolve_base_ref,
    resolve_integration_branch,
    resolve_trunk_branch,
)


def _init_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(path)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(path), "config", "user.email", "test@example.com"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(path), "config", "user.name", "Test User"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(path), "commit", "--allow-empty", "-m", "init"],
        check=True,
        capture_output=True,
    )


def test_trunk_branch_config_wins(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)

    ref = resolve_trunk_branch(repo, {"trunk_branch": "release"})

    assert ref.ref == "release"
    assert ref.provenance == "config"


def test_trunk_branch_detected_from_origin_head(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    subprocess.run(
        ["git", "-C", str(repo), "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/dev"],
        check=True,
        capture_output=True,
    )

    ref = resolve_trunk_branch(repo, {})

    assert ref.ref == "dev"
    assert ref.provenance == "detected"


def test_trunk_branch_fallback_when_origin_head_unset(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)

    ref = resolve_trunk_branch(repo, {})

    assert ref.ref == "main"
    assert ref.provenance == "fallback"


def test_integration_branch_cli_base_wins(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)

    ref = resolve_integration_branch(
        repo,
        {"integration_branch": "feature/config"},
        cli_base="feature/cli",
    )

    assert ref.ref == "feature/cli"
    assert ref.provenance == "cli"


def test_integration_branch_env_beats_config(monkeypatch, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    monkeypatch.setenv("AET_WORK_BASE_BRANCH", "feature/env")

    ref = resolve_integration_branch(repo, {"integration_branch": "feature/config"})

    assert ref.ref == "feature/env"
    assert ref.provenance == "env"


def test_integration_branch_config_beats_trunk(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)

    ref = resolve_integration_branch(repo, {"integration_branch": "feature/config"})

    assert ref.ref == "feature/config"
    assert ref.provenance == "config"


def test_integration_branch_falls_back_to_trunk(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)

    ref = resolve_integration_branch(repo, {})

    assert ref.ref == "main"
    assert ref.provenance == "trunk"


def _set_remote_ref(repo: Path, ref: str) -> None:
    """Point ``refs/remotes/<ref>`` at HEAD, as a fetch would."""
    head = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    subprocess.run(
        ["git", "-C", str(repo), "update-ref", f"refs/remotes/{ref}", head],
        check=True,
        capture_output=True,
    )


def test_base_ref_prefers_remote_tracking_ref(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    _set_remote_ref(repo, "origin/main")

    assert resolve_base_ref(repo, "main") == "origin/main"


def test_base_ref_falls_back_to_local_when_no_remote(tmp_path: Path) -> None:
    """A project with no remote must still get a usable worktree base."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)

    assert resolve_base_ref(repo, "main") == "main"


def test_base_ref_falls_back_when_integration_branch_is_unpushed(tmp_path: Path) -> None:
    """single-pr integration branches are often local-only for their first run."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    _set_remote_ref(repo, "origin/main")
    subprocess.run(
        ["git", "-C", str(repo), "branch", "fix/catalog-job-runtime"],
        check=True,
        capture_output=True,
    )

    assert resolve_base_ref(repo, "fix/catalog-job-runtime") == "fix/catalog-job-runtime"


def test_base_ref_leaves_an_already_qualified_ref_alone(tmp_path: Path) -> None:
    """``--base origin/main`` must not become ``origin/origin/main``."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    _set_remote_ref(repo, "origin/main")

    assert resolve_base_ref(repo, "origin/main") == "origin/main"
