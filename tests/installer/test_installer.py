"""Tests for the one-line curl installer (scripts/install.sh)."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
INSTALLER = REPO_ROOT / "scripts" / "install.sh"


def _current_branch() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def run_installer(*args: str, env: dict[str, str] | None = None, check: bool = False):
    """Run the installer script with the given args and return the result."""
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    result = subprocess.run(
        [str(INSTALLER), *args],
        capture_output=True,
        text=True,
        env=merged_env,
    )
    if check and result.returncode != 0:
        pytest.fail(f"installer exited {result.returncode}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}")
    return result


class TestInstallerHelp:
    """``--help`` prints usage and exits zero without network access."""

    def test_help_prints_usage_and_exits_zero(self):
        result = run_installer("--help")
        assert result.returncode == 0, result.stderr
        assert "Usage:" in result.stdout
        assert "--help" in result.stdout
        assert "--tag" in result.stdout
        assert "--agent" in result.stdout
        assert "--bin-dir" in result.stdout
        assert "--skills-dir" in result.stdout
        assert "--repo" in result.stdout
        assert "--dry-run" in result.stdout


class TestInstallerInvalidArgs:
    """The script exits non-zero on invalid arguments."""

    def test_unknown_flag_exits_nonzero(self):
        result = run_installer("--not-a-real-flag")
        assert result.returncode != 0
        assert "unknown" in (result.stdout + result.stderr).lower()

    def test_missing_flag_argument_exits_nonzero(self):
        result = run_installer("--agent")
        assert result.returncode != 0


class TestInstallerDryRun:
    """``--dry-run`` prints planned actions and modifies no files."""

    def test_dry_run_with_local_repo_modifies_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            home = tmp_path / "home"
            home.mkdir()
            bin_dir = tmp_path / "bin"
            skills_dir = tmp_path / "skills"
            data_dir = tmp_path / "ae-toolkit"

            env = {
                "HOME": str(home),
                "AET_BIN_DIR": str(bin_dir),
                "AET_SKILLS_DIR": str(skills_dir),
                "AET_DATA_DIR": str(data_dir),
            }
            result = run_installer(
                "--dry-run",
                "--repo", str(REPO_ROOT),
                "--agent", "generic",
                env=env,
                check=True,
            )
            stdout = result.stdout.lower()
            assert "would" in stdout
            assert not bin_dir.exists()
            assert not skills_dir.exists()
            assert not data_dir.exists()


class TestInstallerSmoke:
    """End-to-end smoke test against a local repo checkout."""

    def test_installs_from_local_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            home = tmp_path / "home"
            home.mkdir()
            bin_dir = tmp_path / "bin"
            skills_dir = tmp_path / "skills"
            data_dir = tmp_path / "ae-toolkit"

            env = {
                "HOME": str(home),
                "AET_BIN_DIR": str(bin_dir),
                "AET_SKILLS_DIR": str(skills_dir),
                "AET_DATA_DIR": str(data_dir),
            }
            run_installer(
                "--repo", str(REPO_ROOT),
                "--agent", "generic",
                "--tag", _current_branch(),
                "--bin-dir", str(bin_dir),
                "--skills-dir", str(skills_dir),
                env=env,
                check=True,
            )

            # aet is symlinked into the bin dir
            aet_link = bin_dir / "aet"
            assert aet_link.is_symlink(), f"{aet_link} is not a symlink"
            aet_bin = aet_link.resolve()
            assert aet_bin.exists(), f"{aet_bin} does not exist"
            assert "venv/bin/aet" in str(aet_bin)

            # the installed aet binary runs
            help_result = subprocess.run(
                [str(aet_bin), "--help"],
                capture_output=True,
                text=True,
                env=env,
            )
            assert help_result.returncode == 0, help_result.stderr
            assert "Agentic Engineering Toolkit" in help_result.stdout

            # aet reports its version
            version_result = subprocess.run(
                [str(aet_bin), "--version"],
                capture_output=True,
                text=True,
                env=env,
            )
            assert version_result.returncode == 0, version_result.stderr
            assert "aet" in version_result.stdout

            # skills are linked from the cloned repo
            setup_skill_dir = skills_dir / "aet-setup"
            assert setup_skill_dir.is_symlink(), f"{setup_skill_dir} is not a symlink"
            setup_skill = setup_skill_dir / "SKILL.md"
            assert setup_skill.resolve().is_file(), f"{setup_skill.resolve()} is not a file"

            # idempotent re-run exits zero
            rerun = run_installer(
                "--repo", str(REPO_ROOT),
                "--agent", "generic",
                "--tag", _current_branch(),
                env=env,
                check=True,
            )
            assert rerun.returncode == 0, rerun.stderr
