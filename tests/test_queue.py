"""Tests for queue module."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "aet-work" / "lib"))

import json
import tempfile
import unittest

from queue import (
    append_history_record,
    get_next_unblocked,
    has_pending_tasks,
    mark_awaiting_merge,
    mark_completed,
    mark_status,
    read_queue,
    record_task_meta,
    seal_terminal,
    write_queue,
)


class TestQueue(unittest.TestCase):
    def test_read_write_queue(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path = f.name

        queue = [{"id": "t1", "status": "unblocked"}]
        write_queue(path, queue)
        read_back = read_queue(path)
        self.assertEqual(read_back, queue)

    def test_read_queue_nested(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path = f.name
            json.dump({"tasks": [{"id": "t1", "status": "blocked"}]}, f)

        read_back = read_queue(path)
        self.assertEqual(read_back[0]["id"], "t1")

    def test_read_queue_missing_tasks_fallback(self):
        """Dict without 'tasks' key should return empty list, not the dict."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path = f.name
            json.dump({"source_prd": "foo"}, f)

        read_back = read_queue(path)
        self.assertEqual(read_back, [])

    def test_write_queue_preserves_wrapper(self):
        """Wrapper metadata (source_prd, queue_updated_at) must survive a read-write cycle."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path = f.name
            original = {
                "source_prd": "docs/prds/test.md",
                "queue_updated_at": "2026-01-01T00:00:00Z",
                "tasks": [{"id": "t1", "status": "unblocked"}],
            }
            json.dump(original, f)

        queue = read_queue(path)
        mark_status(queue, "t1", "in-progress")
        write_queue(path, queue)

        with open(path, "r") as f:
            data = json.load(f)

        self.assertIsInstance(data, dict)
        self.assertEqual(data.get("source_prd"), "docs/prds/test.md")
        self.assertEqual(data.get("queue_updated_at"), "2026-01-01T00:00:00Z")
        self.assertEqual(data["tasks"][0]["status"], "in-progress")

    def test_get_next_unblocked(self):
        queue = [
            {"id": "t1", "state": "blocked"},
            {"id": "t2", "state": "ready"},
        ]
        task = get_next_unblocked(queue)
        self.assertEqual(task["id"], "t2")

    def test_get_next_unblocked_none(self):
        queue = [{"id": "t1", "state": "blocked"}]
        self.assertIsNone(get_next_unblocked(queue))

    def test_has_pending_tasks(self):
        queue = [{"id": "t1", "state": "in_progress"}]
        self.assertTrue(has_pending_tasks(queue))

    def test_has_pending_tasks_all_done(self):
        queue = [
            {"id": "t1", "state": "merged"},
            {"id": "t2", "state": "abandoned"},
        ]
        self.assertFalse(has_pending_tasks(queue))

    def test_mark_status(self):
        queue = [{"id": "t1", "status": "unblocked"}]
        mark_status(queue, "t1", "failed", "pipeline")
        self.assertEqual(queue[0]["status"], "failed")
        self.assertEqual(queue[0]["failed_stage"], "pipeline")

    def test_mark_completed(self):
        queue = [{"id": "t1", "status": "in-progress"}]
        mark_completed(queue, "t1")
        self.assertEqual(queue[0]["status"], "done")
        self.assertIn("completed_at", queue[0])

    def test_mark_awaiting_merge(self):
        queue = [{"id": "t1", "status": "in-progress"}]
        mark_awaiting_merge(queue, "t1")
        self.assertEqual(queue[0]["status"], "awaiting_merge")
        self.assertIn("completed_at", queue[0])

    def test_has_pending_tasks_awaiting_merge(self):
        queue = [{"id": "t1", "state": "awaiting_merge"}]
        self.assertTrue(has_pending_tasks(queue))

    def test_record_task_meta(self):
        queue = [{"id": "t1"}]
        record_task_meta(queue, "t1", "/path/to/wt", "feat-001")
        self.assertEqual(queue[0]["worktree"], "/path/to/wt")
        self.assertEqual(queue[0]["branch"], "feat-001")

    def test_terminal_seal_removes_from_live_and_appends_jsonl(self):
        """Sealing a task moves it from the live queue to the settled history log."""
        with tempfile.TemporaryDirectory() as tmp:
            queue_file = Path(tmp) / "work-queue.json"
            history_file = Path(tmp) / "work-history.jsonl"
            task = {"id": "t1", "state": "merged", "title": "Task one"}
            write_queue(queue_file, [task])

            seal_terminal(queue_file, history_file, "t1")

            live = read_queue(queue_file)
            self.assertEqual(live, [])
            self.assertTrue(history_file.exists())
            lines = history_file.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(lines), 1)
            settled = json.loads(lines[0])
            self.assertEqual(settled["id"], "t1")
            self.assertEqual(settled["state"], "merged")

    def test_no_id_in_both_live_and_settled(self):
        """The same task id must never exist in both live and settled stores."""
        with tempfile.TemporaryDirectory() as tmp:
            queue_file = Path(tmp) / "work-queue.json"
            history_file = Path(tmp) / "work-history.jsonl"
            write_queue(queue_file, [
                {"id": "t1", "state": "merged"},
                {"id": "t2", "state": "ready"},
            ])

            seal_terminal(queue_file, history_file, "t1")

            live_ids = {t["id"] for t in read_queue(queue_file)}
            settled_ids = {
                json.loads(line)["id"]
                for line in history_file.read_text(encoding="utf-8").strip().splitlines()
            }
            self.assertNotIn("t1", live_ids)
            self.assertIn("t1", settled_ids)
            self.assertFalse(live_ids & settled_ids)

    def test_dependents_promoted_before_seal(self):
        """seal_terminal must not re-walk or mutate dependent blockers."""
        with tempfile.TemporaryDirectory() as tmp:
            queue_file = Path(tmp) / "work-queue.json"
            history_file = Path(tmp) / "work-history.jsonl"
            write_queue(queue_file, [
                {"id": "t1", "state": "merged"},
                {"id": "t2", "state": "blocked", "pending_blockers": 1},
            ])

            seal_terminal(queue_file, history_file, "t1")

            live = read_queue(queue_file)
            t2 = next(t for t in live if t["id"] == "t2")
            self.assertEqual(t2["state"], "blocked")
            self.assertEqual(t2["pending_blockers"], 1)


if __name__ == "__main__":
    unittest.main()
