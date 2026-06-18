"""Tests for queue module."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "aet-work" / "lib"))

import json
import tempfile
import unittest

from queue import (
    get_next_unblocked,
    has_pending_tasks,
    mark_awaiting_merge,
    mark_completed,
    mark_status,
    read_queue,
    record_task_meta,
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


if __name__ == "__main__":
    unittest.main()
