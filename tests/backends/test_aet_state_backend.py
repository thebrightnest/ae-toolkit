"""Tests for backend-aware aet-state transitions."""

import importlib.machinery
import importlib.util
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

_AET_STATE_PY = Path(__file__).parents[2] / "src" / "aet" / "cli" / "aet_state.py"
_spec = importlib.util.spec_from_loader(
    "aet_state", importlib.machinery.SourceFileLoader("aet_state", str(_AET_STATE_PY))
)
aet_state = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(aet_state)


class FakeBackend:
    """In-memory backend that records every call made by aet-state."""

    def __init__(self, queue, history=None):
        self.queue_file = "/fake/work-queue.json"
        self.history_file = "/fake/work-history.jsonl"
        self._queue = list(queue)
        self._history = list(history or [])
        self.calls = []

    def load(self):
        self.calls.append(("load", {}))
        path = Path(self.queue_file)
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return {"queue": list(data.get("tasks", [])), "history": []}
            return {"queue": list(data), "history": []}
        return {"queue": list(self._queue), "history": list(self._history)}

    def save(self, queue):
        self.calls.append(("save", {"queue": list(queue)}))
        self._queue = list(queue)
        path = Path(self.queue_file)
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                data = []
            if isinstance(data, dict):
                data["tasks"] = list(queue)
            else:
                data = list(queue)
            path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def transition(self, task_id, from_state, to_state, by="system", evidence=None):
        self.calls.append(
            (
                "transition",
                {
                    "task_id": task_id,
                    "from_state": from_state,
                    "to_state": to_state,
                    "by": by,
                    "evidence": evidence,
                },
            )
        )
        return True

    def plan_drift(self, plans_dir):
        self.calls.append(("plan_drift", {"plans_dir": plans_dir}))
        return []

    def close(self):
        self.calls.append(("close", {}))

    def fetch(self):
        self.calls.append(("fetch", {}))

    def push(self, *, mandatory=False):
        self.calls.append(("push", {"mandatory": mandatory}))
        return True

    def on_transition(self, task_id, from_state, to_state, evidence=None):
        self.calls.append(
            (
                "on_transition",
                {
                    "task_id": task_id,
                    "from_state": from_state,
                    "to_state": to_state,
                    "evidence": evidence,
                },
            )
        )

    def close_task(self, task_id, evidence=None):
        self.calls.append(
            ("close_task", {"task_id": task_id, "evidence": evidence})
        )

    def seal(self, task_id, history_file):
        """Mirror queue.seal_terminal against the fake's file-backed queue."""
        self.calls.append(("seal", {"task_id": task_id, "history_file": history_file}))
        path = Path(self.queue_file)
        data = json.loads(path.read_text(encoding="utf-8"))
        tasks = data.get("tasks", data) if isinstance(data, dict) else data
        task = next((t for t in tasks if t.get("id") == task_id), None)
        if task is None:
            raise ValueError(f"Task {task_id} not found in live queue {self.queue_file}")
        live = [t for t in tasks if t.get("id") != task_id]
        record = {**task, "settled_at": datetime.now(timezone.utc).isoformat()}
        os.makedirs(os.path.dirname(history_file), exist_ok=True)
        with open(history_file, "a", encoding="utf-8") as f:
            json.dump(record, f)
            f.write("\n")
        if isinstance(data, dict):
            data["tasks"] = live
        else:
            data = live
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return task


class MockResult:
    def __init__(self, returncode, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _subprocess_mock(responses):
    def mock_run(cmd, **kwargs):
        args = tuple(cmd)
        rc, out, err = responses.get(args, (1, "", ""))
        return MockResult(rc, out, err)

    return mock_run


class TestBackendAwareTransition(unittest.TestCase):
    def test_transition_uses_backend_load_and_save(self):
        """The transition command loads and saves through the configured backend."""
        backend = FakeBackend([{"id": "t1", "state": "planned"}])

        args = aet_state.argparse.Namespace(
            command="transition",
            task_id="t1",
            from_stage="planned",
            to_stage="ready",
            queue="/fake/work-queue.json",
            dry_run=False,
            reason=None,
        )

        with patch.object(aet_state, "create_backend", return_value=backend):
            rc = aet_state.cmd_transition(args)

        self.assertEqual(rc, 0)
        self.assertTrue(any(c[0] == "load" for c in backend.calls))
        saved = next((c[1]["queue"] for c in backend.calls if c[0] == "save"), None)
        self.assertIsNotNone(saved)
        self.assertEqual(saved[0]["state"], "ready")

    def test_transition_notifies_backend_hook(self):
        """A non-terminal transition calls backend.on_transition with evidence."""
        backend = FakeBackend([{"id": "t1", "state": "planned"}])

        args = aet_state.argparse.Namespace(
            command="transition",
            task_id="t1",
            from_stage="planned",
            to_stage="ready",
            queue="/fake/work-queue.json",
            dry_run=False,
            reason=None,
        )

        with patch.object(aet_state, "create_backend", return_value=backend):
            aet_state.cmd_transition(args)

        hooks = [c for c in backend.calls if c[0] == "on_transition"]
        self.assertEqual(len(hooks), 1)
        self.assertEqual(hooks[0][1]["task_id"], "t1")
        self.assertEqual(hooks[0][1]["from_state"], "planned")
        self.assertEqual(hooks[0][1]["to_state"], "ready")
        self.assertNotIn("close_task", [c[0] for c in backend.calls])

    def test_dry_run_transition_does_not_mutate_backend(self):
        """A dry-run transition validates only and never saves or hooks."""
        backend = FakeBackend([{"id": "t1", "state": "planned"}])

        args = aet_state.argparse.Namespace(
            command="transition",
            task_id="t1",
            from_stage="planned",
            to_stage="ready",
            queue="/fake/work-queue.json",
            dry_run=True,
            reason=None,
        )

        with patch.object(aet_state, "create_backend", return_value=backend):
            rc = aet_state.cmd_transition(args)

        self.assertEqual(rc, 0)
        self.assertFalse(any(c[0] in ("save", "on_transition", "close_task") for c in backend.calls))

    def test_terminal_transition_calls_backend_close_task(self):
        """A terminal transition seals the task and asks the backend to close it."""
        with tempfile.TemporaryDirectory() as tmpdir:
            queue_path = Path(tmpdir) / "work-queue.json"
            queue_path.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "id": "blocker",
                                "state": "awaiting_merge",
                                "branch": "feat-blocker",
                                "blocks": ["dependent"],
                            },
                            {
                                "id": "dependent",
                                "state": "blocked",
                                "blocked_by": ["blocker"],
                                "pending_blockers": 1,
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            backend = FakeBackend([])
            backend.queue_file = str(queue_path)
            backend.history_file = str(queue_path.with_name("work-history.jsonl"))

            responses = {
                ("git", "merge-base", "--is-ancestor", "feat-blocker", "origin/main"): (
                    0,
                    "",
                    "",
                ),
            }

            args = aet_state.argparse.Namespace(
                command="transition",
                task_id="blocker",
                from_stage="awaiting_merge",
                to_stage="merged",
                queue=str(queue_path),
                dry_run=False,
                reason=None,
            )

            with patch.object(aet_state, "create_backend", return_value=backend):
                with patch.object(
                    aet_state.subprocess, "run", side_effect=_subprocess_mock(responses)
                ):
                    rc = aet_state.cmd_transition(args)

            self.assertEqual(rc, 0)
            close_calls = [c for c in backend.calls if c[0] == "close_task"]
            self.assertEqual(len(close_calls), 1)
            self.assertEqual(close_calls[0][1]["task_id"], "blocker")

            history_file = queue_path.with_name("work-history.jsonl")
            self.assertTrue(history_file.exists())
            settled = json.loads(history_file.read_text(encoding="utf-8").strip())
            self.assertEqual(settled["id"], "blocker")
            self.assertEqual(settled["state"], "merged")


class TestBackendAwareRecordMerge(unittest.TestCase):
    def test_record_merge_calls_backend_close_task(self):
        """record-merge seals the task and asks the backend to close it."""
        with tempfile.TemporaryDirectory() as tmpdir:
            queue_path = Path(tmpdir) / "work-queue.json"
            queue_path.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "id": "t1",
                                "state": "awaiting_merge",
                                "branch": "feat-001",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            backend = FakeBackend([])
            backend.queue_file = str(queue_path)
            backend.history_file = str(queue_path.with_name("work-history.jsonl"))

            responses = {
                ("git", "fetch", "origin"): (0, "", ""),
                ("git", "rev-parse", "feat-001"): (0, "abc1234\n", ""),
                (
                    "git",
                    "merge-base",
                    "--is-ancestor",
                    "abc1234",
                    "origin/main",
                ): (0, "", ""),
            }

            args = aet_state.argparse.Namespace(
                command="record-merge",
                task_id="t1",
                queue=str(queue_path),
                dry_run=False,
            )

            with patch.object(aet_state, "create_backend", return_value=backend):
                with patch.object(
                    aet_state.subprocess, "run", side_effect=_subprocess_mock(responses)
                ):
                    rc = aet_state.cmd_record_merge(args)

            self.assertEqual(rc, 0)
            self.assertTrue(any(c[0] == "load" for c in backend.calls))
            self.assertTrue(any(c[0] == "save" for c in backend.calls))
            self.assertTrue(any(c[0] == "close_task" for c in backend.calls))

            history_file = queue_path.with_name("work-history.jsonl")
            settled = json.loads(history_file.read_text(encoding="utf-8").strip())
            self.assertEqual(settled["merge_commit"], "abc1234")


class TestBackendAwareValidate(unittest.TestCase):
    def test_validate_command_uses_backend(self):
        """The validate command loads the queue through the backend."""
        backend = FakeBackend([{"id": "t1", "state": "planned"}])

        args = aet_state.argparse.Namespace(
            command="validate",
            task_id="t1",
            from_stage="planned",
            to_stage="ready",
            queue="/fake/work-queue.json",
        )

        with patch.object(aet_state, "create_backend", return_value=backend):
            rc = aet_state.cmd_validate(args)

        self.assertEqual(rc, 0)
        self.assertTrue(any(c[0] == "load" for c in backend.calls))


class TestBackendDefaultHooks(unittest.TestCase):
    def test_default_transition_hooks_are_safe(self):
        """The base backend provides no-op on_transition and close_task hooks."""
        from aet.backends.json_backend import JsonBackend

        with tempfile.TemporaryDirectory() as tmpdir:
            queue_file = str(Path(tmpdir) / "work-queue.json")
            history_file = str(Path(tmpdir) / "work-history.jsonl")
            backend = JsonBackend(queue_file, history_file)

            # These should not raise and should not mutate the queue.
            backend.on_transition("t1", "planned", "ready")
            backend.close_task("t1")


if __name__ == "__main__":
    unittest.main()
