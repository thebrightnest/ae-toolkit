"""Tests for aet-work telemetry record builders and reporting."""

from __future__ import annotations

import json
import os
import tempfile
import unittest

import telemetry


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


if __name__ == "__main__":
    unittest.main()
