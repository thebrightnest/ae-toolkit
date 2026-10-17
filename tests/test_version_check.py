"""Tests for version currency awareness (src/aet/version_check.py)."""

from __future__ import annotations

import importlib.metadata
import subprocess

import pytest

from aet import version_check


class TestSemverComparison:
    @pytest.mark.parametrize(
        ("latest", "current"),
        [
            ("1.20.0", "1.19.0"),
            ("v1.20.0", "1.19.0"),
            ("1.19.1", "v1.19.0"),
            ("2.0.0", "1.99.99"),
            ("1.10.0", "1.9.0"),
            ("1.20.0", "1.20.0-rc.1"),
            ("1.21.0", "1.20.1.dev4+g2c2d533d2"),
            ("1.20.1", "1.20.1.dev4+g2c2d533d2"),
            ("1.20.0", "1.20.0rc1"),
        ],
    )
    def test_newer_version_is_detected(self, latest, current):
        assert version_check.is_newer_version(latest, current)

    @pytest.mark.parametrize(
        ("latest", "current"),
        [
            ("1.19.0", "1.19.0"),
            ("v1.19.0", "1.19.0"),
            ("1.18.5", "1.19.0"),
            ("1.20.0-rc.1", "1.20.0"),
            ("not-a-version", "1.19.0"),
            ("1.20.0", "garbage"),
            ("1.20.0", "1.20.1.dev4+g2c2d533d2"),
            ("1.20.0", "1.20.0+local"),
        ],
    )
    def test_same_older_or_unparseable_is_not_newer(self, latest, current):
        assert not version_check.is_newer_version(latest, current)

    def test_parse_semver_accepts_prefix_and_rejects_garbage(self):
        assert version_check.parse_semver("v1.2.3") == version_check.parse_semver("1.2.3")
        assert version_check.parse_semver("1.2") is None
        assert version_check.parse_semver("") is None


def _git(cwd, *args):
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
    )


@pytest.fixture
def tagged_remote(tmp_path):
    """A local git repository with release tags, usable as a remote URL."""
    repo = tmp_path / "remote"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "commit", "-q", "--allow-empty", "-m", "init")

    def tag(*names):
        for name in names:
            _git(repo, "tag", "-a", name, "-m", name)
        return str(repo)

    return tag


class TestFetchLatestRemoteTag:
    def test_returns_highest_stable_semver_tag(self, tagged_remote):
        url = tagged_remote("v1.9.0", "v1.10.0", "v1.2.0", "v2.0.0-rc.1", "nightly")
        assert version_check.fetch_latest_remote_tag(url) == "1.10.0"

    def test_returns_none_when_remote_has_no_release_tags(self, tagged_remote):
        url = tagged_remote("nightly")
        assert version_check.fetch_latest_remote_tag(url) is None

    def test_returns_none_when_remote_is_unreachable(self, tmp_path):
        assert version_check.fetch_latest_remote_tag(str(tmp_path / "missing")) is None


class TestVersionCache:
    def test_cache_lives_under_the_managed_data_dir(self, tmp_path, monkeypatch):
        monkeypatch.delenv("AET_DATA_DIR", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path))
        assert version_check.cache_path() == tmp_path / ".local/share/ae-toolkit/version-cache.json"
        monkeypatch.setenv("AET_DATA_DIR", str(tmp_path / "data"))
        assert version_check.cache_path() == tmp_path / "data" / "version-cache.json"

    def test_written_entry_round_trips_within_ttl(self, tmp_path):
        path = tmp_path / "nested" / "version-cache.json"
        version_check.write_version_cache("1.20.0", path=path, now=1_000.0)

        entry = version_check.read_version_cache(path=path, now=1_000.0 + 86_399)
        assert entry is not None
        assert entry["latest_version"] == "1.20.0"
        assert entry["checked_at"] == 1_000.0
        assert entry["source"] == "git-ls-remote"

    def test_entry_older_than_24h_is_treated_as_missing(self, tmp_path):
        path = tmp_path / "version-cache.json"
        version_check.write_version_cache("1.20.0", path=path, now=1_000.0)
        assert version_check.read_version_cache(path=path, now=1_000.0 + 86_401) is None

    def test_failed_lookup_is_cached_so_offline_users_are_not_retried_every_call(self, tmp_path):
        path = tmp_path / "version-cache.json"
        version_check.write_version_cache(None, path=path, now=1_000.0)
        entry = version_check.read_version_cache(path=path, now=1_001.0)
        assert entry is not None
        assert entry["latest_version"] is None

    @pytest.mark.parametrize("content", ["", "{not json", "[]", '{"checked_at": "soon"}'])
    def test_missing_or_corrupt_cache_reads_as_none(self, tmp_path, content):
        path = tmp_path / "version-cache.json"
        assert version_check.read_version_cache(path=path) is None
        path.write_text(content)
        assert version_check.read_version_cache(path=path) is None


@pytest.fixture
def interactive(monkeypatch, tmp_path):
    """An interactive terminal with no opt-out flags and an isolated cache."""
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("AET_NO_UPDATE_CHECK", raising=False)
    monkeypatch.setenv("AET_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(version_check, "_stdout_is_tty", lambda: True)
    return tmp_path / "data" / "version-cache.json"


class TestSuppression:
    def test_interactive_terminal_is_not_suppressed(self, interactive):
        assert not version_check.update_check_suppressed()

    @pytest.mark.parametrize(("name", "value"), [("AET_NO_UPDATE_CHECK", "1"), ("CI", "1"), ("CI", "true")])
    def test_opt_out_flags_suppress(self, interactive, monkeypatch, name, value):
        monkeypatch.setenv(name, value)
        assert version_check.update_check_suppressed()

    @pytest.mark.parametrize("value", ["", "0", "false"])
    def test_falsy_flag_values_do_not_suppress(self, interactive, monkeypatch, value):
        monkeypatch.setenv("CI", value)
        assert not version_check.update_check_suppressed()

    def test_non_tty_stdout_suppresses(self, interactive, monkeypatch):
        monkeypatch.setattr(version_check, "_stdout_is_tty", lambda: False)
        assert version_check.update_check_suppressed()

    def test_suppressed_check_never_queries_remote_or_writes_cache(self, interactive, monkeypatch, tagged_remote):
        monkeypatch.setenv("AET_NO_UPDATE_CHECK", "1")
        url = tagged_remote("v9.0.0")
        assert version_check.version_status("1.0.0", refresh=True, remote_url=url) is None
        assert not interactive.exists()


class TestVersionStatus:
    def test_cached_only_lookup_never_queries_remote(self, interactive, tagged_remote):
        url = tagged_remote("v9.0.0")
        status = version_check.version_status("1.0.0", remote_url=url)
        assert status is not None
        assert status.latest is None
        assert not status.update_available
        assert not interactive.exists()

    def test_refresh_queries_remote_and_populates_cache(self, interactive, tagged_remote):
        url = tagged_remote("v1.20.0")
        status = version_check.version_status("1.19.0", refresh=True, remote_url=url)
        assert status == version_check.VersionStatus(current="1.19.0", latest="1.20.0")
        assert status.update_available
        assert version_check.read_version_cache(path=interactive)["latest_version"] == "1.20.0"

    def test_fresh_cache_is_used_without_querying_remote(self, interactive, tmp_path):
        version_check.write_version_cache("1.20.0", path=interactive)
        status = version_check.version_status("1.20.0", refresh=True, remote_url=str(tmp_path / "missing"))
        assert status.latest == "1.20.0"
        assert not status.update_available


class TestVersionFlagNotice:
    def _run_version(self):
        from aet.cli.main import app
        from tests.cli._helpers import run_typer

        return run_typer(app, ["--version"])

    def test_notice_on_stderr_when_cache_has_newer_release(self, interactive):
        current = importlib.metadata.version("aet")
        version_check.write_version_cache("999.0.0", path=interactive)

        result = self._run_version()

        assert result.exit_code == 0
        assert result.stdout.strip() == f"aet {current}"
        assert (
            f"A newer version of aet is available: v999.0.0 (current: v{current}). Run 'aet update' to upgrade."
            in result.stderr
        )

    def test_no_notice_when_up_to_date(self, interactive):
        version_check.write_version_cache(importlib.metadata.version("aet"), path=interactive)
        result = self._run_version()
        assert result.exit_code == 0
        assert "newer version" not in result.stderr

    def test_no_notice_when_suppressed(self, interactive, monkeypatch):
        monkeypatch.setenv("CI", "1")
        version_check.write_version_cache("999.0.0", path=interactive)
        result = self._run_version()
        assert result.exit_code == 0
        assert "newer version" not in result.stderr

    def test_version_flag_never_queries_remote(self, interactive):
        result = self._run_version()
        assert result.exit_code == 0
        assert not interactive.exists()
