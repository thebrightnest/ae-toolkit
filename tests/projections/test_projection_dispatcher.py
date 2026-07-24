"""Tests for the fail-open projection dispatcher."""

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from aet.backends.factory import resolve_config
from aet.backends.json_backend import JsonBackend
from aet.projections.base import Projection
from aet.projections.dispatcher import ProjectionDispatcher, resolve_projections


class _CaptureStderr:
    """Context manager that captures sys.stderr."""

    def __enter__(self):
        self.original = sys.stderr
        self.buffer = io.StringIO()
        sys.stderr = self.buffer
        return self.buffer

    def __exit__(self, *args):
        sys.stderr = self.original


class FailingProjection(Projection):
    """Projection whose methods always raise."""

    def __init__(self, name: str = "FailingProjection"):
        self._name = name

    def on_add(self, task, is_new):
        raise RuntimeError(f"{self._name} on_add failed")

    def on_transition(self, task_id, from_state, to_state, evidence=None):
        raise RuntimeError(f"{self._name} on_transition failed")

    def on_close(self, task_id, evidence=None):
        raise RuntimeError(f"{self._name} on_close failed")

    def ensure_labels(self):
        raise RuntimeError(f"{self._name} ensure_labels failed")

    def reconcile(self, apply=False):
        raise RuntimeError(f"{self._name} reconcile failed")


class NoOpProjection(Projection):
    """Projection that records calls but never raises."""

    def __init__(self):
        self.calls = []

    def on_add(self, task, is_new):
        self.calls.append(("on_add", task, is_new))

    def on_transition(self, task_id, from_state, to_state, evidence=None):
        self.calls.append(
            ("on_transition", task_id, from_state, to_state, evidence)
        )

    def on_close(self, task_id, evidence=None):
        self.calls.append(("on_close", task_id, evidence))

    def ensure_labels(self):
        self.calls.append(("ensure_labels",))

    def reconcile(self, apply=False):
        self.calls.append(("reconcile", apply))


class TestProjectionDispatcher(unittest.TestCase):
    def test_dispatcher_swallows_projection_error_and_warns(self):
        dispatcher = ProjectionDispatcher([FailingProjection()])

        with _CaptureStderr() as stderr:
            dispatcher.on_add({"id": "t1"}, is_new=True)

        warning = stderr.getvalue()
        self.assertIn("warning:", warning)
        self.assertIn("FailingProjection", warning)
        self.assertIn("on_add failed", warning)

    def test_dispatcher_calls_all_projections_despite_failure(self):
        ok = NoOpProjection()
        dispatcher = ProjectionDispatcher([FailingProjection(), ok])

        with _CaptureStderr():
            dispatcher.on_add({"id": "t1"}, is_new=True)

        self.assertEqual(len(ok.calls), 1)
        self.assertEqual(ok.calls[0][0], "on_add")

    def test_dispatcher_methods_cover_lifecycle(self):
        ok = NoOpProjection()
        dispatcher = ProjectionDispatcher([ok])

        dispatcher.on_add({"id": "t1"}, is_new=True)
        dispatcher.on_transition("t1", "planned", "ready", evidence={"by": "test"})
        dispatcher.on_close("t1", evidence={"state": "merged"})
        dispatcher.ensure_labels()
        dispatcher.reconcile()

        self.assertEqual(ok.calls[0], ("on_add", {"id": "t1"}, True))
        self.assertEqual(
            ok.calls[1],
            ("on_transition", "t1", "planned", "ready", {"by": "test"}),
        )
        self.assertEqual(ok.calls[2], ("on_close", "t1", {"state": "merged"}))
        self.assertEqual(ok.calls[3], ("ensure_labels",))
        self.assertEqual(ok.calls[4], ("reconcile", False))


class TestProjectionStorageSeparation(unittest.TestCase):
    """Fail-open must not leak into storage writes (R-4, R-5)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.queue_file = str(Path(self.tmp.name) / "work-queue.json")
        self.history_file = str(Path(self.tmp.name) / "work-history.jsonl")

    def tearDown(self):
        self.tmp.cleanup()

    def test_storage_write_proceeds_when_projection_raises(self):
        backend = JsonBackend(self.queue_file, self.history_file)
        dispatcher = ProjectionDispatcher([FailingProjection()])
        queue = [{"id": "t1", "state": "ready"}]

        with _CaptureStderr() as stderr:
            backend.save(queue)
            dispatcher.on_add({"id": "t1"}, is_new=True)

        with open(self.queue_file, "r", encoding="utf-8") as f:
            self.assertEqual(json.load(f), queue)
        self.assertIn("warning:", stderr.getvalue())

    def test_storage_failure_still_raises(self):
        backend = JsonBackend(self.queue_file, self.history_file)
        dispatcher = ProjectionDispatcher([NoOpProjection()])

        # Create the queue file first, then replace it with a directory so the
        # JSON write fails.
        Path(self.queue_file).write_text("[]", encoding="utf-8")
        os.remove(self.queue_file)
        Path(self.queue_file).mkdir()

        with self.assertRaises(OSError):
            backend.save([{"id": "t1"}])

        # The dispatcher is not involved in storage failures.
        self.assertEqual(dispatcher.projections[0].calls, [])


class TestResolveProjections(unittest.TestCase):
    def test_empty_projections_returns_empty_dispatcher(self):
        dispatcher = resolve_projections({"task_backend": "json"})
        self.assertEqual(dispatcher.projections, [])

    def test_github_projection_resolved_from_config(self):
        dispatcher = resolve_projections(
            {
                "task_backend": "git-refs",
                "projections": [
                    {"type": "github", "repo": "owner/repo", "label_prefix": "aet"}
                ],
            }
        )

        self.assertEqual(len(dispatcher.projections), 1)
        projection = dispatcher.projections[0]
        self.assertEqual(type(projection).__name__, "GitHubBackend")
        self.assertEqual(projection.repo, "owner/repo")
        self.assertEqual(projection.label_prefix, "aet")

    def test_github_projection_repo_fallback_to_top_level_config(self):
        dispatcher = resolve_projections(
            {
                "task_backend": "git-refs",
                "github": {"repo": "legacy/repo", "label_prefix": "legacy"},
                "projections": [{"type": "github"}],
            }
        )

        projection = dispatcher.projections[0]
        self.assertEqual(projection.repo, "legacy/repo")
        self.assertEqual(projection.label_prefix, "legacy")

    def test_unknown_projection_type_is_ignored(self):
        dispatcher = resolve_projections(
            {
                "task_backend": "git-refs",
                "projections": [{"type": "azure_devops"}],
            }
        )
        self.assertEqual(dispatcher.projections, [])


class TestProjectionsResolvedExternalFirst(unittest.TestCase):
    """Projection config uses the same external-first resolution as backends (R-1)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name) / "project"
        self.project.mkdir()
        self.home = Path(self.tmp.name) / "home"
        self.home.mkdir()
        subprocess.run(
            ["git", "init", "-q", str(self.project)],
            check=True,
            capture_output=True,
        )

    def tearDown(self):
        self.tmp.cleanup()

    def _write_in_tree(self, config):
        path = self.project / ".agents" / "aet-config.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(config), encoding="utf-8")

    def _write_external(self, slug, config):
        path = self.home / ".aet" / slug / "config.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(config), encoding="utf-8")

    def test_projections_resolved_external_first(self):
        self._write_in_tree(
            {
                "task_backend": "json",
                "projections": [{"type": "github", "repo": "in/tree"}],
            }
        )
        self._write_external(
            "myproject/main",
            {
                "task_backend": "git-refs",
                "projections": [{"type": "github", "repo": "external/repo"}],
            },
        )

        with mock.patch.dict(
            os.environ,
            {"HOME": str(self.home), "AET_PROJECT_ID": "myproject/main"},
            clear=False,
        ):
            config = resolve_config(str(self.project / ".agents" / "aet-config.json"))

        dispatcher = resolve_projections(config)
        self.assertEqual(len(dispatcher.projections), 1)
        self.assertEqual(dispatcher.projections[0].repo, "external/repo")

    def test_precedence_env_over_external_over_in_tree(self):
        env_config = self.home / "env-config.json"
        env_config.write_text(
            json.dumps(
                {
                    "task_backend": "json",
                    "projections": [{"type": "github", "repo": "env/repo"}],
                }
            ),
            encoding="utf-8",
        )

        self._write_external(
            "myproject/main",
            {
                "task_backend": "git-refs",
                "projections": [{"type": "github", "repo": "external/repo"}],
            },
        )
        self._write_in_tree(
            {
                "task_backend": "git-refs",
                "projections": [{"type": "github", "repo": "in/tree"}],
            }
        )

        with mock.patch.dict(
            os.environ,
            {
                "HOME": str(self.home),
                "AET_PROJECT_ID": "myproject/main",
                "AET_WORK_CONFIG": str(env_config),
            },
            clear=False,
        ):
            config = resolve_config(str(self.project / ".agents" / "aet-config.json"))

        dispatcher = resolve_projections(config)
        self.assertEqual(dispatcher.projections[0].repo, "env/repo")


if __name__ == "__main__":
    unittest.main()
