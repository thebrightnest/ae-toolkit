"""Tests for aet-work backend abstraction."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "aet-work" / "lib"))

import json
import tempfile
import unittest
import unittest.mock
from abc import ABC

from backends.base import TaskBackend
from backends.factory import create_backend
from backends.github_backend import GitHubBackend
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


class TestGithubBackend(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.queue_file = str(Path(self.tmp.name) / "work-queue.json")
        self.history_file = str(Path(self.tmp.name) / "work-history.jsonl")
        self.repo = "owner/repo"
        self.backend = GitHubBackend(
            queue_file=self.queue_file,
            history_file=self.history_file,
            repo=self.repo,
        )
        self.run_patcher = unittest.mock.patch("backends.github_backend.subprocess.run")
        self.mock_run = self.run_patcher.start()

    def tearDown(self):
        self.run_patcher.stop()
        self.tmp.cleanup()

    def _make_result(self, stdout="", returncode=0):
        result = unittest.mock.MagicMock()
        result.returncode = returncode
        result.stdout = stdout
        result.stderr = ""
        return result

    def test_load_returns_empty_lists_for_missing_files(self):
        data = self.backend.load()
        self.assertEqual(data["queue"], [])
        self.assertEqual(data["history"], [])

    def test_save_writes_local_json_mirror(self):
        queue = [{"id": "t1", "state": "ready"}]
        self.backend.save(queue)

        with open(self.queue_file, "r", encoding="utf-8") as f:
            self.assertEqual(json.load(f), queue)

    def test_sync_task_creates_issue_for_new_task(self):
        self.mock_run.return_value = self._make_result(stdout="https://github.com/owner/repo/issues/42\n")
        task = {
            "id": "feat-001",
            "title": "First task",
            "state": "ready",
            "plan_file": "docs/plans/feat-001.md",
        }

        self.backend.sync_task(task, is_new=True)

        self.mock_run.assert_called_once()
        call_args = self.mock_run.call_args[0][0]
        self.assertIn("issue", call_args)
        self.assertIn("create", call_args)
        self.assertIn("--repo", call_args)
        self.assertIn(self.repo, call_args)
        self.assertIn("--label", call_args)
        self.assertIn("aet:ready", call_args)
        self.assertEqual(task["github_issue_number"], 42)
        self.assertEqual(task["github_issue_url"], "https://github.com/owner/repo/issues/42")

    def test_sync_task_updates_labels_for_existing_task(self):
        self.mock_run.side_effect = [
            self._make_result(stdout='{"labels": []}'),
            self._make_result(stdout=""),
        ]
        task = {
            "id": "feat-001",
            "title": "First task",
            "state": "ready",
            "plan_file": "docs/plans/feat-001.md",
            "github_issue_number": 42,
        }

        self.backend.sync_task(task, is_new=False)

        self.assertEqual(self.mock_run.call_count, 2)
        edit_call = self.mock_run.call_args_list[1][0][0]
        self.assertIn("issue", edit_call)
        self.assertIn("edit", edit_call)
        self.assertIn("42", edit_call)
        self.assertIn("--repo", edit_call)
        self.assertIn(self.repo, edit_call)
        self.assertIn("--add-label", edit_call)
        self.assertIn("aet:ready", edit_call)

    def test_sync_task_removes_stale_labels_for_existing_task(self):
        self.mock_run.side_effect = [
            self._make_result(
                stdout='{"labels": [{"name": "aet:planned"}, {"name": "aet:blocked"}]}'
            ),
            self._make_result(stdout=""),
        ]
        task = {
            "id": "feat-001",
            "title": "First task",
            "state": "ready",
            "plan_file": "docs/plans/feat-001.md",
            "github_issue_number": 42,
        }

        self.backend.sync_task(task, is_new=False)

        self.assertEqual(self.mock_run.call_count, 2)
        edit_call = self.mock_run.call_args_list[1][0][0]
        self.assertIn("--remove-label", edit_call)
        self.assertIn("aet:planned", edit_call)
        self.assertIn("aet:blocked", edit_call)

    def test_sync_task_raises_clear_error_when_gh_fails(self):
        self.mock_run.return_value = self._make_result(stdout="", returncode=1)
        self.mock_run.return_value.stderr = "gh not authenticated"
        task = {
            "id": "feat-001",
            "title": "First task",
            "state": "ready",
            "plan_file": "docs/plans/feat-001.md",
        }

        with self.assertRaises(RuntimeError):
            self.backend.sync_task(task, is_new=True)

    def test_close_is_safe(self):
        self.backend.close()


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

    def test_factory_returns_github_backend_when_configured(self):
        config_path = Path(self.tmp.name) / "aet-work.json"
        config_path.write_text(
            '{"task_backend": "github", "github": {"repo": "owner/repo"}}',
            encoding="utf-8",
        )

        backend = create_backend(
            config_path=str(config_path),
            queue_file=self.queue_file,
            history_file=self.history_file,
        )
        self.assertIsInstance(backend, GitHubBackend)
        self.assertEqual(backend.repo, "owner/repo")

    def test_factory_raises_for_both_backend(self):
        config_path = Path(self.tmp.name) / "aet-work.json"
        config_path.write_text('{"task_backend": "both"}', encoding="utf-8")

        with self.assertRaises(NotImplementedError):
            create_backend(
                config_path=str(config_path),
                queue_file=self.queue_file,
                history_file=self.history_file,
            )

    def test_factory_raises_for_unknown_backend(self):
        config_path = Path(self.tmp.name) / "aet-work.json"
        config_path.write_text('{"task_backend": "magic"}', encoding="utf-8")

        with self.assertRaises(ValueError):
            create_backend(
                config_path=str(config_path),
                queue_file=self.queue_file,
                history_file=self.history_file,
            )


if __name__ == "__main__":
    unittest.main()
