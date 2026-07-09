"""Tests for structured gate evidence contracts."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

import evidence


class TestReportsDir(unittest.TestCase):
    def test_reports_dir_env_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            env = os.environ.copy()
            env["AET_REPORTS_DIR"] = str(tmp_path)
            # Module-level default is computed at import time, so call the
            # function with the environment variable set via mocking.
            original = os.environ.get("AET_REPORTS_DIR")
            os.environ["AET_REPORTS_DIR"] = str(tmp_path)
            try:
                self.assertEqual(evidence.reports_dir(), tmp_path)
            finally:
                if original is None:
                    del os.environ["AET_REPORTS_DIR"]
                else:
                    os.environ["AET_REPORTS_DIR"] = original


class TestEvidencePath(unittest.TestCase):
    def test_evidence_path_is_project_namespaced(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            path_a = evidence.evidence_path(
                task_id="frh-10",
                kind="qa",
                project_slug="owner/repo-a",
                reports_root=base,
            )
            path_b = evidence.evidence_path(
                task_id="frh-10",
                kind="qa",
                project_slug="owner/repo-b",
                reports_root=base,
            )
            self.assertNotEqual(path_a, path_b)
            self.assertIn("repo-a", str(path_a))
            self.assertIn("repo-b", str(path_b))


class TestValidateVerdict(unittest.TestCase):
    def test_valid_qa_verdict_passes_validation(self):
        record = {
            "task_id": "frh-10",
            "stage": "qa-complete",
            "skill": "aet-qa",
            "verdict": "pass",
            "summary": "All checks passed",
            "generated_at": "2026-07-09T20:00:00Z",
            "test_command": "pytest tests/test_gate_evidence.py",
            "tests_total": 6,
            "tests_passed": 6,
            "tests_failed": 0,
        }
        evidence.validate_verdict(record, "qa")  # should not raise

    def test_missing_required_key_fails_validation(self):
        record = {
            "task_id": "frh-10",
            "stage": "qa-complete",
            "skill": "aet-qa",
            "verdict": "pass",
            "summary": "Missing generated_at",
        }
        with self.assertRaises(evidence.VerdictValidationError):
            evidence.validate_verdict(record, "qa")

    def test_wrong_type_fails_validation(self):
        record = {
            "task_id": "frh-10",
            "stage": "qa-complete",
            "skill": "aet-qa",
            "verdict": "pass",
            "summary": "Bad counts",
            "generated_at": "2026-07-09T20:00:00Z",
            "test_command": "pytest",
            "tests_total": "six",
            "tests_passed": 6,
            "tests_failed": 0,
        }
        with self.assertRaises(evidence.VerdictValidationError):
            evidence.validate_verdict(record, "qa")

    def test_invalid_verdict_value_fails_validation(self):
        record = {
            "task_id": "frh-10",
            "stage": "qa-complete",
            "skill": "aet-qa",
            "verdict": "maybe",
            "summary": "Invalid verdict value",
            "generated_at": "2026-07-09T20:00:00Z",
            "test_command": "pytest",
            "tests_total": 1,
            "tests_passed": 1,
            "tests_failed": 0,
        }
        with self.assertRaises(evidence.VerdictValueError):
            evidence.validate_verdict(record, "qa")

    def test_unknown_kind_fails_validation(self):
        with self.assertRaises(evidence.VerdictValidationError):
            evidence.validate_verdict({"task_id": "frh-10"}, "unknown-kind")


class TestWriteThenReadVerdict(unittest.TestCase):
    def test_write_then_read_verdict_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            record = {
                "task_id": "frh-10",
                "stage": "qa-complete",
                "skill": "aet-qa",
                "verdict": "pass",
                "summary": "Roundtrip",
                "generated_at": "2026-07-09T20:00:00Z",
                "test_command": "pytest",
                "tests_total": 1,
                "tests_passed": 1,
                "tests_failed": 0,
            }
            path = evidence.write_verdict(
                task_id="frh-10",
                kind="qa",
                record=record,
                project_slug="owner/repo",
                reports_root=base,
            )
            self.assertTrue(path.exists())
            loaded = evidence.read_verdict(path)
            self.assertEqual(loaded["task_id"], "frh-10")
            self.assertEqual(loaded["verdict"], "pass")


if __name__ == "__main__":
    unittest.main()
