"""Unit tests for the run-scoped handoff note module."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from aet import handoff


class TestHandoffPath(unittest.TestCase):
    def test_path_lies_under_run_dir(self):
        path = handoff.handoff_path("/repo", "run-20260810-093000-abcd1234")
        self.assertEqual(
            path,
            Path("/repo/.agents/runs/run-20260810-093000-abcd1234/handoff.json"),
        )


class TestReadNote(unittest.TestCase):
    def test_missing_file_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(handoff.read_note(tmp, "run-missing"))

    def test_corrupt_file_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = handoff.handoff_path(tmp, "run-bad")
            path.parent.mkdir(parents=True)
            path.write_text("not json", encoding="utf-8")
            self.assertIsNone(handoff.read_note(tmp, "run-bad"))

    def test_wrong_schema_version_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = handoff.handoff_path(tmp, "run-old")
            path.parent.mkdir(parents=True)
            path.write_text(
                json.dumps(
                    {"schema_version": 0, "run_id": "run-old", "entries": [{}]}
                ),
                encoding="utf-8",
            )
            self.assertIsNone(handoff.read_note(tmp, "run-old"))

    def test_mismatched_run_id_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = handoff.handoff_path(tmp, "run-a")
            path.parent.mkdir(parents=True)
            path.write_text(
                json.dumps(
                    {"schema_version": 1, "run_id": "run-b", "entries": [{}]}
                ),
                encoding="utf-8",
            )
            self.assertIsNone(handoff.read_note(tmp, "run-a"))

    def test_empty_entries_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = handoff.handoff_path(tmp, "run-empty")
            path.parent.mkdir(parents=True)
            path.write_text(
                json.dumps(
                    {"schema_version": 1, "run_id": "run-empty", "entries": []}
                ),
                encoding="utf-8",
            )
            self.assertIsNone(handoff.read_note(tmp, "run-empty"))


class TestAppendEntry(unittest.TestCase):
    def test_creates_file_lazily_on_first_append(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = handoff.handoff_path(tmp, "run-new")
            self.assertFalse(path.exists())
            handoff.append_entry(
                tmp,
                "run-new",
                stage="plan-approved",
                decisions=["use JSON"],
            )
            self.assertTrue(path.exists())
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["schema_version"], 1)
            self.assertEqual(data["run_id"], "run-new")
            self.assertEqual(len(data["entries"]), 1)

    def test_appends_subsequent_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            handoff.append_entry(
                tmp, "run-two", stage="plan-approved", decisions=["a"]
            )
            handoff.append_entry(
                tmp, "run-two", stage="implemented", validation_commands=["make test"]
            )
            data = json.loads(
                handoff.handoff_path(tmp, "run-two").read_text(encoding="utf-8")
            )
            self.assertEqual(len(data["entries"]), 2)
            self.assertEqual(data["entries"][0]["stage"], "plan-approved")
            self.assertEqual(data["entries"][1]["stage"], "implemented")

    def test_empty_fields_raise(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(handoff.EmptyEntryError):
                handoff.append_entry(tmp, "run-empty", stage="plan-approved")

    def test_recorded_at_minted_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            note = handoff.append_entry(
                tmp,
                "run-time",
                stage="plan-approved",
                decisions=["x"],
            )
            self.assertIn("T", note["entries"][0]["recorded_at"])


class TestRenderPromptBlock(unittest.TestCase):
    def test_renders_all_fields(self):
        note = {
            "schema_version": 1,
            "run_id": "run-x",
            "entries": [
                {
                    "stage": "plan-approved",
                    "decisions": ["d1", "d2"],
                    "pre_existing_failures": ["f1"],
                    "validation_commands": ["make test"],
                    "evidence_path": "/path/to/evidence.json",
                    "recorded_at": "2026-08-10T09:30:00+00:00",
                }
            ],
        }
        block = handoff.render_prompt_block(note)
        self.assertIn("Run handoff note", block)
        self.assertIn("[stage: plan-approved]", block)
        self.assertIn("decisions: d1, d2", block)
        self.assertIn("pre-existing failures: f1", block)
        self.assertIn("validation commands: make test", block)
        self.assertIn("evidence path: /path/to/evidence.json", block)

    def test_renders_none_for_missing_fields(self):
        note = {
            "schema_version": 1,
            "run_id": "run-x",
            "entries": [
                {
                    "stage": "implemented",
                    "decisions": [],
                    "pre_existing_failures": [],
                    "validation_commands": [],
                    "evidence_path": None,
                    "recorded_at": "2026-08-10T09:30:00+00:00",
                }
            ],
        }
        block = handoff.render_prompt_block(note)
        self.assertIn("decisions: (none)", block)
        self.assertIn("pre-existing failures: (none)", block)
        self.assertIn("validation commands: (none)", block)
        self.assertIn("evidence path: (none)", block)

    def test_truncation_marker_on_long_note(self):
        note = {
            "schema_version": 1,
            "run_id": "run-x",
            "entries": [
                {
                    "stage": "plan-approved",
                    "decisions": ["x" * 5000],
                    "pre_existing_failures": [],
                    "validation_commands": [],
                    "evidence_path": None,
                    "recorded_at": "2026-08-10T09:30:00+00:00",
                }
            ],
        }
        block = handoff.render_prompt_block(note)
        self.assertLessEqual(len(block), handoff.PROMPT_BLOCK_CAP)
        self.assertIn("[handoff note truncated]", block)


if __name__ == "__main__":
    unittest.main()
