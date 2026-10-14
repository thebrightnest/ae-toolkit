"""Unit tests for batch verdict evidence (Task 6, R-7)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from aet import evidence


class TestBatchVerdictEvidence(unittest.TestCase):
    def test_valid_batch_verdict(self):
        record = {
            "branch": "main",
            "verdict": "pass",
            "summary": "Merge train flush passed",
            "generated_at": "2026-10-13T12:00:00Z",
            "tree_hash": "abc123tree",
            "task_ids": ["task-1", "task-2"],
        }
        evidence.validate_verdict(record, "batch")

    def test_batch_verdict_missing_task_ids(self):
        record = {
            "branch": "main",
            "verdict": "pass",
            "summary": "Merge train flush passed",
            "generated_at": "2026-10-13T12:00:00Z",
            "tree_hash": "abc123tree",
        }
        with self.assertRaises(evidence.VerdictValidationError):
            evidence.validate_verdict(record, "batch")

    def test_evidence_path_for_batch(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = evidence.evidence_path(
                "main",
                "batch",
                project_slug="my-proj",
                reports_root=tmpdir,
            )
            self.assertEqual(
                p,
                Path(tmpdir) / "my-proj" / "_train" / "main" / "batch.json",
            )

    def test_write_verdict_batch_append_only(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            record1 = {
                "branch": "main",
                "verdict": "pass",
                "summary": "First batch flush",
                "generated_at": "2026-10-13T12:00:00Z",
                "tree_hash": "hash1",
                "task_ids": ["task-1"],
            }
            p = evidence.write_verdict(
                "main",
                "batch",
                record1,
                project_slug="my-proj",
                reports_root=tmpdir,
            )
            self.assertTrue(p.exists())
            data1 = json.loads(p.read_text(encoding="utf-8"))
            self.assertEqual(len(data1), 1)
            self.assertEqual(data1[0]["task_ids"], ["task-1"])

            record2 = {
                "branch": "main",
                "verdict": "pass",
                "summary": "Second batch flush",
                "generated_at": "2026-10-13T13:00:00Z",
                "tree_hash": "hash2",
                "task_ids": ["task-2", "task-3"],
            }
            evidence.write_verdict(
                "main",
                "batch",
                record2,
                project_slug="my-proj",
                reports_root=tmpdir,
            )
            data2 = json.loads(p.read_text(encoding="utf-8"))
            self.assertEqual(len(data2), 2)
            self.assertEqual(data2[0]["summary"], "First batch flush")
            self.assertEqual(data2[1]["summary"], "Second batch flush")

    def test_find_batch_verdicts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            record1 = {
                "branch": "feat/my-branch",
                "verdict": "pass",
                "summary": "Branch flush",
                "generated_at": "2026-10-13T12:00:00Z",
                "tree_hash": "hash1",
                "task_ids": ["task-1"],
            }
            evidence.write_verdict(
                "feat/my-branch",
                "batch",
                record1,
                project_slug="my-proj",
                reports_root=tmpdir,
            )

            # Match by task_id in task_ids
            recs = evidence.find_batch_verdicts(
                "task-1",
                project_slug="my-proj",
                reports_root=tmpdir,
            )
            self.assertEqual(len(recs), 1)
            self.assertEqual(recs[0]["tree_hash"], "hash1")

            # Match by branch
            recs = evidence.find_batch_verdicts(
                "other-task",
                branch="feat/my-branch",
                project_slug="my-proj",
                reports_root=tmpdir,
            )
            self.assertEqual(len(recs), 1)

            # No match for unrelated task when branch is None
            recs = evidence.find_batch_verdicts(
                "unrelated-task",
                branch=None,
                project_slug="my-proj",
                reports_root=tmpdir,
            )
            self.assertEqual(len(recs), 0)
