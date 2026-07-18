"""Tests for aet-work backend abstraction."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "aet-work" / "lib"))

import json
import subprocess
import tempfile
import unittest
from abc import ABC

from backends.base import TaskBackend
from backends.factory import UnknownBackendError, create_backend
from backends.git_refs_backend import GitRefsBackend
from backends.json_backend import JsonBackend


class TestTaskBackend(unittest.TestCase):
    def test_task_backend_is_abstract(self):
        with self.assertRaises(TypeError):
            TaskBackend()

    def test_task_backend_is_abc_subclass(self):
        self.assertTrue(issubclass(TaskBackend, ABC))


class TestJsonBackend(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.queue_file = str(Path(self.tmp.name) / "work-queue.json")
        self.history_file = str(Path(self.tmp.name) / "work-history.jsonl")
        self.plans_dir = Path(self.tmp.name) / "plans"
        self.plans_dir.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_load_reads_queue_and_history(self):
        queue = [{"id": "t1", "state": "ready"}]
        with open(self.queue_file, "w", encoding="utf-8") as f:
            json.dump(queue, f)
        with open(self.history_file, "w", encoding="utf-8") as f:
            f.write('{"id": "h1", "state": "merged"}\n')

        backend = JsonBackend(self.queue_file, self.history_file)
        data = backend.load()

        self.assertEqual(data["queue"], queue)
        self.assertEqual([t["id"] for t in data["history"]], ["h1"])

    def test_load_returns_empty_lists_for_missing_files(self):
        backend = JsonBackend(self.queue_file, self.history_file)
        data = backend.load()

        self.assertEqual(data["queue"], [])
        self.assertEqual(data["history"], [])

    def test_load_preserves_dict_wrapper(self):
        original = {
            "source_prd": "docs/prds/test.md",
            "tasks": [{"id": "t1", "state": "ready"}],
        }
        with open(self.queue_file, "w", encoding="utf-8") as f:
            json.dump(original, f)

        backend = JsonBackend(self.queue_file, self.history_file)
        data = backend.load()
        self.assertEqual(data["queue"], original["tasks"])

    def test_save_writes_queue(self):
        backend = JsonBackend(self.queue_file, self.history_file)
        queue = [{"id": "t1", "state": "ready"}]
        backend.save(queue)

        with open(self.queue_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertEqual(data, queue)

    def test_save_preserves_wrapper_metadata(self):
        original = {
            "source_prd": "docs/prds/test.md",
            "queue_updated_at": "2026-01-01T00:00:00Z",
            "tasks": [{"id": "t1", "state": "ready"}],
        }
        with open(self.queue_file, "w", encoding="utf-8") as f:
            json.dump(original, f)

        backend = JsonBackend(self.queue_file, self.history_file)
        backend.load()
        backend.save([{"id": "t1", "state": "in_progress"}])

        with open(self.queue_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertEqual(data.get("source_prd"), "docs/prds/test.md")
        self.assertEqual(data.get("queue_updated_at"), "2026-01-01T00:00:00Z")
        self.assertEqual(data["tasks"][0]["state"], "in_progress")

    def test_plan_drift_returns_orphaned_plans(self):
        (self.plans_dir / "tracked.md").write_text("# Tracked", encoding="utf-8")
        (self.plans_dir / "orphan.md").write_text("# Orphan", encoding="utf-8")

        with open(self.queue_file, "w", encoding="utf-8") as f:
            json.dump([{"id": "t1", "plan_file": str(self.plans_dir / "tracked.md")}], f)

        backend = JsonBackend(self.queue_file, self.history_file)
        orphaned = backend.plan_drift(str(self.plans_dir))

        self.assertEqual(orphaned, [str(self.plans_dir / "orphan.md")])

    def test_plan_drift_returns_empty_when_all_tracked(self):
        (self.plans_dir / "tracked.md").write_text("# Tracked", encoding="utf-8")

        with open(self.queue_file, "w", encoding="utf-8") as f:
            json.dump([{"id": "t1", "plan_file": str(self.plans_dir / "tracked.md")}], f)

        backend = JsonBackend(self.queue_file, self.history_file)
        orphaned = backend.plan_drift(str(self.plans_dir))
        self.assertEqual(orphaned, [])

    def test_plan_drift_considers_history(self):
        (self.plans_dir / "settled.md").write_text("# Settled", encoding="utf-8")

        with open(self.history_file, "w", encoding="utf-8") as f:
            f.write(f'{{"id": "t1", "plan_file": "{self.plans_dir / "settled.md"}"}}\n')

        backend = JsonBackend(self.queue_file, self.history_file)
        orphaned = backend.plan_drift(str(self.plans_dir))
        self.assertEqual(orphaned, [])

    def test_close_is_safe(self):
        backend = JsonBackend(self.queue_file, self.history_file)
        backend.close()

    def test_sync_task_is_safe_noop(self):
        backend = JsonBackend(self.queue_file, self.history_file)
        backend.sync_task({"id": "t1", "state": "ready"}, is_new=True)
        backend.sync_task({"id": "t1", "state": "ready"}, is_new=False)


class TestFactory(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.queue_file = str(Path(self.tmp.name) / "work-queue.json")
        self.history_file = str(Path(self.tmp.name) / "work-history.jsonl")

    def tearDown(self):
        self.tmp.cleanup()

    def test_factory_returns_json_backend_by_default(self):
        backend = create_backend(
            config_path=str(Path(self.tmp.name) / "missing.json"),
            queue_file=self.queue_file,
            history_file=self.history_file,
        )
        self.assertIsInstance(backend, JsonBackend)

    def test_factory_returns_json_backend_when_configured(self):
        config_path = Path(self.tmp.name) / "aet-work.json"
        config_path.write_text('{"task_backend": "json"}', encoding="utf-8")

        backend = create_backend(
            config_path=str(config_path),
            queue_file=self.queue_file,
            history_file=self.history_file,
        )
        self.assertIsInstance(backend, JsonBackend)

    def test_factory_returns_git_refs_backend_when_configured(self):
        config_path = Path(self.tmp.name) / "aet-work.json"
        config_path.write_text('{"task_backend": "git-refs"}', encoding="utf-8")
        # GitRefsBackend requires the queue path to live inside a git repo.
        subprocess.run(["git", "init", "-q", self.tmp.name], check=True)

        backend = create_backend(
            config_path=str(config_path),
            queue_file=self.queue_file,
            history_file=self.history_file,
        )
        self.assertIsInstance(backend, GitRefsBackend)

    def test_factory_raises_named_error_for_github_backend(self):
        config_path = Path(self.tmp.name) / "aet-work.json"
        config_path.write_text(
            '{"task_backend": "github", "github": {"repo": "owner/repo"}}',
            encoding="utf-8",
        )

        with self.assertRaises(UnknownBackendError) as ctx:
            create_backend(
                config_path=str(config_path),
                queue_file=self.queue_file,
                history_file=self.history_file,
            )
        self.assertIn("projections", str(ctx.exception).lower())

    def test_factory_raises_named_error_for_both_backend(self):
        config_path = Path(self.tmp.name) / "aet-work.json"
        config_path.write_text('{"task_backend": "both"}', encoding="utf-8")

        with self.assertRaises(UnknownBackendError) as ctx:
            create_backend(
                config_path=str(config_path),
                queue_file=self.queue_file,
                history_file=self.history_file,
            )
        self.assertIn("projections", str(ctx.exception).lower())

    def test_factory_raises_for_unknown_backend(self):
        config_path = Path(self.tmp.name) / "aet-work.json"
        config_path.write_text('{"task_backend": "magic"}', encoding="utf-8")

        with self.assertRaises(UnknownBackendError):
            create_backend(
                config_path=str(config_path),
                queue_file=self.queue_file,
                history_file=self.history_file,
            )


if __name__ == "__main__":
    unittest.main()
