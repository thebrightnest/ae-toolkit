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
            path.write_text(
                json.dumps(
                    {"schema_version": 3, "run_id": "run-old", "entries": [{}]}
                ),
                encoding="utf-8",
            )
            self.assertIsNone(handoff.read_note(tmp, "run-old"))

    def test_read_note_accepts_version_1_and_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            for version in (1, 2):
                path = handoff.handoff_path(tmp, f"run-v{version}")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(
                    json.dumps(
                        {
                            "schema_version": version,
                            "run_id": f"run-v{version}",
                            "entries": [{"stage": "plan-approved"}],
                        }
                    ),
                    encoding="utf-8",
                )
                note = handoff.read_note(tmp, f"run-v{version}")
                self.assertIsNotNone(note)
                self.assertEqual(note["schema_version"], version)

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
                task_id="task-x",
                decisions=["use JSON"],
            )
            self.assertTrue(path.exists())
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["schema_version"], 2)
            self.assertEqual(data["run_id"], "run-new")
            self.assertEqual(len(data["entries"]), 1)
            self.assertEqual(data["entries"][0]["task_id"], "task-x")

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

    def test_append_entry_upgrades_v1_to_v2(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = handoff.handoff_path(tmp, "run-upgrade")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "run_id": "run-upgrade",
                        "entries": [
                            {"stage": "plan-approved", "decisions": ["d1"]}
                        ],
                    }
                ),
                encoding="utf-8",
            )
            handoff.append_entry(
                tmp,
                "run-upgrade",
                stage="implemented",
                task_id="task-x",
                decisions=["d2"],
            )
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["schema_version"], 2)
            self.assertEqual(len(data["entries"]), 2)
            self.assertEqual(data["entries"][1]["task_id"], "task-x")

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

    def test_repeated_entries_collapsed_and_task_filtered(self):
        entries = []
        # 57 identical entries of task A
        for i in range(57):
            entries.append(
                {
                    "stage": "implemented",
                    "task_id": "task-A",
                    "decisions": ["retry build"],
                    "pre_existing_failures": [],
                    "validation_commands": ["pytest"],
                    "evidence_path": None,
                    "recorded_at": f"2026-10-28T10:{i % 60:02d}:00+00:00",
                }
            )
        # entries of task B
        entries.append(
            {
                "stage": "implemented",
                "task_id": "task-B",
                "decisions": ["task-B decision"],
                "pre_existing_failures": [],
                "validation_commands": ["pytest task-B"],
                "evidence_path": None,
                "recorded_at": "2026-10-28T11:00:00+00:00",
            }
        )
        # one newer distinct entry of task A
        entries.append(
            {
                "stage": "qa-complete",
                "task_id": "task-A",
                "decisions": ["task-A new decision"],
                "pre_existing_failures": [],
                "validation_commands": ["pytest full"],
                "evidence_path": None,
                "recorded_at": "2026-10-28T11:30:00+00:00",
            }
        )

        note = {
            "schema_version": 2,
            "run_id": "run-repeat",
            "entries": entries,
        }
        block = handoff.render_prompt_block(note, task_id="task-A")
        self.assertIn("(repeated 57 times)", block)
        self.assertIn("task-A new decision", block)
        self.assertNotIn("task-B decision", block)
        self.assertNotIn("task-B", block)

    def test_drops_oldest_entries_when_exceeding_cap(self):
        entries = [
            {
                "stage": "plan-approved",
                "task_id": "task-A",
                "decisions": ["old entry " + "a" * 2500],
                "pre_existing_failures": [],
                "validation_commands": [],
                "evidence_path": None,
                "recorded_at": "2026-10-28T10:00:00+00:00",
            },
            {
                "stage": "implemented",
                "task_id": "task-A",
                "decisions": ["newest entry " + "z" * 2500],
                "pre_existing_failures": [],
                "validation_commands": [],
                "evidence_path": None,
                "recorded_at": "2026-10-28T11:00:00+00:00",
            },
        ]
        note = {
            "schema_version": 2,
            "run_id": "run-cap",
            "entries": entries,
        }
        block = handoff.render_prompt_block(note, task_id="task-A")
        self.assertLessEqual(len(block), handoff.PROMPT_BLOCK_CAP)
        self.assertIn("newest entry", block)
        self.assertNotIn("old entry", block)

    def test_v1_note_without_task_id_renders_for_any_task(self):
        note = {
            "schema_version": 1,
            "run_id": "run-v1",
            "entries": [
                {
                    "stage": "plan-approved",
                    "decisions": ["v1 global decision"],
                    "pre_existing_failures": [],
                    "validation_commands": [],
                    "evidence_path": None,
                    "recorded_at": "2026-10-28T10:00:00+00:00",
                }
            ],
        }
        block = handoff.render_prompt_block(note, task_id="arbitrary-task")
        self.assertIn("v1 global decision", block)


if __name__ == "__main__":
    unittest.main()
