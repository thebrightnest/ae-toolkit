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
    mark_completed,
    mark_status,
    promote_dependents,
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

    def test_get_next_unblocked(self):
        queue = [
            {"id": "t1", "status": "blocked"},
            {"id": "t2", "status": "unblocked"},
        ]
        task = get_next_unblocked(queue)
        self.assertEqual(task["id"], "t2")

    def test_get_next_unblocked_none(self):
        queue = [{"id": "t1", "status": "blocked"}]
        self.assertIsNone(get_next_unblocked(queue))

    def test_has_pending_tasks(self):
        queue = [{"id": "t1", "status": "in-progress"}]
        self.assertTrue(has_pending_tasks(queue))

    def test_has_pending_tasks_all_done(self):
        queue = [{"id": "t1", "status": "done"}, {"id": "t2", "status": "merged"}]
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

    def test_promote_dependents(self):
        queue = [
            {"id": "t1", "status": "done"},
            {"id": "t2", "status": "blocked", "blocked_by": ["t1"]},
        ]
        promote_dependents(queue)
        self.assertEqual(queue[1]["status"], "unblocked")

    def test_record_task_meta(self):
        queue = [{"id": "t1"}]
        record_task_meta(queue, "t1", "/path/to/wt", "feat-001")
        self.assertEqual(queue[0]["worktree"], "/path/to/wt")
        self.assertEqual(queue[0]["branch"], "feat-001")


if __name__ == "__main__":
    unittest.main()
