"""Tests for `aet update` (and its `aet setup update` alias).

The managed repository is a real git clone of a local bare "origin" carrying
release tags, so fetch/checkout/rollback run for real. Only the steps that
would touch the user's environment (package install, skill and binary
linking) are intercepted.
"""

from __future__ import annotations

import importlib
import json
import subprocess
from pathlib import Path

import pytest
import typer.main
from typer.testing import CliRunner

from aet.cli import setup as setup_cli
from aet.cli import update as update_cli
from tests.cli._helpers import Result, git, run_typer

aet = importlib.import_module("aet.cli.main")


def _head(repo: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()


def _tag_commit(repo: Path, tag: str) -> str:
    return subprocess.run(
        ["git", "rev-parse", f"{tag}^{{commit}}"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()


@pytest.fixture
def managed(tmp_path, monkeypatch):
    """A managed install at v1.0.0 whose origin also has v1.1.0."""
    seed = tmp_path / "seed"
    seed.mkdir()
    git(["init", "-q", "-b", "main"], seed)
    git(["config", "user.email", "t@example.com"], seed)
    git(["config", "user.name", "t"], seed)
    for version in ("1.0.0", "1.1.0"):
        (seed / "VERSION").write_text(version)
        git(["add", "VERSION"], seed)
        git(["commit", "-q", "-m", version], seed)
        git(["tag", f"v{version}"], seed)

    origin = tmp_path / "origin.git"
    git(["clone", "-q", "--bare", str(seed), str(origin)], tmp_path)

    data_dir = tmp_path / "data"
    repo = data_dir / "repo"
    git(["clone", "-q", str(origin), str(repo)], tmp_path)
    git(["checkout", "-q", "tags/v1.0.0"], repo)
    venv = data_dir / "venv"
    (venv / "bin").mkdir(parents=True)

    monkeypatch.setenv("AET_DATA_DIR", str(data_dir))
    monkeypatch.setattr(update_cli, "_running_prefix", lambda: venv)
    monkeypatch.setattr(update_cli, "_current_version", lambda: "1.0.0")
    monkeypatch.setattr(update_cli.shutil, "which", lambda name: "/usr/bin/uv" if name == "uv" else None)

    calls: list[list[str]] = []
    failing: list[str] = []
    real_run = update_cli._run

    def fake_run(cmd, **kwargs):
        if cmd[0] == "git":
            return real_run(cmd, **kwargs)
        calls.append(list(cmd))
        joined = " ".join(cmd)
        # Each marker fails the first matching call only.
        hit = next((marker for marker in failing if marker in joined), None)
        if hit is not None:
            failing.remove(hit)
        returncode = 1 if hit is not None else 0
        return subprocess.CompletedProcess(cmd, returncode, stdout="", stderr="boom" if returncode else "")

    monkeypatch.setattr(update_cli, "_run", fake_run)

    class Env:
        pass

    env = Env()
    env.repo, env.venv, env.data_dir, env.origin = repo, venv, data_dir, origin
    env.calls, env.failing, env.seed = calls, failing, seed
    return env


def _update(*args: str):
    return run_typer(aet.app, ["update", *args])


# --- --check -----------------------------------------------------------------


def test_check_reports_current_latest_and_planned_steps_without_mutating(managed):
    before = _head(managed.repo)

    result = _update("--check")

    assert result.exit_code == 0, result.output
    assert "current: v1.0.0" in result.output
    assert "latest:  v1.1.0" in result.output
    assert "update available" in result.output
    assert "git fetch --tags origin" in result.output
    assert "git checkout tags/v1.1.0" in result.output
    assert "setup skills" in result.output
    assert "setup link" in result.output
    assert _head(managed.repo) == before
    assert managed.calls == []
    assert not (managed.data_dir / "version-cache.json").exists()


def test_check_when_up_to_date(managed, monkeypatch):
    monkeypatch.setattr(update_cli, "_current_version", lambda: "1.1.0")

    result = _update("--check")

    assert result.exit_code == 0, result.output
    assert "up to date" in result.output
    assert "git checkout" not in result.output


def test_check_with_explicit_tag_plans_that_tag(managed):
    result = _update("--check", "--tag", "v1.0.0")

    assert result.exit_code == 0, result.output
    assert "git checkout tags/v1.0.0" in result.output


def test_check_reports_offline_remote(managed):
    git(["remote", "set-url", "origin", str(managed.data_dir / "missing.git")], managed.repo)

    result = _update("--check")

    assert result.exit_code == 1
    assert "could not reach" in result.output


# --- topology ----------------------------------------------------------------


def test_development_checkout_is_refused(tmp_path, monkeypatch):
    checkout = tmp_path / "checkout"
    (checkout / ".git").mkdir(parents=True)
    monkeypatch.setenv("AET_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(update_cli, "_running_prefix", lambda: tmp_path / ".venv")
    monkeypatch.setattr(update_cli, "_source_checkout", lambda: checkout)

    result = _update("--yes")

    assert result.exit_code == 1
    assert f"Development checkout detected at {checkout}" in result.output
    assert "git pull && make install-skills" in result.output


def test_unmanaged_install_is_refused(tmp_path, monkeypatch):
    monkeypatch.setenv("AET_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(update_cli, "_running_prefix", lambda: tmp_path / "elsewhere")
    monkeypatch.setattr(update_cli, "_source_checkout", lambda: None)

    result = _update("--yes")

    assert result.exit_code == 1
    assert "No managed installation" in result.output


# --- managed update ----------------------------------------------------------


def test_managed_update_runs_full_sequence(managed):
    result = _update("--yes")

    assert result.exit_code == 0, result.output
    assert _head(managed.repo) == _tag_commit(managed.repo, "v1.1.0")
    venv_python = str(managed.venv / "bin" / "python")
    venv_aet = str(managed.venv / "bin" / "aet")
    assert managed.calls == [
        ["/usr/bin/uv", "pip", "install", "--python", venv_python, str(managed.repo)],
        [venv_aet, "setup", "skills"],
        [venv_aet, "setup", "link"],
    ]
    cache = json.loads((managed.data_dir / "version-cache.json").read_text())
    assert cache["latest_version"] == "1.1.0"
    assert "aet updated: v1.0.0 -> v1.1.0" in result.output


def test_managed_update_falls_back_to_pip_without_uv(managed, monkeypatch):
    monkeypatch.setattr(update_cli.shutil, "which", lambda name: None)

    result = _update("--yes")

    assert result.exit_code == 0, result.output
    venv_python = str(managed.venv / "bin" / "python")
    assert managed.calls[0] == [venv_python, "-m", "pip", "install", str(managed.repo)]


def test_new_upstream_tag_is_fetched_before_resolving(managed):
    (managed.seed / "VERSION").write_text("1.2.0")
    git(["commit", "-qam", "1.2.0"], managed.seed)
    git(["tag", "v1.2.0"], managed.seed)
    git(["push", "-q", str(managed.origin), "v1.2.0"], managed.seed)

    result = _update("--yes")

    assert result.exit_code == 0, result.output
    assert _head(managed.repo) == _tag_commit(managed.repo, "v1.2.0")


def test_explicit_tag_is_checked_out(managed, monkeypatch):
    monkeypatch.setattr(update_cli, "_current_version", lambda: "1.1.0")
    git(["checkout", "-q", "tags/v1.1.0"], managed.repo)

    result = _update("--yes", "--tag", "v1.0.0")

    assert result.exit_code == 0, result.output
    assert _head(managed.repo) == _tag_commit(managed.repo, "v1.0.0")
    assert "aet updated: v1.1.0 -> v1.0.0" in result.output


def test_explicit_tag_accepts_missing_v_prefix(managed):
    result = _update("--yes", "--tag", "1.1.0")

    assert result.exit_code == 0, result.output
    assert _head(managed.repo) == _tag_commit(managed.repo, "v1.1.0")


def test_unknown_tag_is_rejected_without_changes(managed):
    before = _head(managed.repo)

    result = _update("--yes", "--tag", "v9.9.9")

    assert result.exit_code == 1
    assert "v9.9.9" in result.output
    assert _head(managed.repo) == before
    assert managed.calls == []


def test_already_up_to_date_does_nothing(managed, monkeypatch):
    monkeypatch.setattr(update_cli, "_current_version", lambda: "1.1.0")
    before = _head(managed.repo)

    result = _update("--yes")

    assert result.exit_code == 0, result.output
    assert "already up to date" in result.output
    assert _head(managed.repo) == before
    assert managed.calls == []


def test_dirty_managed_repo_is_refused(managed):
    (managed.repo / "VERSION").write_text("local edit")

    result = _update("--yes")

    assert result.exit_code == 1
    assert "uncommitted changes" in result.output
    assert managed.calls == []


def test_declined_confirmation_changes_nothing(managed, monkeypatch):
    monkeypatch.setattr(update_cli, "_interactive", lambda: True)
    before = _head(managed.repo)

    result = Result(CliRunner().invoke(aet.app, ["update"], input="n\n"))

    assert result.exit_code == 1
    assert _head(managed.repo) == before
    assert managed.calls == []


# --- fail-safe ---------------------------------------------------------------


def test_fetch_failure_stops_before_any_change(managed):
    before = _head(managed.repo)
    git(["remote", "set-url", "origin", str(managed.data_dir / "missing.git")], managed.repo)

    result = _update("--yes")

    assert result.exit_code == 1
    assert "git fetch --tags origin failed" in result.output
    assert _head(managed.repo) == before
    assert managed.calls == []


def test_install_failure_rolls_back_checkout(managed):
    before = _head(managed.repo)
    managed.failing.append("pip install")

    result = _update("--yes")

    assert result.exit_code == 1
    assert "boom" in result.output
    assert "rolled back to v1.0.0" in result.output
    assert _head(managed.repo) == before
    # Install of the target, then reinstall of the previous checkout; no linking.
    assert [call[1:3] for call in managed.calls] == [["pip", "install"], ["pip", "install"]]
    assert not (managed.data_dir / "version-cache.json").exists()


def test_link_failure_rolls_back_checkout_and_reinstalls(managed):
    before = _head(managed.repo)
    managed.failing.append("setup link")

    result = _update("--yes")

    assert result.exit_code == 1
    assert _head(managed.repo) == before
    assert managed.calls[-1][1:3] == ["pip", "install"]


def test_failed_rollback_prints_recovery_guidance(managed, monkeypatch):
    managed.failing.append("pip install")
    real_run = update_cli._run

    def fail_restore(cmd, **kwargs):
        if cmd[0] == "git" and "checkout" in cmd and "tags/" not in cmd[-1]:
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="restore failed")
        return real_run(cmd, **kwargs)

    monkeypatch.setattr(update_cli, "_run", fail_restore)

    result = _update("--yes", "--tag", "v1.1.0")

    assert result.exit_code == 1
    assert "rollback failed" in result.output
    assert "re-run the installer" in result.output


# --- registration ------------------------------------------------------------


def test_setup_update_alias(managed):
    result = run_typer(aet.app, ["setup", "update", "--check"])

    assert result.exit_code == 0, result.output
    assert "latest:  v1.1.0" in result.output


@pytest.mark.parametrize(
    ("app", "path"),
    [(aet.app, "update"), (setup_cli.app, "update")],
    ids=["update", "setup-update"],
)
def test_update_has_no_dry_run_option(app, path):
    group = typer.main.get_command(app)
    command = group.commands[path]
    opts = {opt for param in command.params for opt in getattr(param, "opts", [])}
    assert "--dry-run" not in opts
    assert {"--check", "--tag", "--yes", "-y"} <= opts
