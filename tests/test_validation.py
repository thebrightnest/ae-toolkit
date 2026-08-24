"""Tests for the validation helper module."""

from __future__ import annotations

import json
from pathlib import Path

from aet import validation


class TestSelectTargetedTests:
    """The stage-session entry point onto the one selection authority."""

    def test_it_delegates_to_change_scope(self, monkeypatch):
        """One authority: a stage session and `make validate` cannot disagree."""
        seen = {}

        def fake(paths, repo_root=None):
            seen["paths"] = paths
            return ["tests/sentinel.py"]

        monkeypatch.setattr(validation.change_scope, "targets", fake)

        assert validation.select_targeted_tests(["src/aet/identity.py"]) == [
            "tests/sentinel.py"
        ]
        assert seen["paths"] == ["src/aet/identity.py"]

    def test_empty_change_set_falls_back_to_full_suite(self):
        """From this caller an empty list means "undetermined", not "nothing"."""
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

    def test_prose_only_change_runs_nothing(self):
        assert validation.select_targeted_tests(["README.md"]) == []

    def test_a_real_module_selects_only_tests_that_exist(self):
        """The rule this replaced named a non-existent file for 69 of 82 modules."""
        repo_root = Path(__file__).resolve().parents[1]

        targets = validation.select_targeted_tests(
            ["src/aet/identity.py"], repo_root=repo_root
        )

        assert targets and targets != ["tests/"]
        for target in targets:
            assert (repo_root / target).exists(), target

    def test_an_unreachable_source_path_falls_back_to_full_suite(self):
        assert validation.select_targeted_tests(["scripts/unknown.sh"]) == ["tests/"]


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
