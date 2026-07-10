"""Tests for the GitHub Issues task backend."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.parent / "aet-work" / "lib"))

from backends.github_backend import STATE_LABELS, GitHubBackend


def _completed(stdout: str = "", returncode: int = 0, stderr: str = ""):
    return subprocess.CompletedProcess(
        args=["gh"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def _label_list_response(labels: list[str]) -> str:
    return json.dumps([{"name": name} for name in labels])


def _write_queue(path: str, tasks: list[dict]) -> None:
    Path(path).write_text(json.dumps(tasks), encoding="utf-8")


class TestGitHubBackend(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.queue_file = str(Path(self.tmp.name) / "work-queue.json")
        self.history_file = str(Path(self.tmp.name) / "work-history.jsonl")
        self.backend = GitHubBackend(
            repo="owner/repo",
            queue_file=self.queue_file,
            history_file=self.history_file,
        )

    def tearDown(self):
        self.tmp.cleanup()

    def _label_names_from_cmd(self, cmd: list[str]) -> set[str]:
        names = set()
        for i, arg in enumerate(cmd):
            if arg == "--add-label" and i + 1 < len(cmd):
                names.add(cmd[i + 1])
        return names

    def test_backend_is_task_backend(self):
        from backends.base import TaskBackend

        self.assertTrue(issubclass(GitHubBackend, TaskBackend))

    def test_load_reads_local_json_mirror(self):
        _write_queue(self.queue_file, [{"id": "t1", "state": "ready"}])
        data = self.backend.load()
        self.assertEqual(data["queue"], [{"id": "t1", "state": "ready"}])
        self.assertEqual(data["history"], [])

    def test_save_writes_local_json_mirror(self):
        queue = [{"id": "t1", "state": "ready"}]
        self.backend.save(queue)

        with open(self.queue_file, "r", encoding="utf-8") as f:
            self.assertEqual(json.load(f), queue)

    @mock.patch("backends.github_backend.subprocess.run")
    def test_sync_task_creates_issue_for_new_task(self, mock_run):
        mock_run.return_value = _completed(
            stdout="https://github.com/owner/repo/issues/42\n"
        )
        task = {
            "id": "feat-001",
            "title": "First task",
            "state": "ready",
            "plan_file": "docs/plans/feat-001.md",
        }

        self.backend.sync_task(task, is_new=True)

        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        self.assertIn("issue", call_args)
        self.assertIn("create", call_args)
        self.assertIn("--repo", call_args)
        self.assertIn("owner/repo", call_args)
        self.assertIn("--label", call_args)
        self.assertIn("aet:ready", call_args)
        self.assertEqual(task["github_issue_number"], 42)
        self.assertEqual(
            task["github_issue_url"],
            "https://github.com/owner/repo/issues/42",
        )

    @mock.patch("backends.github_backend.subprocess.run")
    def test_sync_task_updates_labels_for_existing_task(self, mock_run):
        mock_run.side_effect = [
            _completed(stdout='{"labels": []}'),
            _completed(stdout=""),
        ]
        task = {
            "id": "feat-001",
            "title": "First task",
            "state": "ready",
            "plan_file": "docs/plans/feat-001.md",
            "github_issue_number": 42,
        }

        self.backend.sync_task(task, is_new=False)

        self.assertEqual(mock_run.call_count, 2)
        edit_call = mock_run.call_args_list[1][0][0]
        self.assertIn("issue", edit_call)
        self.assertIn("edit", edit_call)
        self.assertIn("42", edit_call)
        self.assertIn("--repo", edit_call)
        self.assertIn("owner/repo", edit_call)
        self.assertIn("--add-label", edit_call)
        self.assertIn("aet:ready", edit_call)

    @mock.patch("backends.github_backend.subprocess.run")
    def test_sync_task_removes_stale_labels_for_existing_task(self, mock_run):
        mock_run.side_effect = [
            _completed(
                stdout='{"labels": [{"name": "aet:planned"}, {"name": "aet:blocked"}]}'
            ),
            _completed(stdout=""),
        ]
        task = {
            "id": "feat-001",
            "title": "First task",
            "state": "ready",
            "plan_file": "docs/plans/feat-001.md",
            "github_issue_number": 42,
        }

        self.backend.sync_task(task, is_new=False)

        self.assertEqual(mock_run.call_count, 2)
        edit_call = mock_run.call_args_list[1][0][0]
        self.assertIn("--remove-label", edit_call)
        self.assertIn("aet:planned", edit_call)
        self.assertIn("aet:blocked", edit_call)

    @mock.patch("backends.github_backend.subprocess.run")
    def test_ensure_labels_creates_missing_labels(self, mock_run):
        existing = ["aet:ready", "aet:blocked"]

        def side_effect(cmd, **kwargs):
            if cmd[:3] == ["gh", "label", "list"]:
                return _completed(stdout=_label_list_response(existing))
            if cmd[:3] == ["gh", "label", "create"]:
                return _completed(stdout="")
            raise AssertionError(f"unexpected command: {cmd}")

        mock_run.side_effect = side_effect

        self.backend.ensure_labels()

        created = [
            call.args[0]
            for call in mock_run.call_args_list
            if call.args[0][:3] == ["gh", "label", "create"]
        ]
        created_names = {cmd[5] for cmd in created}
        missing = {f"aet:{STATE_LABELS[s]}" for s in STATE_LABELS} - set(existing)
        self.assertEqual(created_names, missing)

    @mock.patch("backends.github_backend.subprocess.run")
    def test_missing_gh_cli_raises_clear_error(self, mock_run):
        mock_run.side_effect = FileNotFoundError("No such file or directory: 'gh'")

        with self.assertRaises(RuntimeError) as ctx:
            self.backend.ensure_labels()

        self.assertIn("gh auth login", str(ctx.exception))

    @mock.patch("backends.github_backend.subprocess.run")
    def test_failed_gh_command_raises_clear_error(self, mock_run):
        mock_run.return_value = _completed(
            returncode=1,
            stderr="HTTP 401: Bad credentials\n",
        )

        with self.assertRaises(RuntimeError) as ctx:
            self.backend.ensure_labels()

        self.assertIn("Bad credentials", str(ctx.exception))

    @mock.patch("backends.github_backend.subprocess.run")
    def test_on_transition_updates_issue_labels(self, mock_run):
        _write_queue(
            self.queue_file,
            [
                {
                    "id": "task",
                    "state": "in_progress",
                    "github_issue_number": 10,
                    "plan_file": "docs/plans/task.md",
                }
            ],
        )
        mock_run.side_effect = [
            _completed(stdout='{"labels": [{"name": "aet:ready"}]}'),
            _completed(stdout=""),
        ]

        self.backend.on_transition("task", "ready", "in_progress")

        edit_calls = [
            call.args[0]
            for call in mock_run.call_args_list
            if call.args[0][:3] == ["gh", "issue", "edit"]
        ]
        self.assertEqual(len(edit_calls), 1)
        self.assertIn("aet:in-progress", self._label_names_from_cmd(edit_calls[0]))

    @mock.patch("backends.github_backend.subprocess.run")
    def test_on_transition_skips_terminal_states(self, mock_run):
        _write_queue(
            self.queue_file,
            [
                {
                    "id": "task",
                    "state": "merged",
                    "github_issue_number": 10,
                    "plan_file": "docs/plans/task.md",
                }
            ],
        )

        self.backend.on_transition("task", "awaiting_merge", "merged")

        mock_run.assert_not_called()

    @mock.patch("backends.github_backend.subprocess.run")
    def test_close_task_closes_terminal_issue(self, mock_run):
        _write_queue(
            self.queue_file,
            [
                {
                    "id": "task",
                    "state": "merged",
                    "github_issue_number": 11,
                    "plan_file": "docs/plans/task.md",
                }
            ],
        )
        mock_run.return_value = _completed(stdout="")

        self.backend.close_task("task")

        close_calls = [
            call.args[0]
            for call in mock_run.call_args_list
            if call.args[0][:3] == ["gh", "issue", "close"]
        ]
        self.assertEqual(len(close_calls), 1)
        self.assertIn("11", close_calls[0])

    def test_close_task_is_noop_when_task_missing(self):
        _write_queue(self.queue_file, [])
        # Should not raise and should not call gh.
        self.backend.close_task("missing")


class TestFactoryGitHub(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_factory_creates_github_backend_when_configured(self):
        from backends.factory import create_backend
        from backends.github_backend import GitHubBackend

        config_path = Path(self.tmp.name) / "aet-work.json"
        config_path.write_text(
            json.dumps({"task_backend": "github", "github": {"repo": "owner/repo"}}),
            encoding="utf-8",
        )

        backend = create_backend(
            config_path=str(config_path),
            queue_file=str(Path(self.tmp.name) / "queue.json"),
            history_file=str(Path(self.tmp.name) / "history.jsonl"),
        )
        self.assertIsInstance(backend, GitHubBackend)
        self.assertEqual(backend.repo, "owner/repo")

    def test_factory_raises_when_github_repo_missing(self):
        from backends.factory import create_backend

        config_path = Path(self.tmp.name) / "aet-work.json"
        config_path.write_text(
            json.dumps({"task_backend": "github"}),
            encoding="utf-8",
        )

        with self.assertRaises(ValueError):
            create_backend(
                config_path=str(config_path),
                queue_file=str(Path(self.tmp.name) / "queue.json"),
                history_file=str(Path(self.tmp.name) / "history.jsonl"),
            )


if __name__ == "__main__":
    unittest.main()
