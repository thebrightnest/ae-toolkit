"""Tests for aet-work backend abstraction."""

import io
import subprocess
import tempfile
import unittest
from abc import ABC
from contextlib import redirect_stderr
from pathlib import Path

from aet.backends.base import TaskBackend
from aet.backends.factory import (
    LegacyTaskBackendError,
    QueueOutsideRepositoryError,
    create_backend,
)
from aet.backends.git_refs_backend import GitRefsBackend
from tests.cli._helpers import seed_legacy_epic


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

        with self.assertRaises(LegacyTaskBackendError):
            create_backend(
                config_path=str(config_path),
                queue_file=self.queue_file,
                history_file=self.history_file,
            )
    def test_factory_raises_queue_outside_repo_error(self):
        with self.assertRaises(QueueOutsideRepositoryError):
            create_backend(
                config_path=str(Path(self.tmp.name) / "missing.json"),
                queue_file=self.queue_file,
                history_file=self.history_file,
            )

    def _backend(self):
        return create_backend(
            config_path=str(Path(self.tmp.name) / "missing.json"),
            queue_file=self.queue_file,
            history_file=self.history_file,
        )

    def test_envelope_without_epic_key_loads_silently(self):
        """R-11: an envelope without the epic key loads with no warning."""
        subprocess.run(["git", "init", "-q", self.tmp.name], check=True)
        backend = self._backend()
        backend.save([], wrapper={"source_prd": "docs/prds/test.md"})
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            backend.load()
        self.assertIsNone(backend.read_legacy_epic())
        self.assertEqual(stderr.getvalue(), "")
        backend.close()

    def test_legacy_epic_key_warns_once_and_is_dropped_on_save(self):
        """R-11: a legacy epic key warns once, names its branch, and is absent after save."""
        subprocess.run(["git", "init", "-q", self.tmp.name], check=True)
        seed_legacy_epic(self.tmp.name, {"branch": "feat/legacy-epic"})
        backend = self._backend()
        self.assertEqual(backend.read_legacy_epic(), {"branch": "feat/legacy-epic"})

        stderr = io.StringIO()
        with redirect_stderr(stderr):
            data = backend.load()
            backend.load()
            backend.save(data["queue"])
        self.assertEqual(stderr.getvalue().count("legacy active epic"), 1)
        self.assertIn("feat/legacy-epic", stderr.getvalue())
        self.assertIsNone(backend.read_legacy_epic())
        backend.close()

    def test_epic_declaration_writers_are_removed(self):
        """R-11: the backend no longer declares or clears an epic."""
        subprocess.run(["git", "init", "-q", self.tmp.name], check=True)
        backend = self._backend()
        self.assertFalse(hasattr(backend, "set_epic"))
        self.assertFalse(hasattr(backend, "clear_epic"))
        self.assertFalse(hasattr(backend, "read_epic"))
        backend.close()

if __name__ == "__main__":
    unittest.main()
