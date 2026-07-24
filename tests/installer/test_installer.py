"""Tests for the one-line curl installer (scripts/install.sh).

Coverage rules this module enforces:

1. Default configuration is the primary test case. ``run_installer`` invokes
   ``install.sh`` under ``/bin/bash`` with no ``--agent``, ``--skills-dir``,
   or ``--bin-dir`` flags and ``AET_SKILLS_DIR`` unset, so the bash-3.2 empty-
   array path and the default derivation of ``AET_BIN_DIR``/``AET_DATA_DIR``
   are exercised.

2. The unresolved ``aet`` link is executed. Tests read the link with
   ``os.readlink`` before and after running a subcommand through it; resolving
   the link first is what hid the symlink-corruption defect.

3. The subcommand reaches the callback body. ``--help`` and ``--version`` are
   eager Typer options that exit before callbacks run, so a real subcommand
   such as ``aet status`` is used.

4. Version is asserted exactly against ``git describe --tags``, not by
   substring, so a stale version at a newer tag cannot pass unnoticed.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
INSTALLER = REPO_ROOT / "scripts" / "install.sh"
BIN_BASH = Path("/bin/bash")


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
    """Run the installer script under ``/bin/bash`` with the given args."""
    assert BIN_BASH.exists(), f"{BIN_BASH} is required for installer tests"
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    result = subprocess.run(
        [str(BIN_BASH), str(INSTALLER), *args],
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
                "--repo",
                str(REPO_ROOT),
                "--agent",
                "generic",
                env=env,
                check=True,
            )
            stdout = result.stdout.lower()
            assert "would" in stdout
            assert not bin_dir.exists()
            assert not skills_dir.exists()
            assert not data_dir.exists()


class TestInstallerBash:
    """The installer is exercised under the macOS-shipped ``/bin/bash``."""

    def test_installer_runs_under_bin_bash(self):
        assert BIN_BASH.exists(), f"{BIN_BASH} is required for installer tests"
        result = run_installer("--help")
        assert result.returncode == 0, result.stderr


class TestInstallerSmoke:
    """End-to-end smoke tests against a local repo checkout."""

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
                "--repo",
                str(REPO_ROOT),
                "--agent",
                "generic",
                "--tag",
                _current_branch(),
                "--bin-dir",
                str(bin_dir),
                "--skills-dir",
                str(skills_dir),
                env=env,
                check=True,
            )

            # aet is symlinked into the bin dir
            aet_link = bin_dir / "aet"
            assert aet_link.is_symlink(), f"{aet_link} is not a symlink"
            assert aet_link.exists(), f"{aet_link} does not exist"
            assert "venv/bin/aet" in str(aet_link.readlink())

            # the installed aet binary runs through the unresolved link
            help_result = subprocess.run(
                [str(aet_link), "--help"],
                capture_output=True,
                text=True,
                env=env,
            )
            assert help_result.returncode == 0, help_result.stderr
            assert "Agentic Engineering Toolkit" in help_result.stdout

            # skills are linked from the cloned repo
            setup_skill_dir = skills_dir / "aet-setup"
            assert setup_skill_dir.is_symlink(), f"{setup_skill_dir} is not a symlink"
            setup_skill = setup_skill_dir / "SKILL.md"
            assert setup_skill.is_file(), f"{setup_skill} is not a file"

            # idempotent re-run exits zero
            rerun = run_installer(
                "--repo",
                str(REPO_ROOT),
                "--agent",
                "generic",
                "--tag",
                _current_branch(),
                env=env,
                check=True,
            )
            assert rerun.returncode == 0, rerun.stderr

    def test_version_matches_git_describe(self):
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
                "--repo",
                str(REPO_ROOT),
                "--agent",
                "generic",
                "--tag",
                _current_branch(),
                "--bin-dir",
                str(bin_dir),
                "--skills-dir",
                str(skills_dir),
                env=env,
                check=True,
            )

            aet_link = bin_dir / "aet"
            version_result = subprocess.run(
                [str(aet_link), "--version"],
                capture_output=True,
                text=True,
                env=env,
            )
            assert version_result.returncode == 0, version_result.stderr

            # Exact match against the version reported by the installed venv,
            # which is derived from the git tag via hatch-vcs.
            venv_python = data_dir / "venv" / "bin" / "python"
            expected_version = subprocess.run(
                [str(venv_python), "-c", "from importlib.metadata import version; print(version('aet'))"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            expected = f"aet {expected_version}"
            assert version_result.stdout.strip() == expected, (
                f"Expected {expected!r}, got {version_result.stdout.strip()!r}"
            )

    def test_installs_with_no_flags(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            home = tmp_path / "home"
            home.mkdir()

            # Empty strings let install.sh derive these from HOME, covering
            # the default derivation path while overriding the autouse test
            # fixture that otherwise pins AET_BIN_DIR to a pytest temp dir.
            env = {
                "HOME": str(home),
                "AET_BIN_DIR": "",
                "AET_DATA_DIR": "",
            }
            run_installer(
                "--repo",
                str(REPO_ROOT),
                "--tag",
                _current_branch(),
                env=env,
                check=True,
            )

            bin_dir = home / ".local" / "bin"
            aet_link = bin_dir / "aet"
            assert aet_link.is_symlink(), f"{aet_link} is not a symlink"
            assert aet_link.exists(), f"{aet_link} does not exist"
            assert "venv/bin/aet" in str(aet_link.readlink())

            # The default derivation of AET_DATA_DIR created the install tree.
            data_dir = home / ".local" / "share" / "ae-toolkit"
            assert data_dir.is_dir(), f"{data_dir} is not a directory"

    def test_subcommand_through_link_does_not_rewrite_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            home = tmp_path / "home"
            home.mkdir()

            env = {
                "HOME": str(home),
                "AET_BIN_DIR": "",
                "AET_DATA_DIR": "",
            }
            run_installer(
                "--repo",
                str(REPO_ROOT),
                "--tag",
                _current_branch(),
                env=env,
                check=True,
            )

            bin_dir = home / ".local" / "bin"
            aet_link = bin_dir / "aet"
            assert aet_link.is_symlink(), f"{aet_link} is not a symlink"
            before = os.readlink(aet_link)

            # Run a real subcommand (not --help/--version) through the
            # unresolved link so the callback body executes.
            repo_dir = home / ".local" / "share" / "ae-toolkit" / "repo"
            result = subprocess.run(
                [str(aet_link), "status"],
                capture_output=True,
                text=True,
                env=env,
                cwd=str(repo_dir),
            )
            assert result.returncode == 0, result.stderr

            after = os.readlink(aet_link)
            assert before == after, f"aet link changed from {before!r} to {after!r}"
