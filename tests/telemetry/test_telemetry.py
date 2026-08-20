"""Tests for aet-work telemetry record builders and reporting."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from unittest import mock

from aet import telemetry


class TestStageRecord(unittest.TestCase):
    def test_stage_record_stages_defaults_to_none(self):
        record = telemetry.stage_record(
            run_id="r1",
            task_id="t1",
            plan_file="docs/plans/demo.md",
            stage="implemented",
            agent_cli="kimi",
            isolation_level="full",
            start_time="2026-06-18T00:00:00Z",
            end_time="2026-06-18T00:00:05Z",
            exit_code=0,
        )
        self.assertEqual(record["type"], "stage")
        self.assertEqual(record["stage"], "implemented")
        self.assertIsNone(record["stages"])
        self.assertEqual(record["result"], "success")
        self.assertEqual(record["duration_seconds"], 5.0)

    def test_stage_record_carries_stage_span_for_group_session(self):
        record = telemetry.stage_record(
            run_id="r1",
            task_id="t1",
            plan_file="docs/plans/demo.md",
            stage="qa-complete",
            agent_cli="kimi",
            isolation_level="standard",
            start_time="2026-06-18T00:00:00Z",
            end_time="2026-06-18T00:00:05Z",
            exit_code=0,
            stages=["plan-approved", "implemented"],
        )
        self.assertEqual(record["stage"], "qa-complete")
        self.assertEqual(record["stages"], ["plan-approved", "implemented"])

    def test_stage_record_defaults_actual_stages_to_target_stage(self):
        record = telemetry.stage_record(
            run_id="r1",
            task_id="t1",
            plan_file="docs/plans/demo.md",
            stage="implemented",
            agent_cli="kimi",
            isolation_level="full",
            start_time="2026-06-18T00:00:00Z",
            end_time="2026-06-18T00:00:05Z",
            exit_code=0,
        )
        self.assertEqual(record["actual_stages"], ["implemented"])

    def test_stage_record_uses_provided_actual_stages(self):
        record = telemetry.stage_record(
            run_id="r1",
            task_id="t1",
            plan_file="docs/plans/demo.md",
            stage="implemented",
            agent_cli="kimi",
            isolation_level="standard",
            start_time="2026-06-18T00:00:00Z",
            end_time="2026-06-18T00:00:05Z",
            exit_code=0,
            stages=["plan-approved", "implemented"],
            actual_stages=["plan-approved", "implemented"],
        )
        self.assertEqual(record["actual_stages"], ["plan-approved", "implemented"])

    def test_stage_record_includes_failure_class_plan_snapshot_and_attempt(self):
        record = telemetry.stage_record(
            run_id="r1",
            task_id="t1",
            plan_file="docs/plans/demo.md",
            stage="implemented",
            agent_cli="kimi",
            isolation_level="full",
            start_time="2026-06-18T00:00:00Z",
            end_time="2026-06-18T00:00:05Z",
            exit_code=1,
            failure_class="design",
            plan_snapshot={"size": "M", "pipeline": "standard"},
            attempt=2,
        )
        self.assertEqual(record["failure_class"], "design")
        self.assertEqual(record["plan_snapshot"], {"size": "M", "pipeline": "standard"})
        self.assertEqual(record["attempt"], 2)

    def test_stage_record_attempt_defaults_to_one(self):
        record = telemetry.stage_record(
            run_id="r1",
            task_id="t1",
            plan_file="docs/plans/demo.md",
            stage="implemented",
            agent_cli="kimi",
            isolation_level="full",
            start_time="2026-06-18T00:00:00Z",
            end_time="2026-06-18T00:00:05Z",
            exit_code=0,
        )
        self.assertEqual(record["attempt"], 1)

    def test_stage_record_success_has_null_failure_class_and_plan_snapshot(self):
        record = telemetry.stage_record(
            run_id="r1",
            task_id="t1",
            plan_file="docs/plans/demo.md",
            stage="implemented",
            agent_cli="kimi",
            isolation_level="full",
            start_time="2026-06-18T00:00:00Z",
            end_time="2026-06-18T00:00:05Z",
            exit_code=0,
        )
        self.assertIsNone(record["failure_class"])
        self.assertIsNone(record["plan_snapshot"])

    def test_stage_record_carries_session_identifier(self):
        record = telemetry.stage_record(
            run_id="r1",
            task_id="t1",
            plan_file="docs/plans/demo.md",
            stage="implemented",
            agent_cli="claude",
            isolation_level="full",
            start_time="2026-06-18T00:00:00Z",
            end_time="2026-06-18T00:00:05Z",
            exit_code=0,
            session_identifier="s1",
        )
        self.assertEqual(record["session_identifier"], "s1")

    def test_stage_record_session_identifier_null_when_unresolvable(self):
        record = telemetry.stage_record(
            run_id="r1",
            task_id="t1",
            plan_file="docs/plans/demo.md",
            stage="implemented",
            agent_cli="claude",
            isolation_level="full",
            start_time="2026-06-18T00:00:00Z",
            end_time="2026-06-18T00:00:05Z",
            exit_code=0,
        )
        self.assertIsNone(record["session_identifier"])

    def test_stage_record_carries_targeted_tests(self):
        record = telemetry.stage_record(
            run_id="r1",
            task_id="t1",
            plan_file="docs/plans/demo.md",
            stage="implemented",
            agent_cli="kimi",
            isolation_level="full",
            start_time="2026-06-18T00:00:00Z",
            end_time="2026-06-18T00:00:05Z",
            exit_code=0,
            targeted_tests=["pytest tests/test_foo.py"],
        )
        self.assertEqual(record["targeted_tests"], ["pytest tests/test_foo.py"])

    def test_stage_record_targeted_tests_defaults_to_empty_list(self):
        record = telemetry.stage_record(
            run_id="r1",
            task_id="t1",
            plan_file="docs/plans/demo.md",
            stage="implemented",
            agent_cli="kimi",
            isolation_level="full",
            start_time="2026-06-18T00:00:00Z",
            end_time="2026-06-18T00:00:05Z",
            exit_code=0,
        )
        self.assertEqual(record["targeted_tests"], [])


class TestRunSummaryRecord(unittest.TestCase):
    def _summary(self, **kwargs):
        return telemetry.run_summary_record(
            run_id="r1",
            start_time="2026-07-12T00:00:00Z",
            end_time="2026-07-12T00:01:00Z",
            tasks_spawned=1,
            tasks_succeeded=1,
            tasks_failed=0,
            **kwargs,
        )

    def test_usage_aggregates_default_to_null(self):
        record = self._summary()
        self.assertIsNone(record["total_tokens"])
        self.assertIsNone(record["total_cost_usd"])

    def test_usage_aggregates_carried_when_provided(self):
        record = self._summary(total_tokens=13851, total_cost_usd=0.139146)
        self.assertEqual(record["total_tokens"], 13851)
        self.assertAlmostEqual(record["total_cost_usd"], 0.139146)


class TestEnvironmentIssueRecord(unittest.TestCase):
    def test_environment_issue_record_contains_required_fields(self):
        record = telemetry.environment_issue_record(
            run_id="r1",
            task_id="t1",
            plan_file="docs/plans/demo.md",
            issue_type="missing_dependency",
            dependency="app/node_modules",
            resolved=False,
            message="Dependency directory missing in worktree",
        )
        self.assertEqual(record["type"], "environment_issue")
        self.assertEqual(record["run_id"], "r1")
        self.assertEqual(record["task_id"], "t1")
        self.assertEqual(record["issue_type"], "missing_dependency")
        self.assertEqual(record["dependency"], "app/node_modules")
        self.assertEqual(record["resolved"], False)
        self.assertEqual(record["message"], "Dependency directory missing in worktree")
        self.assertIn("timestamp", record)


class TestTestRunRecord(unittest.TestCase):
    def test_test_run_record_computes_duration_and_result(self):
        record = telemetry.test_run_record(
            run_id="r1",
            task_id="t1",
            plan_file="docs/plans/demo.md",
            stage="qa-complete",
            scope="impact",
            test_command="python3 -m pytest tests/test_demo.py",
            source="wire",
            start_time="2026-06-18T00:00:00Z",
            end_time="2026-06-18T00:00:10Z",
            exit_code=0,
            tests_total=5,
            tests_passed=5,
            tests_failed=0,
        )
        self.assertEqual(record["type"], "test_run")
        self.assertEqual(record["scope"], "impact")
        self.assertEqual(record["duration_seconds"], 10.0)
        self.assertEqual(record["result"], "success")
        self.assertEqual(record["tests_total"], 5)
        self.assertEqual(record["source"], "wire")

    def test_test_run_record_requires_source(self):
        """Provenance is declared by the emitter, never defaulted (ADR-051)."""
        with self.assertRaises(TypeError):
            telemetry.test_run_record(
                run_id="r1",
                task_id="t1",
                plan_file="docs/plans/demo.md",
                stage="implemented",
                scope="impact",
                test_command="pytest tests/test_a.py",
                start_time=None,
                end_time=None,
                exit_code=0,
            )

    def test_test_run_record_rejects_unknown_source(self):
        """``source`` is an enum of the two emitters, not free text."""
        with self.assertRaises(ValueError):
            telemetry.test_run_record(
                run_id="r1",
                task_id="t1",
                plan_file="docs/plans/demo.md",
                stage="implemented",
                scope="impact",
                test_command="pytest tests/test_a.py",
                source="guessed",
                start_time=None,
                end_time=None,
                exit_code=0,
            )

    def test_test_run_record_null_timestamps_yield_null_duration(self):
        """Null contract: unmeasured timestamps produce a null duration."""
        record = telemetry.test_run_record(
            run_id="r1",
            task_id="t1",
            plan_file="docs/plans/demo.md",
            stage="implemented",
            scope="full-suite",
            test_command="pytest tests/",
            source="wire",
            start_time="2026-06-18T00:00:00Z",
            end_time=None,
            exit_code=None,
        )
        self.assertIsNone(record["end_time"])
        self.assertIsNone(record["duration_seconds"])
        self.assertIsNone(record["exit_code"])
        self.assertEqual(record["result"], "unknown")

    def test_test_run_record_none_exit_code_result_unknown(self):
        record = telemetry.test_run_record(
            run_id="r1",
            task_id="t1",
            plan_file="docs/plans/demo.md",
            stage="implemented",
            scope="impact",
            test_command="pytest tests/test_a.py",
            source="wire",
            start_time="2026-06-18T00:00:00Z",
            end_time="2026-06-18T00:00:10Z",
            exit_code=None,
        )
        self.assertEqual(record["duration_seconds"], 10.0)
        self.assertEqual(record["result"], "unknown")

    def test_test_run_record_nonzero_exit_is_failure(self):
        record = telemetry.test_run_record(
            run_id="r1",
            task_id="t1",
            plan_file="docs/plans/demo.md",
            stage="implemented",
            scope="full-suite",
            test_command="pytest tests/",
            source="wire",
            start_time="2026-06-18T00:00:00Z",
            end_time="2026-06-18T00:01:00Z",
            exit_code=1,
        )
        self.assertEqual(record["result"], "failure")


class TestClassifyTestScope(unittest.TestCase):
    """The single scope heuristic shared by every test_run emission site."""

    def test_bare_suite_runners_are_full_suite(self):
        for command in (
            "pytest",
            "pytest tests/",
            "python -m pytest tests/",
            "python3 -m pytest tests/ -q",
            "pytest -k smoke",
            "vitest run",
            "jest",
            "make test",
            "make validate",
            "make -j4 test",
            "npm test",
            "cargo test",
            "go test",
            "go test ./...",
        ):
            with self.subTest(command=command):
                self.assertEqual(telemetry.classify_test_scope(command), "full-suite")

    def test_commands_naming_test_files_or_dirs_are_impact(self):
        for command in (
            "pytest tests/test_panel_serve.py",
            "pytest tests/test_a.py tests/test_b.py",
            "python3 -m pytest tests/unit/",
            "pytest -v --maxfail=1 tests/test_x.py",
            "vitest run src/foo.test.ts",
            "jest tests/foo.test.js",
            "go test ./pkg/foo",
        ):
            with self.subTest(command=command):
                self.assertEqual(telemetry.classify_test_scope(command), "impact")

    def test_unrecognized_commands_are_unknown(self):
        for command in (
            "make build",
            "echo pytest",
            "./run_tests.sh",
            "ruby -Itest test/foo_test.rb",
            "git status",
            "",
        ):
            with self.subTest(command=command):
                self.assertEqual(telemetry.classify_test_scope(command), "unknown")

    def test_make_scope_classification_unchanged_by_registry_move(self):
        """Pins v1 make behaviour behind the shared registry; the make-target
        scope correction belongs to tap-06, not to the registry move."""
        for command in ("make test", "make validate", "make -j4 test"):
            with self.subTest(command=command):
                self.assertEqual(telemetry.classify_test_scope(command), "full-suite")
        for command in ("make build", "make testify"):
            with self.subTest(command=command):
                self.assertEqual(telemetry.classify_test_scope(command), "unknown")


class TestClassifyTestScopeFromMarker(unittest.TestCase):
    """tap-06: a `make` run's real scope comes from the marker in its output.

    `make validate` runs pytest in a sub-make the session log never sees, so
    the command string alone always read `full-suite`. The marker carries the
    targets `change_scope` resolved; absent or malformed, the command-string
    heuristic answers as before.
    """

    def _marker(self, *targets):
        return f"{telemetry.TEST_SCOPE_MARKER_PREFIX} {' '.join(targets)}"

    def test_classify_scope_reads_marker_and_returns_impact_for_narrowed_targets(self):
        output = f"→ targeted tests: tests/queue\n{self._marker('tests/queue')}\n"
        self.assertEqual(telemetry.classify_test_scope("make validate", output), "impact")

    def test_classify_scope_returns_full_suite_for_marker_naming_suite_root(self):
        output = f"→ full suite (changed paths: 12)\n{self._marker('tests/')}\n"
        self.assertEqual(
            telemetry.classify_test_scope("make validate", output), "full-suite"
        )

    def test_classify_scope_falls_back_to_heuristic_when_marker_absent(self):
        self.assertEqual(
            telemetry.classify_test_scope("make validate", "ruff ok\n✓ Tests passed\n"),
            "full-suite",
        )
        self.assertEqual(telemetry.classify_test_scope("make validate", None), "full-suite")
        self.assertEqual(telemetry.classify_test_scope("make build", "irrelevant"), "unknown")

    def test_classify_scope_falls_back_when_marker_malformed(self):
        for payload in (
            "",
            "   ",
            "src/aet/queue.py",
            "tests/queue; rm -rf /",
            "../../etc/passwd",
            "tests/queue $(whoami)",
            "tests/queue tests/../secrets",
        ):
            with self.subTest(payload=payload):
                output = f"{telemetry.TEST_SCOPE_MARKER_PREFIX} {payload}\n"
                self.assertEqual(
                    telemetry.classify_test_scope("make validate", output), "full-suite"
                )

    def test_classify_scope_unchanged_for_non_make_commands(self):
        """The pure-heuristic path is untouched: output never overrides it."""
        cases = [
            ("pytest tests/", "full-suite"),
            ("pytest tests/test_queue.py", "impact"),
            ("./run_tests.sh", "unknown"),
        ]
        marker = self._marker("tests/queue")
        for command, expected in cases:
            with self.subTest(command=command):
                self.assertEqual(telemetry.classify_test_scope(command, marker), expected)

    def test_omitting_output_is_identical_to_the_pre_tap06_heuristic(self):
        """No archived record carries output, so this path must not move them.

        Every historical `test_run` reaches the classifier with `output=None`.
        If that answer ever diverges from the one-argument call, tap-06 would
        silently reclassify the archive — the shift R-13 exists to prevent.
        """
        for command in (
            "make validate",
            "make test",
            "make -j4 test",
            "make build",
            "pytest",
            "pytest tests/",
            "pytest tests/test_queue.py",
            "python3 -m pytest tests/ -q",
            "vitest run src/foo.test.ts",
            "go test ./...",
            "./run_tests.sh",
            "",
        ):
            with self.subTest(command=command):
                self.assertEqual(
                    telemetry.classify_test_scope(command, None),
                    telemetry.classify_test_scope(command),
                )

    def test_repeated_agreeing_markers_classify_normally(self):
        """Two `make validate` runs in one shell call that resolved the same."""
        output = f"{self._marker('tests/queue')}\n...\n{self._marker('tests/queue')}\n"
        self.assertEqual(telemetry.classify_test_scope("make validate", output), "impact")

    def test_disagreeing_markers_fall_back_to_full_suite(self):
        """Regression: pytest echoing a marker must not shrink the recorded scope.

        A full-suite `make validate` whose own change_scope test fails makes
        pytest print that test's captured stdout — an unindented marker line
        naming a narrowed target. Trusting the last marker recorded the run as
        `impact`, understating suite cost precisely when tests were failing.
        Disagreement is now unresolvable and falls back, per ADR-049's bias.
        """
        output = (
            "→ full suite (changed paths: 15)\n"
            f"{self._marker('tests/')}\n"
            "=================================== FAILURES ===================================\n"
            "--------------------------- Captured stdout call -------------------------------\n"
            "→ targeted tests: tests/queue (changed paths: 1)\n"
            f"{self._marker('tests/queue')}\n"
        )
        self.assertEqual(
            telemetry.classify_test_scope("make validate", output), "full-suite"
        )

    def test_one_malformed_marker_discards_the_whole_output(self):
        """A marker that fails the grammar is not silently skipped over."""
        output = f"{self._marker('tests/queue')}\n{telemetry.TEST_SCOPE_MARKER_PREFIX} /etc/passwd\n"
        self.assertEqual(
            telemetry.classify_test_scope("make validate", output), "full-suite"
        )


class TestLearningCandidateRecord(unittest.TestCase):
    def test_learning_candidate_record_contains_required_fields(self):
        record = telemetry.learning_candidate_record(
            run_id="r1",
            task_id="t1",
            plan_file="docs/plans/demo.md",
            stage="implemented",
            pattern_type="repeated_format_fix",
            description="Formatter was retried after lint failure",
            evidence={"loop_type": "format_fix", "iterations": 2},
            confidence=0.8,
        )
        self.assertEqual(record["type"], "learning_candidate")
        self.assertEqual(record["pattern_type"], "repeated_format_fix")
        self.assertEqual(record["confidence"], 0.8)
        self.assertEqual(record["evidence"]["iterations"], 2)


class TestReport(unittest.TestCase):
    def test_report_includes_environment_issue_count(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            log_path = f.name
            f.write(
                json.dumps(
                    telemetry.run_summary_record(
                        run_id="r1",
                        start_time="2026-06-18T00:00:00Z",
                        end_time="2026-06-18T00:00:30Z",
                        tasks_spawned=1,
                        tasks_succeeded=1,
                        tasks_failed=0,
                    )
                )
                + "\n"
            )
            f.write(
                json.dumps(
                    telemetry.environment_issue_record(
                        run_id="r1",
                        task_id="t1",
                        plan_file="docs/plans/demo.md",
                        issue_type="missing_dependency",
                        dependency="app/node_modules",
                        timestamp="2026-06-18T00:00:01Z",
                    )
                )
                + "\n"
            )

        try:
            output = telemetry.report(log_path)
            self.assertIn("Environment issues: 1", output)
        finally:
            os.unlink(log_path)

    def test_report_has_no_loop_line(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            log_path = f.name
            f.write(
                json.dumps(
                    telemetry.stage_record(
                        run_id="r1",
                        task_id="t1",
                        plan_file="docs/plans/demo.md",
                        stage="implemented",
                        agent_cli="kimi",
                        isolation_level="full",
                        start_time="2026-06-18T00:00:00Z",
                        end_time="2026-06-18T00:00:10Z",
                        exit_code=0,
                    )
                )
                + "\n"
            )
            f.write(
                json.dumps(
                    telemetry.environment_issue_record(
                        run_id="r1",
                        task_id="t1",
                        plan_file="docs/plans/demo.md",
                        issue_type="missing_dependency",
                        dependency="app/node_modules",
                        timestamp="2026-06-18T00:00:01Z",
                    )
                )
                + "\n"
            )

        try:
            output = telemetry.report(log_path)
            self.assertNotIn("Loops", output)
        finally:
            os.unlink(log_path)

    def test_report_since_filter_applies_to_environment_issue_timestamp(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            log_path = f.name
            f.write(
                json.dumps(
                    telemetry.environment_issue_record(
                        run_id="r1",
                        task_id="t1",
                        plan_file="docs/plans/demo.md",
                        issue_type="missing_dependency",
                        dependency="app/node_modules",
                        timestamp="2026-06-17T00:00:00Z",
                    )
                )
                + "\n"
            )
            f.write(
                json.dumps(
                    telemetry.environment_issue_record(
                        run_id="r2",
                        task_id="t2",
                        plan_file="docs/plans/demo.md",
                        issue_type="missing_dependency",
                        dependency="app/vendor",
                        timestamp="2026-06-19T00:00:00Z",
                    )
                )
                + "\n"
            )

        try:
            output = telemetry.report(log_path, since="2026-06-18T00:00:00Z")
            self.assertIn("Environment issues: 1", output)
        finally:
            os.unlink(log_path)


class TestDeriveProjectSlug(unittest.TestCase):
    """Worktree-based slug: ``<main-worktree-dir>/<worktree-label>``."""

    def setUp(self):
        self._env = mock.patch.dict(
            os.environ,
            {"AET_PROJECT_ID": "", "AET_REPO_SLUG": "", "AET_REPO_ROOT": ""},
        )
        self._env.start()
        self.addCleanup(self._env.stop)

    def _git(self, *args, cwd):
        result = subprocess.run(
            [
                "git",
                "-c",
                "user.email=test@example.com",
                "-c",
                "user.name=test",
                *args,
            ],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def _init_repo(self, path):
        os.makedirs(path)
        self._git("init", cwd=path)
        self._git("commit", "--allow-empty", "-m", "init", cwd=path)

    def test_primary_worktree_slug(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = os.path.join(tmp, "foo")
            self._init_repo(repo)
            self.assertEqual(telemetry.derive_project_slug(repo), "foo/main")

    def test_linked_worktree_slug(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = os.path.join(tmp, "foo")
            self._init_repo(repo)
            worktree = os.path.join(repo, ".worktrees", "bar")
            self._git("worktree", "add", worktree, cwd=repo)
            self.assertEqual(telemetry.derive_project_slug(worktree), "foo/bar")

    def test_env_override_wins(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = os.path.join(tmp, "foo")
            self._init_repo(repo)
            with mock.patch.dict(os.environ, {"AET_PROJECT_ID": "x/y"}):
                self.assertEqual(telemetry.derive_project_slug(repo), "x/y")

    def test_non_git_dir_falls_back_to_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            plain = os.path.join(tmp, "plain-dir")
            os.makedirs(plain)
            self.assertEqual(telemetry.derive_project_slug(plain), "plain-dir")


if __name__ == "__main__":
    unittest.main()
