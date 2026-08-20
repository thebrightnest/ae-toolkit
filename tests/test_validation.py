"""Tests for the validation helper module."""

from __future__ import annotations

import json
from pathlib import Path

from aet import validation


class TestSelectTargetedTests:
    """Path-based floor: same-directory or matching-name test files."""

    def test_empty_change_set_falls_back_to_full_suite(self):
        assert validation.select_targeted_tests([]) == ["tests/"]

    def test_shared_infrastructure_runs_full_suite(self):
        for path in (
            "pyproject.toml",
            "Makefile",
            "tests/conftest.py",
            "tests/fixtures/data.json",
        ):
            assert validation.select_targeted_tests([path]) == ["tests/"], path

    def test_changed_test_file_includes_itself(self):
        assert validation.select_targeted_tests(["tests/test_foo.py"]) == [
            "tests/test_foo.py"
        ]

    def test_changed_source_file_matches_same_directory_test(self, tmp_path: Path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "src" / "aet").mkdir(parents=True)
        (repo / "src" / "aet" / "foo.py").write_text("x")
        (repo / "tests").mkdir()
        (repo / "tests" / "test_foo.py").write_text("x")

        assert validation.select_targeted_tests(
            ["src/aet/foo.py"], repo_root=str(repo)
        ) == ["tests/test_foo.py"]

    def test_changed_source_file_matches_name_anywhere_under_tests(self, tmp_path: Path):
        repo = tmp_path / "repo"
        (repo / "src" / "aet").mkdir(parents=True)
        (repo / "src" / "aet" / "foo.py").write_text("x")
        (repo / "tests" / "cli").mkdir(parents=True)
        (repo / "tests" / "cli" / "test_foo.py").write_text("x")

        targets = validation.select_targeted_tests(
            ["src/aet/foo.py"], repo_root=str(repo)
        )
        assert "tests/cli/test_foo.py" in targets

    def test_changed_source_in_subdirectory_matches_same_directory_test(self, tmp_path: Path):
        repo = tmp_path / "repo"
        (repo / "src" / "aet" / "cli").mkdir(parents=True)
        (repo / "src" / "aet" / "cli" / "bar.py").write_text("x")
        (repo / "tests" / "cli").mkdir(parents=True)
        (repo / "tests" / "cli" / "test_bar.py").write_text("x")

        assert validation.select_targeted_tests(
            ["src/aet/cli/bar.py"], repo_root=str(repo)
        ) == ["tests/cli/test_bar.py"]

    def test_unmapped_path_outside_src_falls_back_to_full_suite(self):
        assert validation.select_targeted_tests(["README.md"]) == ["tests/"]
        assert validation.select_targeted_tests(["scripts/unknown.sh"]) == ["tests/"]

    def test_deduplicates_and_sorts_targets(self, tmp_path: Path):
        repo = tmp_path / "repo"
        (repo / "src" / "aet").mkdir(parents=True)
        (repo / "src" / "aet" / "foo.py").write_text("x")
        (repo / "src" / "aet" / "bar.py").write_text("x")
        (repo / "tests").mkdir()
        (repo / "tests" / "test_bar.py").write_text("x")
        (repo / "tests" / "test_foo.py").write_text("x")

        assert validation.select_targeted_tests(
            ["src/aet/foo.py", "src/aet/bar.py"], repo_root=str(repo)
        ) == ["tests/test_bar.py", "tests/test_foo.py"]


class TestIsSharedPath:
    def test_known_shared_paths(self):
        assert validation._is_shared("pyproject.toml")
        assert validation._is_shared("Makefile")
        assert validation._is_shared("tests/conftest.py")
        assert validation._is_shared("tests/fixtures/skills-lint/legacy.md")

    def test_regular_paths_are_not_shared(self):
        assert not validation._is_shared("src/aet/foo.py")
        assert not validation._is_shared("tests/test_foo.py")


class TestTargetedTestsPath:
    def test_returns_run_scoped_json_file(self):
        path = validation.targeted_tests_path("/repo", "run-1")
        assert path == Path("/repo/.agents/runs/run-1/implement-targeted-tests.json")


class TestReadTargetedTests:
    def test_missing_file_returns_empty_list(self, tmp_path: Path):
        path = tmp_path / "missing.json"
        assert validation.read_targeted_tests(str(path)) == []

    def test_malformed_json_returns_empty_list(self, tmp_path: Path):
        path = tmp_path / "bad.json"
        path.write_text("not json", encoding="utf-8")
        assert validation.read_targeted_tests(str(path)) == []

    def test_reads_list_of_commands(self, tmp_path: Path):
        path = tmp_path / "good.json"
        path.write_text(
            json.dumps(["pytest tests/test_foo.py"]), encoding="utf-8"
        )
        assert validation.read_targeted_tests(str(path)) == ["pytest tests/test_foo.py"]
