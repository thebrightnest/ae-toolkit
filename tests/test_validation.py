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


class TestExtractTestTargets:
    def test_bare_pytest_runs_full_suite(self):
        assert validation.extract_test_targets(["pytest"]) == {"tests/"}

    def test_python_m_pytest_runs_full_suite(self):
        assert validation.extract_test_targets(["python -m pytest"]) == {"tests/"}

    def test_pytest_with_file_target(self):
        assert validation.extract_test_targets(["pytest tests/test_foo.py"]) == {
            "tests/test_foo.py"
        }

    def test_pytest_with_directory_target(self):
        assert validation.extract_test_targets(["pytest tests/cli/"]) == {
            "tests/cli"
        }

    def test_pytest_with_nodeid_target(self):
        assert validation.extract_test_targets(
            ["pytest tests/test_foo.py::test_x"]
        ) == {"tests/test_foo.py"}

    def test_ignores_non_pytest_commands(self):
        assert validation.extract_test_targets(["npm test"]) == set()

    def test_drops_flags(self):
        assert validation.extract_test_targets(
            ["pytest -q -k slow tests/test_bar.py"]
        ) == {"tests/test_bar.py"}

    def test_multiple_commands_merge_targets(self):
        assert validation.extract_test_targets(
            ["pytest tests/test_foo.py", "pytest tests/cli/test_bar.py"]
        ) == {"tests/test_foo.py", "tests/cli/test_bar.py"}


class TestCoversTest:
    def test_file_target_covers_nodeid_in_file(self):
        assert validation.covers_test(
            {"tests/test_foo.py"}, "tests/test_foo.py::test_x"
        )

    def test_file_target_covers_file_itself(self):
        assert validation.covers_test({"tests/test_foo.py"}, "tests/test_foo.py")

    def test_file_target_does_not_cover_other_file(self):
        assert not validation.covers_test(
            {"tests/test_foo.py"}, "tests/test_bar.py::test_x"
        )

    def test_directory_target_covers_children(self):
        assert validation.covers_test(
            {"tests/cli"}, "tests/cli/test_bar.py::test_x"
        )

    def test_full_suite_target_covers_all(self):
        assert validation.covers_test({"tests/"}, "tests/anything.py::test_x")

    def test_uncovered_when_targets_empty(self):
        assert not validation.covers_test(set(), "tests/test_foo.py::test_x")


class TestGapAnalysis:
    def test_no_missed_tests_when_all_covered(self):
        assert validation.gap_analysis(
            ["tests/test_foo.py::test_a"],
            ["pytest tests/test_foo.py"],
        ) == {"missed_tests": [], "reason": ""}

    def test_reports_missed_tests(self):
        result = validation.gap_analysis(
            [
                "tests/test_foo.py::test_a",
                "tests/test_bar.py::test_b",
            ],
            ["pytest tests/test_foo.py"],
        )
        assert result["missed_tests"] == ["tests/test_bar.py::test_b"]
        assert result["reason"] == "not in implement targeted tests"

    def test_full_suite_command_covers_every_failure(self):
        assert validation.gap_analysis(
            ["tests/test_foo.py::test_a", "tests/test_bar.py::test_b"],
            ["pytest tests/"],
        ) == {"missed_tests": [], "reason": ""}
