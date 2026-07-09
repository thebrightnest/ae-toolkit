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
    read_history,
    read_queue,
    record_task_meta,
    seal_terminal,
    write_queue,
)


class TestQueue(unittest.TestCase):
    def test_read_write_queue(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path = f.name

        queue = [{"id": "t1", "state": "ready"}]
        write_queue(path, queue)
        read_back = read_queue(path)
        self.assertEqual(read_back, queue)

    def test_read_queue_nested(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path = f.name
            json.dump({"tasks": [{"id": "t1", "state": "blocked"}]}, f)

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
                "tasks": [{"id": "t1", "state": "ready"}],
            }
            json.dump(original, f)

        queue = read_queue(path)
        queue[0]["state"] = "in_progress"
        write_queue(path, queue)

        with open(path, "r") as f:
            data = json.load(f)

        self.assertIsInstance(data, dict)
        self.assertEqual(data.get("source_prd"), "docs/prds/test.md")
        self.assertEqual(data.get("queue_updated_at"), "2026-01-01T00:00:00Z")
        self.assertEqual(data["tasks"][0]["state"], "in_progress")
        self.assertNotIn("status", data["tasks"][0])

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

    def test_read_queue_normalizes_legacy_status_records(self):
        """A status-only legacy record gains state and loses status on read."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path = f.name
            json.dump([{"id": "t1", "status": "unblocked"}], f)

        queue = read_queue(path)
        self.assertEqual(queue[0]["state"], "ready")
        self.assertNotIn("status", queue[0])

    def test_read_queue_keeps_state_when_present(self):
        """Modern records with state are returned unchanged and status stripped."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path = f.name
            json.dump([{"id": "t1", "state": "ready", "status": "unblocked"}], f)

        queue = read_queue(path)
        self.assertEqual(queue[0]["state"], "ready")
        self.assertNotIn("status", queue[0])

    def test_write_queue_never_emits_status_key(self):
        """write_queue strips any status key before serializing tasks."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path = f.name

        write_queue(path, [{"id": "t1", "state": "ready", "status": "unblocked"}])

        with open(path, "r") as f:
            data = json.load(f)

        self.assertEqual(data[0]["state"], "ready")
        self.assertNotIn("status", data[0])

    def test_has_pending_tasks_awaiting_merge(self):
        queue = [{"id": "t1", "state": "awaiting_merge"}]
        self.assertTrue(has_pending_tasks(queue))

    def test_record_task_meta(self):
        queue = [{"id": "t1"}]
        record_task_meta(queue, "t1", "/path/to/wt", "feat-001")
        self.assertEqual(queue[0]["worktree"], "/path/to/wt")
        self.assertEqual(queue[0]["branch"], "feat-001")

    def test_read_history_missing_file_returns_empty_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            history_file = Path(tmp) / "work-history.jsonl"
            self.assertEqual(read_history(str(history_file)), [])

    def test_read_history_skips_blank_lines_and_parses_jsonl(self):
        with tempfile.TemporaryDirectory() as tmp:
            history_file = Path(tmp) / "work-history.jsonl"
            history_file.write_text(
                '{"id": "t1", "state": "merged"}\n\n{"id": "t2", "state": "abandoned"}\n',
                encoding="utf-8",
            )
            records = read_history(str(history_file))
            self.assertEqual([r["id"] for r in records], ["t1", "t2"])

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
