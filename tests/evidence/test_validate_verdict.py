"""Unit tests for verdict value checking (ADR-072 / eop-04).

Verifies that gating fields (summary) are checked for substance:
empty strings, whitespace-only, and placeholder tokens are refused with
VerdictValueError, while real attestations pass.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from aet import evidence
from aet.cli import gate


def _valid_qa_record(**overrides) -> dict:
    record = {
        "task_id": "eop-04",
        "stage": "qa-complete",
        "skill": "aet-qa",
        "verdict": "pass",
        "summary": "All 12 unit tests passed cleanly",
        "generated_at": "2026-08-29T20:00:00Z",
        "tree_hash": "tree123",
        "test_command": "pytest tests/evidence/",
        "tests_total": 12,
        "tests_passed": 12,
        "tests_failed": 0,
    }
    record.update(overrides)
    return record


def _valid_verify_record(**overrides) -> dict:
    record = {
        "task_id": "eop-04",
        "stage": "verified",
        "skill": "aet-verify",
        "verdict": "pass",
        "summary": "Exercised CLI end-to-end and captured exit codes",
        "generated_at": "2026-08-29T20:00:00Z",
        "tree_hash": "tree123",
    }
    record.update(overrides)
    return record


class TestValidateVerdictSubstance(unittest.TestCase):
    """Substance constraints on gating text fields in validate_verdict."""

    def test_real_summary_passes_validation(self):
        record = _valid_qa_record(summary="All tests passed with 100% coverage")
        evidence.validate_verdict(record, "qa")  # should not raise

    def test_real_verify_summary_passes_validation(self):
        record = _valid_verify_record(summary="Live smoke checks passed on staging")
        evidence.validate_verdict(record, "verify")  # should not raise

    def test_empty_summary_raises_verdict_value_error(self):
        record = _valid_qa_record(summary="")
        with self.assertRaises(evidence.VerdictValueError) as ctx:
            evidence.validate_verdict(record, "qa")
        self.assertIn("summary", str(ctx.exception).lower())

    def test_whitespace_only_summary_raises_verdict_value_error(self):
        record = _valid_qa_record(summary="   \t\n  ")
        with self.assertRaises(evidence.VerdictValueError) as ctx:
            evidence.validate_verdict(record, "qa")
        self.assertIn("summary", str(ctx.exception).lower())

    def test_placeholder_summaries_are_refused(self):
        placeholders = [
            "pending",
            "PENDING",
            "Pending",
            "todo",
            "TODO",
            "tbd",
            "TBD",
            "placeholder",
            "PLACEHOLDER",
            "n/a",
            "N/A",
            "na",
            "none",
            "NONE",
            "null",
            "NULL",
            "wip",
            "WIP",
            "...",
            "<one-line>",
            "<one line>",
            "<summary>",
            "  pending  ",
            " <one-line> ",
        ]
        for ph in placeholders:
            with self.subTest(placeholder=ph):
                record = _valid_qa_record(summary=ph)
                with self.assertRaises(evidence.VerdictValueError) as ctx:
                    evidence.validate_verdict(record, "qa")
                self.assertIn("summary", str(ctx.exception).lower())

    def test_payload_with_only_verdict_and_tree_hash_fails_schema_check(self):
        # A payload missing required fields continues to raise VerdictValidationError
        record = {
            "verdict": "pass",
            "tree_hash": "tree123",
        }
        with self.assertRaises(evidence.VerdictValidationError):
            evidence.validate_verdict(record, "qa")

    def test_invalid_verdict_enum_still_raises_verdict_value_error(self):
        record = _valid_qa_record(verdict="unknown")
        with self.assertRaises(evidence.VerdictValueError) as ctx:
            evidence.validate_verdict(record, "qa")
        self.assertIn("verdict", str(ctx.exception).lower())


class TestGateSubmitSubstanceRefusal(unittest.TestCase):
    """aet gate submit exits non-zero when summary is a placeholder or empty."""

    def _run(self, argv):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            rc = gate.main(argv)
        return rc, stdout.getvalue(), stderr.getvalue()

    def test_gate_submit_rejects_placeholder_summary(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            dest = tmp / "verdicts" / "qa.json"
            report = tmp / "report.json"
            report.write_text(
                json.dumps(
                    {
                        "test_command": "pytest",
                        "tests_total": 5,
                        "tests_passed": 5,
                        "tests_failed": 0,
                    }
                ),
                encoding="utf-8",
            )
            env = {
                "AET_EVIDENCE_PATH": str(dest),
                "AET_TASK_ID": "eop-04",
            }
            with patch.dict(os.environ, env, clear=True):
                rc, out, err = self._run(
                    [
                        "submit",
                        "--stage",
                        "qa",
                        "--verdict",
                        "pass",
                        "--summary",
                        "pending",
                        "--from-pytest",
                        str(report),
                    ]
                )
            self.assertNotEqual(rc, 0, f"Expected gate submit to fail, got {rc}. Output: {out} {err}")
            self.assertFalse(dest.exists(), "Verdict file should not have been written")

    def test_gate_submit_accepts_real_summary(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            dest = tmp / "verdicts" / "qa.json"
            report = tmp / "report.json"
            report.write_text(
                json.dumps(
                    {
                        "test_command": "pytest",
                        "tests_total": 5,
                        "tests_passed": 5,
                        "tests_failed": 0,
                    }
                ),
                encoding="utf-8",
            )
            env = {
                "AET_EVIDENCE_PATH": str(dest),
                "AET_TASK_ID": "eop-04",
            }
            with patch.dict(os.environ, env, clear=True):
                rc, out, err = self._run(
                    [
                        "submit",
                        "--stage",
                        "qa",
                        "--verdict",
                        "pass",
                        "--summary",
                        "5 tests passed cleanly",
                        "--from-pytest",
                        str(report),
                    ]
                )
            self.assertEqual(rc, 0, f"Gate submit failed: {out} {err}")
            self.assertTrue(dest.exists(), "Verdict file should have been written")
