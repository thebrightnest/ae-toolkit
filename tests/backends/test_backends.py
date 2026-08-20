"""Tests for aet-work backend abstraction."""

import subprocess
import tempfile
import unittest
from abc import ABC
from pathlib import Path

from aet.backends.base import TaskBackend
from aet.backends.factory import (
    LegacyTaskBackendError,
    QueueOutsideRepositoryError,
    create_backend,
)
from aet.backends.git_refs_backend import GitRefsBackend


class TestTaskBackend(unittest.TestCase):
    def test_task_backend_is_abstract(self):
        with self.assertRaises(TypeError):
            TaskBackend()

    def test_task_backend_is_abc_subclass(self):
        self.assertTrue(issubclass(TaskBackend, ABC))


class TestFactory(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.queue_file = str(Path(self.tmp.name) / "aet-queue")
        self.history_file = str(Path(self.tmp.name) / "work-history.jsonl")

    def tearDown(self):
        self.tmp.cleanup()

    def test_factory_returns_git_refs_backend_by_default(self):
        subprocess.run(["git", "init", "-q", self.tmp.name], check=True)

        backend = create_backend(
            config_path=str(Path(self.tmp.name) / "missing.json"),
            queue_file=self.queue_file,
            history_file=self.history_file,
        )
        self.assertIsInstance(backend, GitRefsBackend)

    def test_factory_returns_git_refs_backend_with_other_config(self):
        config_path = Path(self.tmp.name) / "aet-config.json"
        config_path.write_text('{"integration_mode": "single-pr"}', encoding="utf-8")
        subprocess.run(["git", "init", "-q", self.tmp.name], check=True)

        backend = create_backend(
            config_path=str(config_path),
            queue_file=self.queue_file,
            history_file=self.history_file,
        )
        self.assertIsInstance(backend, GitRefsBackend)

    def test_factory_raises_migration_error_for_json_backend(self):
        config_path = Path(self.tmp.name) / "aet-config.json"
        config_path.write_text('{"task_backend": "json"}', encoding="utf-8")

        with self.assertRaises(LegacyTaskBackendError) as ctx:
            create_backend(
                config_path=str(config_path),
                queue_file=self.queue_file,
                history_file=self.history_file,
            )
        self.assertIn("migration", str(ctx.exception).lower())

    def test_factory_raises_migration_error_for_any_task_backend_key(self):
        config_path = Path(self.tmp.name) / "aet-config.json"
        config_path.write_text('{"task_backend": "git-refs"}', encoding="utf-8")

        with self.assertRaises(LegacyTaskBackendError) as ctx:
            create_backend(
                config_path=str(config_path),
                queue_file=self.queue_file,
                history_file=self.history_file,
            )
        self.assertIn("migration", str(ctx.exception).lower())

    def test_factory_raises_queue_outside_repo_error(self):
        with self.assertRaises(QueueOutsideRepositoryError):
            create_backend(
                config_path=str(Path(self.tmp.name) / "missing.json"),
                queue_file=self.queue_file,
                history_file=self.history_file,
            )


if __name__ == "__main__":
    unittest.main()
