"""Tests for `aet release-prep` (src/aet/cli/release_prep.py).

Covers config loading, version-source detection (setuptools-scm, package.json,
VERSION, pyproject, composer.json, git tags), document-path and version-scheme
resolution, baseline resolution including tags unreachable from HEAD, commit
classification, and semantic-version bump calculation.
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


# --- helpers for the repo-shaped fixtures below ----------------------------


def _init_repo(path: Path) -> None:
    """Create a git repo with a deterministic identity."""
    subprocess.run(["git", "init", "-b", "main"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, check=True, capture_output=True)


def _commit(path: Path, message: str, filename: str = "file.txt", content: str | None = None) -> str:
    """Commit *content* to *filename* and return the resulting sha."""
    (path / filename).parent.mkdir(parents=True, exist_ok=True)
    (path / filename).write_text(content if content is not None else message)
    subprocess.run(["git", "add", "-A"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", message], cwd=path, check=True, capture_output=True)
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=path, check=True, capture_output=True, text=True
    ).stdout.strip()


def _write_config(path: Path, section: dict) -> None:
    """Write a ``release_prep`` section into .agents/aet-config.json."""
    (path / ".agents").mkdir(parents=True, exist_ok=True)
    (path / ".agents" / "aet-config.json").write_text(json.dumps({"release_prep": section}))


class TestLoadConfig:
    """The release_prep config section degrades to {} rather than failing."""

    def test_missing_file_is_empty(self, tmp_path: Path) -> None:
        assert release_prep.load_config(tmp_path) == {}

    def test_reads_section(self, tmp_path: Path) -> None:
        _write_config(tmp_path, {"product_path": "docs/PRODUCT.md"})

        assert release_prep.load_config(tmp_path) == {"product_path": "docs/PRODUCT.md"}

    def test_malformed_json_is_empty(self, tmp_path: Path) -> None:
        (tmp_path / ".agents").mkdir()
        (tmp_path / ".agents" / "aet-config.json").write_text("{not json")

        assert release_prep.load_config(tmp_path) == {}

    def test_absent_section_is_empty(self, tmp_path: Path) -> None:
        (tmp_path / ".agents").mkdir()
        (tmp_path / ".agents" / "aet-config.json").write_text(json.dumps({"boundary_contract": {}}))

        assert release_prep.load_config(tmp_path) == {}


class TestSetuptoolsScmDetection:
    """A dynamic version has no file to edit; the tag is the version."""

    def test_scm_wins_over_package_json(self, tmp_path: Path) -> None:
        # The shape that misdetected before: a frontend package.json beside a
        # Python project whose real version comes from git tags.
        (tmp_path / "package.json").write_text(json.dumps({"version": "1.0.0"}))
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "x"\ndynamic = ["version"]\n\n[tool.setuptools_scm]\nversion_file = "_v.py"\n'
        )
        _init_repo(tmp_path)
        _commit(tmp_path, "initial")
        subprocess.run(["git", "tag", "v0.9.0"], cwd=tmp_path, check=True, capture_output=True)

        source, version = release_prep.detect_version_source(tmp_path)

        assert source == "setuptools-scm"
        assert version == "v0.9.0"

    def test_dynamic_without_scm_table_is_not_scm(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text(json.dumps({"version": "1.0.0"}))
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\ndynamic = ["version"]\n')

        source, _ = release_prep.detect_version_source(tmp_path)

        assert source == "package.json"


class TestAdditionalVersionSources:
    """pyproject and composer.json join package.json and VERSION."""

    def test_pyproject_project_version(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\nversion = "0.1.0"\n')

        assert release_prep.detect_version_source(tmp_path) == ("pyproject.toml", "0.1.0")

    def test_pyproject_poetry_version(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text('[tool.poetry]\nname = "x"\nversion = "2.0.0"\n')

        assert release_prep.detect_version_source(tmp_path) == ("pyproject.toml", "2.0.0")

    def test_composer_version(self, tmp_path: Path) -> None:
        (tmp_path / "composer.json").write_text(json.dumps({"version": "3.1.0"}))

        assert release_prep.detect_version_source(tmp_path) == ("composer.json", "3.1.0")

    def test_composer_without_version_falls_through(self, tmp_path: Path) -> None:
        # Laravel's composer.json carries no version field.
        (tmp_path / "composer.json").write_text(json.dumps({"name": "acme/app"}))
        _init_repo(tmp_path)

        assert release_prep.detect_version_source(tmp_path) == ("none", "0.0.0")

    def test_configured_version_file_wins(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text(json.dumps({"version": "1.0.0"}))
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\nversion = "7.7.7"\n')

        source, version = release_prep.detect_version_source(tmp_path, {"version_file": "pyproject.toml"})

        assert source == "pyproject.toml"
        assert version == "7.7.7"


class TestResolveDocumentPaths:
    """Config wins, then an existing file, then the default location."""

    def test_detects_existing_layout(self, tmp_path: Path) -> None:
        (tmp_path / "content").mkdir()
        (tmp_path / "content" / "CHANGELOG.md").write_text("# Changelog\n")
        (tmp_path / "PRODUCT.md").write_text("# Product\n")

        docs = release_prep.resolve_document_paths(tmp_path)

        assert docs["changelog"] == {"path": "content/CHANGELOG.md", "origin": "detected", "exists": True}
        assert docs["product"] == {"path": "PRODUCT.md", "origin": "detected", "exists": True}

    def test_defaults_when_nothing_exists(self, tmp_path: Path) -> None:
        docs = release_prep.resolve_document_paths(tmp_path)

        assert docs["changelog"]["path"] == "CHANGELOG.md"
        assert docs["changelog"]["origin"] == "default"
        assert docs["product"]["path"] == "docs/PRODUCT.md"
        assert docs["product"]["exists"] is False

    def test_config_overrides_detection(self, tmp_path: Path) -> None:
        (tmp_path / "PRODUCT.md").write_text("# Product\n")

        docs = release_prep.resolve_document_paths(tmp_path, {"product_path": "docs/PRODUCT.md"})

        assert docs["product"]["path"] == "docs/PRODUCT.md"
        assert docs["product"]["origin"] == "config"
        assert docs["product"]["exists"] is False

    def test_root_changelog_preferred_over_nested(self, tmp_path: Path) -> None:
        (tmp_path / "CHANGELOG.md").write_text("# Changelog\n")
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "CHANGELOG.md").write_text("# Other\n")

        assert release_prep.resolve_document_paths(tmp_path)["changelog"]["path"] == "CHANGELOG.md"


class TestDetectVersionScheme:
    """Scheme resolution: config, then changelog shape, then version source."""

    def test_config_wins(self, tmp_path: Path) -> None:
        scheme, reason = release_prep.detect_version_scheme(tmp_path, {"version_scheme": "dated"}, None, "package.json")

        assert (scheme, reason) == ("dated", "config")

    def test_unknown_scheme_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="Unknown version_scheme"):
            release_prep.detect_version_scheme(tmp_path, {"version_scheme": "calendar"}, None, "package.json")

    def test_dated_changelog_infers_dated(self, tmp_path: Path) -> None:
        # A continuously deployed project: dated headings, no version headings.
        (tmp_path / "CHANGELOG.md").write_text("# Changelog\n\n## 2026-09-09\n\nShipped a thing.\n")

        scheme, reason = release_prep.detect_version_scheme(tmp_path, {}, "CHANGELOG.md", "pyproject.toml")

        assert (scheme, reason) == ("dated", "changelog-headings-are-dates")

    def test_versioned_headings_are_not_dated(self, tmp_path: Path) -> None:
        (tmp_path / "CHANGELOG.md").write_text("# Changelog\n\n## [1.2.0] - 2026-09-09\n\nShipped.\n")

        scheme, _ = release_prep.detect_version_scheme(tmp_path, {}, "CHANGELOG.md", "package.json")

        assert scheme == "semver-file"

    def test_scm_source_implies_tag_scheme(self, tmp_path: Path) -> None:
        scheme, _ = release_prep.detect_version_scheme(tmp_path, {}, None, "setuptools-scm")

        assert scheme == "semver-tag"

    def test_editable_manifest_implies_file_scheme(self, tmp_path: Path) -> None:
        scheme, _ = release_prep.detect_version_scheme(tmp_path, {}, None, "package.json")

        assert scheme == "semver-file"


class TestBaselineResolution:
    """The release window must never silently widen to the whole history."""

    def test_latest_reachable_tag(self, tmp_path: Path) -> None:
        _init_repo(tmp_path)
        _commit(tmp_path, "first")
        subprocess.run(["git", "tag", "v1.0.0"], cwd=tmp_path, check=True, capture_output=True)
        _commit(tmp_path, "feat: second")

        ref, reason = release_prep.resolve_baseline(tmp_path)

        assert (ref, reason) == ("v1.0.0", "latest-reachable-tag")

    def test_unreachable_tag_is_not_a_baseline(self, tmp_path: Path) -> None:
        # The atelier shape: tags arrive with a vendored import on an abandoned
        # line of history, so `git describe` fatals and the old code fell back
        # to the entire history.
        _init_repo(tmp_path)
        _commit(tmp_path, "upstream")
        subprocess.run(["git", "tag", "v0.52.113"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(["git", "checkout", "--orphan", "fresh"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(["git", "rm", "-rf", "."], cwd=tmp_path, check=True, capture_output=True)
        _commit(tmp_path, "feat: fresh start", "new.txt")

        assert release_prep.reachable_tags(tmp_path) == []
        assert release_prep.unreachable_tags(tmp_path) == ["v0.52.113"]

        ref, reason = release_prep.resolve_baseline(tmp_path)

        assert ref is None
        assert reason == "no-baseline"

    def test_changelog_commit_is_the_fallback(self, tmp_path: Path) -> None:
        _init_repo(tmp_path)
        _commit(tmp_path, "chore: init")
        released = _commit(tmp_path, "docs: release notes", "CHANGELOG.md", "# Changelog\n\n## [1.0.0]\n")
        _commit(tmp_path, "feat: since release", "app.py")

        ref, reason = release_prep.resolve_baseline(tmp_path, changelog_path="CHANGELOG.md")

        assert (ref, reason) == (released, "last-changelog-commit")

    def test_config_baseline_wins_over_tag(self, tmp_path: Path) -> None:
        _init_repo(tmp_path)
        first = _commit(tmp_path, "first")
        subprocess.run(["git", "tag", "v1.0.0"], cwd=tmp_path, check=True, capture_output=True)
        _commit(tmp_path, "feat: second")

        ref, reason = release_prep.resolve_baseline(tmp_path, {"baseline_ref": first})

        assert (ref, reason) == (first, "config")

    def test_since_flag_wins_over_config(self, tmp_path: Path) -> None:
        _init_repo(tmp_path)
        first = _commit(tmp_path, "first")
        subprocess.run(["git", "tag", "v1.0.0"], cwd=tmp_path, check=True, capture_output=True)
        _commit(tmp_path, "feat: second")

        ref, reason = release_prep.resolve_baseline(tmp_path, {"baseline_ref": "v1.0.0"}, since=first)

        assert (ref, reason) == (first, "since-flag")

    def test_bad_since_raises(self, tmp_path: Path) -> None:
        _init_repo(tmp_path)
        _commit(tmp_path, "first")

        with pytest.raises(release_prep.GitError, match="does not resolve"):
            release_prep.resolve_baseline(tmp_path, since="v9.9.9")

    def test_bad_config_baseline_raises(self, tmp_path: Path) -> None:
        _init_repo(tmp_path)
        _commit(tmp_path, "first")

        with pytest.raises(release_prep.GitError, match="baseline_ref"):
            release_prep.resolve_baseline(tmp_path, {"baseline_ref": "nope"})


class TestBuildReport:
    """End-to-end report shape across the three repo archetypes."""

    def test_dated_project_gets_no_bump(self, tmp_path: Path) -> None:
        _init_repo(tmp_path)
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "fleet"\nversion = "0.1.0"\n')
        _commit(tmp_path, "docs: log", "CHANGELOG.md", "# Changelog\n\n## 2026-09-09\n\nShipped.\n")
        _commit(tmp_path, "feat: add a thing", "app.py")

        report = release_prep.build_report(tmp_path)

        assert report["versionScheme"] == "dated"
        assert report["suggestedBump"] is None
        assert report["nextVersion"] is None
        assert report["releaseDate"]

    def test_semver_project_gets_a_bump(self, tmp_path: Path) -> None:
        _init_repo(tmp_path)
        (tmp_path / "VERSION").write_text("1.2.0")
        _commit(tmp_path, "docs: log", "CHANGELOG.md", "# Changelog\n\n## [1.2.0] - 2026-01-01\n")
        _commit(tmp_path, "feat: add a thing", "app.py")

        report = release_prep.build_report(tmp_path)

        assert report["versionScheme"] == "semver-file"
        assert report["suggestedBump"] == "minor"
        assert report["nextVersion"] == "1.3.0"
        assert report["commitCount"] == 1

    def test_bootstrap_when_product_missing(self, tmp_path: Path) -> None:
        _init_repo(tmp_path)
        _commit(tmp_path, "docs: log", "CHANGELOG.md", "# Changelog\n\n## [1.0.0] - 2026-01-01\n")
        _commit(tmp_path, "feat: thing", "app.py")

        assert release_prep.build_report(tmp_path)["bootstrap"] is True

    def test_not_bootstrap_when_both_documents_exist(self, tmp_path: Path) -> None:
        _init_repo(tmp_path)
        (tmp_path / "VERSION").write_text("1.0.0")
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "PRODUCT.md").write_text("# Product\n")
        _commit(tmp_path, "docs: seed", "CHANGELOG.md", "# Changelog\n\n## [1.0.0] - 2026-01-01\n")
        _commit(tmp_path, "feat: thing", "app.py")

        report = release_prep.build_report(tmp_path)

        assert report["bootstrap"] is False
        assert report["documents"]["product"]["path"] == "docs/PRODUCT.md"

    def test_since_narrows_the_window(self, tmp_path: Path) -> None:
        _init_repo(tmp_path)
        _commit(tmp_path, "feat: one")
        cut = _commit(tmp_path, "feat: two", "b.txt")
        _commit(tmp_path, "feat: three", "c.txt")

        report = release_prep.build_report(tmp_path, since=cut)

        assert report["commitCount"] == 1
        assert report["baselineReason"] == "since-flag"


class TestErrorReporting:
    """A bad ref exits non-zero with a JSON error rather than a traceback."""

    def test_bad_since_exits_nonzero(self, tmp_path: Path) -> None:
        _init_repo(tmp_path)
        _commit(tmp_path, "first")

        with patch("sys.stdout") as mock_stdout:
            rc = release_prep.main(["--repo-root", str(tmp_path), "--since", "v9.9.9"])

        assert rc == 1
        output = "".join(call.args[0] for call in mock_stdout.write.call_args_list)
        assert "error" in json.loads(output)
