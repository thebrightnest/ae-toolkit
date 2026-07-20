"""Tests for `aet release-prep` (src/aet/cli/release_prep.py).

Covers version-source detection across package.json/VERSION/git-tag, commit
classification including conventional-commit prefixes and keyword fallbacks,
and semantic-version bump calculation including prerelease stripping.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from aet.cli import release_prep


class TestDetectVersionSource:
    """Version-source detection order: package.json > VERSION > git-tag > none."""

    def test_package_json_wins(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text(json.dumps({"version": "2.3.4"}))
        (tmp_path / "VERSION").write_text("9.9.9")

        source, version = release_prep.detect_version_source(tmp_path)

        assert source == "package.json"
        assert version == "2.3.4"

    def test_version_file_when_no_package_json(self, tmp_path: Path) -> None:
        (tmp_path / "VERSION").write_text("1.2.3\n")

        source, version = release_prep.detect_version_source(tmp_path)

        assert source == "VERSION"
        assert version == "1.2.3"

    def test_git_tag_when_no_files(self, tmp_path: Path) -> None:
        subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True, capture_output=True
        )
        subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True, capture_output=True)
        (tmp_path / "file.txt").write_text("x")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(["git", "tag", "v3.0.0"], cwd=tmp_path, check=True, capture_output=True)

        source, version = release_prep.detect_version_source(tmp_path)

        assert source == "git-tag"
        assert version == "v3.0.0"

    def test_fallback_to_zero(self, tmp_path: Path) -> None:
        subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, check=True, capture_output=True)

        source, version = release_prep.detect_version_source(tmp_path)

        assert source == "none"
        assert version == "0.0.0"


class TestClassifyCommit:
    """Commit classification through conventional commits and keyword fallbacks."""

    @pytest.mark.parametrize(
        ("subject", "body", "expected"),
        [
            ("feat: add widget", "", "feature"),
            ("feat(scope): add widget", "", "feature"),
            ("feature: add widget", "", "feature"),
            ("fix: handle edge case", "", "fix"),
            ("bugfix: handle edge case", "", "fix"),
            ("docs: update README", "", "docs"),
            ("chore: tidy up", "", "chore"),
            ("build: update deps", "", "chore"),
            ("ci: update workflow", "", "chore"),
            ("refactor: simplify", "", "refactor"),
            ("style: format", "", "style"),
            ("test: add tests", "", "test"),
            ("perf: speed up", "", "perf"),
            ("feat!: redesign API", "", "breaking"),
            ("fix: something", "BREAKING CHANGE: drops support", "breaking"),
            ("Add new feature", "", "feature"),
            ("Implement new parser", "", "feature"),
            ("Fix broken login", "", "fix"),
            ("Fix bug in parser", "", "fix"),
            ("Update dependencies", "", "improvement"),
            ("Improve performance", "", "improvement"),
            ("Remove deprecated code", "", "removal"),
            ("Delete unused files", "", "removal"),
            ("something random", "", "other"),
        ],
    )
    def test_classify(self, subject: str, body: str, expected: str) -> None:
        assert release_prep.classify_commit(subject, body) == expected


class TestDetermineBump:
    """Semantic bump from classified commits."""

    def test_breaking_yields_major(self) -> None:
        commits = [{"type": "feature"}, {"type": "breaking"}]
        assert release_prep.determine_bump(commits) == "major"

    def test_feature_yields_minor(self) -> None:
        commits = [{"type": "fix"}, {"type": "feature"}]
        assert release_prep.determine_bump(commits) == "minor"

    def test_fix_yields_patch(self) -> None:
        commits = [{"type": "fix"}]
        assert release_prep.determine_bump(commits) == "patch"

    def test_improvement_yields_patch(self) -> None:
        commits = [{"type": "improvement"}]
        assert release_prep.determine_bump(commits) == "patch"

    def test_other_defaults_to_patch(self) -> None:
        commits = [{"type": "chore"}, {"type": "other"}]
        assert release_prep.determine_bump(commits) == "patch"


class TestCalculateNextVersion:
    """Next-version calculation including v-prefix and prerelease stripping."""

    def test_from_zero(self) -> None:
        assert release_prep.calculate_next_version("0.0.0", "patch") == "1.0.0"
        assert release_prep.calculate_next_version("", "patch") == "1.0.0"

    def test_v_prefix_stripped(self) -> None:
        assert release_prep.calculate_next_version("v1.2.3", "patch") == "1.2.4"

    def test_prerelease_stripped(self) -> None:
        assert release_prep.calculate_next_version("1.0.0-beta3", "minor") == "1.0.0"

    def test_bump_major(self) -> None:
        assert release_prep.calculate_next_version("1.2.3", "major") == "2.0.0"

    def test_bump_minor(self) -> None:
        assert release_prep.calculate_next_version("1.2.3", "minor") == "1.3.0"

    def test_bump_patch(self) -> None:
        assert release_prep.calculate_next_version("1.2.3", "patch") == "1.2.4"

    def test_unparseable_returns_current(self) -> None:
        assert release_prep.calculate_next_version("not-a-version", "patch") == "not-a-version"


class TestGetCommitsSince:
    """Commit parsing from git log format."""

    def test_parses_commits(self, tmp_path: Path) -> None:
        subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True, capture_output=True
        )
        subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True, capture_output=True)
        (tmp_path / "a.txt").write_text("a")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "first"], cwd=tmp_path, check=True, capture_output=True)

        commits = release_prep.get_commits_since(None, tmp_path)

        assert len(commits) == 1
        assert commits[0]["subject"] == "first"
        assert "hash" in commits[0]
        assert "fullHash" in commits[0]

    def test_empty_when_no_commits(self, tmp_path: Path) -> None:
        subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, check=True, capture_output=True)

        commits = release_prep.get_commits_since(None, tmp_path)

        assert commits == []


class TestMain:
    """End-to-end smoke test of the CLI entry point."""

    def test_outputs_valid_json(self, tmp_path: Path) -> None:
        subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True, capture_output=True
        )
        subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True, capture_output=True)
        (tmp_path / "VERSION").write_text("0.5.0")
        (tmp_path / "file.txt").write_text("x")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "feat: add thing"], cwd=tmp_path, check=True, capture_output=True)

        with patch("sys.stdout") as mock_stdout:
            rc = release_prep.main(["--repo-root", str(tmp_path)])

        assert rc == 0
        output = "".join(call.args[0] for call in mock_stdout.write.call_args_list)
        data = json.loads(output)
        assert data["versionSource"] == "VERSION"
        assert data["currentVersion"] == "0.5.0"
        assert data["suggestedBump"] == "minor"
        assert data["nextVersion"] == "0.6.0"
        assert len(data["commits"]) == 1
        assert data["commits"][0]["type"] == "feature"
