#!/usr/bin/env python3
"""Tests for aet-work/lib/telemetry.py — standard-library only."""

import importlib.util
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

TELEMETRY_PY = Path(__file__).resolve().parents[1] / "aet-work" / "lib" / "telemetry.py"

spec = importlib.util.spec_from_file_location("telemetry", TELEMETRY_PY)
telemetry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(telemetry)


class TestStageRecord(unittest.TestCase):
    def test_stage_record_computes_duration_and_success(self):
        start = datetime.now(timezone.utc)
        end = start + timedelta(seconds=42)
        record = telemetry.stage_record(
            run_id="run-1",
            task_id="FEAT-001",
            plan_file="docs/plans/FEAT-001-plan.md",
            stage="implemented",
            agent_cli="kimi",
            isolation_level="minimal",
            start_time=start.isoformat().replace("+00:00", "Z"),
            end_time=end.isoformat().replace("+00:00", "Z"),
            exit_code=0,
            files_modified=["src/auth.ts"],
            commits_created=1,
            worktree_size_bytes=4096,
            token_count=12345,
            cost_estimate=0.42,
        )

        self.assertEqual(record["type"], "stage")
        self.assertEqual(record["run_id"], "run-1")
        self.assertEqual(record["task_id"], "FEAT-001")
        self.assertEqual(record["stage"], "implemented")
        self.assertEqual(record["result"], "success")
        self.assertEqual(record["duration_seconds"], 42.0)
        self.assertEqual(record["files_modified"], ["src/auth.ts"])
        self.assertEqual(record["commits_created"], 1)
        self.assertEqual(record["worktree_size_bytes"], 4096)
        self.assertEqual(record["token_count"], 12345)
        self.assertEqual(record["cost_estimate"], 0.42)

    def test_stage_record_null_token_and_cost(self):
        start = datetime.now(timezone.utc)
        end = start + timedelta(seconds=10)
        record = telemetry.stage_record(
            run_id="run-1",
            task_id="FEAT-002",
            plan_file="docs/plans/FEAT-002-plan.md",
            stage="qa-complete",
            agent_cli="claude",
            isolation_level="standard",
            start_time=start.isoformat().replace("+00:00", "Z"),
            end_time=end.isoformat().replace("+00:00", "Z"),
            exit_code=0,
            token_count=None,
            cost_estimate=None,
        )

        self.assertIsNone(record["token_count"])
        self.assertIsNone(record["cost_estimate"])

    def test_stage_record_failure_result(self):
        start = datetime.now(timezone.utc)
        end = start + timedelta(seconds=5)
        record = telemetry.stage_record(
            run_id="run-2",
            task_id="FEAT-003",
            plan_file="docs/plans/FEAT-003-plan.md",
            stage="implemented",
            agent_cli="kimi",
            isolation_level="full",
            start_time=start.isoformat().replace("+00:00", "Z"),
            end_time=end.isoformat().replace("+00:00", "Z"),
            exit_code=1,
        )

        self.assertEqual(record["result"], "failure")


class TestRunSummaryRecord(unittest.TestCase):
    def test_run_summary_computes_wall_clock(self):
        start = datetime.now(timezone.utc)
        end = start + timedelta(minutes=3, seconds=20)
        record = telemetry.run_summary_record(
            run_id="run-1",
            start_time=start.isoformat().replace("+00:00", "Z"),
            end_time=end.isoformat().replace("+00:00", "Z"),
            tasks_spawned=4,
            tasks_succeeded=3,
            tasks_failed=1,
            parallel_conflicts_detected=2,
            concurrency_cap=4,
        )

        self.assertEqual(record["type"], "run_summary")
        self.assertEqual(record["wall_clock_seconds"], 200.0)
        self.assertEqual(record["tasks_spawned"], 4)
        self.assertEqual(record["tasks_succeeded"], 3)
        self.assertEqual(record["tasks_failed"], 1)
        self.assertEqual(record["parallel_conflicts_detected"], 2)
        self.assertEqual(record["concurrency_cap"], 4)


class TestAppendAndRead(unittest.TestCase):
    def test_append_record_creates_log_and_writes_jsonl(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "execution.log.jsonl"
            record = {"type": "stage", "task_id": "t1"}
            telemetry.append_record(record, log_path)

            self.assertTrue(log_path.exists())
            lines = log_path.read_text().strip().splitlines()
            self.assertEqual(len(lines), 1)
            self.assertEqual(json.loads(lines[0]), record)

    def test_append_is_append_only(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "execution.log.jsonl"
            telemetry.append_record({"type": "stage", "task_id": "t1"}, log_path)
            telemetry.append_record({"type": "stage", "task_id": "t2"}, log_path)

            lines = log_path.read_text().strip().splitlines()
            self.assertEqual(len(lines), 2)
            self.assertEqual(json.loads(lines[1])["task_id"], "t2")

    def test_read_log_skips_invalid_lines(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "execution.log.jsonl"
            log_path.write_text('{"type": "stage"}\nnot json\n{"type": "run_summary"}\n')
            records = telemetry.read_log(log_path)

            self.assertEqual(len(records), 2)
            self.assertEqual(records[0]["type"], "stage")
            self.assertEqual(records[1]["type"], "run_summary")

    def test_read_log_missing_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "missing.log.jsonl"
            self.assertEqual(telemetry.read_log(log_path), [])


class TestReport(unittest.TestCase):
    def sample_records(self):
        return [
            telemetry.run_summary_record(
                run_id="run-1",
                start_time="2026-06-15T14:51:53Z",
                end_time="2026-06-15T14:55:13Z",
                tasks_spawned=2,
                tasks_succeeded=2,
                tasks_failed=0,
                concurrency_cap=4,
            ),
            telemetry.stage_record(
                run_id="run-1",
                task_id="FEAT-001",
                plan_file="docs/plans/FEAT-001-plan.md",
                stage="implemented",
                agent_cli="kimi",
                isolation_level="minimal",
                start_time="2026-06-15T14:51:53Z",
                end_time="2026-06-15T14:53:53Z",
                exit_code=0,
            ),
            telemetry.stage_record(
                run_id="run-1",
                task_id="FEAT-002",
                plan_file="docs/plans/FEAT-002-plan.md",
                stage="implemented",
                agent_cli="kimi",
                isolation_level="standard",
                start_time="2026-06-15T14:53:53Z",
                end_time="2026-06-15T14:55:13Z",
                exit_code=0,
            ),
            telemetry.run_summary_record(
                run_id="run-2",
                start_time="2026-06-16T10:00:00Z",
                end_time="2026-06-16T10:05:00Z",
                tasks_spawned=1,
                tasks_succeeded=0,
                tasks_failed=1,
                concurrency_cap=2,
            ),
        ]

    def test_report_summary(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "execution.log.jsonl"
            for record in self.sample_records():
                telemetry.append_record(record, log_path)

            output = telemetry.report(log_path)
            self.assertIn("Runs: 2", output)
            self.assertIn("Tasks spawned: 3", output)
            self.assertIn("Succeeded: 2", output)
            self.assertIn("Failed: 1", output)
            self.assertIn("Wall-clock time: 500.0s", output)

    def test_report_average_isolation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "execution.log.jsonl"
            for record in self.sample_records():
                telemetry.append_record(record, log_path)

            output = telemetry.report(log_path)
            self.assertIn("Average isolation level: minimal", output)

    def test_report_since_filters_records(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "execution.log.jsonl"
            for record in self.sample_records():
                telemetry.append_record(record, log_path)

            output = telemetry.report(log_path, since="2026-06-16T00:00:00Z")
            self.assertIn("Runs: 1", output)
            self.assertIn("Tasks spawned: 1", output)
            self.assertIn("Succeeded: 0", output)
            self.assertIn("Failed: 1", output)


if __name__ == "__main__":
    unittest.main(verbosity=2)
