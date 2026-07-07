"""Tests for the GitHub Issues task backend."""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "aet-work" / "lib"))

from backends.github_backend import GitHubBackend, STATE_LABELS


def _completed(stdout: str = "", returncode: int = 0, stderr: str = ""):
    return subprocess.CompletedProcess(
        args=["gh"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def _label_list_response(labels: list[str]) -> str:
    return json.dumps([{"name": name} for name in labels])


def _issue(
    number: int,
    title: str,
    labels: list[str],
    body: str,
    url: str = "https://github.com/owner/repo/issues/1",
) -> dict:
    return {
        "number": number,
        "title": title,
        "labels": [{"name": name} for name in labels],
        "body": body,
        "url": url,
    }


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

    @mock.patch("backends.github_backend.subprocess.run")
    def test_load_returns_empty_when_no_issues(self, mock_run):
        def side_effect(cmd, **kwargs):
            if cmd[:3] == ["gh", "label", "list"]:
                return _completed(stdout=_label_list_response([f"aet:{s}" for s in STATE_LABELS.values()]))
            if cmd[:3] == ["gh", "issue", "list"]:
                return _completed(stdout="[]")
            raise AssertionError(f"unexpected command: {cmd}")

        mock_run.side_effect = side_effect

        data = self.backend.load()
        self.assertEqual(data["queue"], [])
        self.assertEqual(data["history"], [])

    @mock.patch("backends.github_backend.subprocess.run")
    def test_load_maps_open_issues_with_aet_labels(self, mock_run):
        def side_effect(cmd, **kwargs):
            if cmd[:3] == ["gh", "label", "list"]:
                return _completed(stdout=_label_list_response([f"aet:{s}" for s in STATE_LABELS.values()]))
            if cmd[:3] == ["gh", "issue", "list"]:
                issue = _issue(
                    number=42,
                    title="GitHub adapter",
                    labels=["aet:ready"],
                    body="<!-- plan-file: docs/plans/ght-02-github-adapter.md -->\n\nDo the work.",
                )
                return _completed(stdout=json.dumps([issue]))
            raise AssertionError(f"unexpected command: {cmd}")

        mock_run.side_effect = side_effect

        data = self.backend.load()
        self.assertEqual(len(data["queue"]), 1)
        task = data["queue"][0]
        self.assertEqual(task["id"], "ght-02-github-adapter")
        self.assertEqual(task["title"], "GitHub adapter")
        self.assertEqual(task["state"], "ready")
        self.assertEqual(task["plan_file"], "docs/plans/ght-02-github-adapter.md")
        self.assertEqual(task["issue_number"], 42)

    @mock.patch("backends.github_backend.subprocess.run")
    def test_load_defaults_to_planned_without_aet_label(self, mock_run):
        def side_effect(cmd, **kwargs):
            if cmd[:3] == ["gh", "label", "list"]:
                return _completed(stdout=_label_list_response([f"aet:{s}" for s in STATE_LABELS.values()]))
            if cmd[:3] == ["gh", "issue", "list"]:
                issue = _issue(
                    number=7,
                    title="Untracked",
                    labels=["bug"],
                    body="<!-- plan-file: docs/plans/untracked.md -->",
                )
                return _completed(stdout=json.dumps([issue]))
            raise AssertionError(f"unexpected command: {cmd}")

        mock_run.side_effect = side_effect

        data = self.backend.load()
        self.assertEqual(len(data["queue"]), 0)

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
    def test_transition_updates_issue_labels(self, mock_run):
        issue = _issue(
            number=10,
            title="Task",
            labels=["aet:ready"],
            body="<!-- plan-file: docs/plans/task.md -->",
        )

        def side_effect(cmd, **kwargs):
            if cmd[:3] == ["gh", "label", "list"]:
                return _completed(stdout=_label_list_response([f"aet:{s}" for s in STATE_LABELS.values()]))
            if cmd[:3] == ["gh", "issue", "list"]:
                return _completed(stdout=json.dumps([issue]))
            if cmd[:3] == ["gh", "issue", "edit"]:
                return _completed(stdout="")
            raise AssertionError(f"unexpected command: {cmd}")

        mock_run.side_effect = side_effect

        result = self.backend.transition("task", "ready", "in_progress")
        self.assertTrue(result)

        edit_calls = [
            call.args[0]
            for call in mock_run.call_args_list
            if call.args[0][:3] == ["gh", "issue", "edit"]
        ]
        self.assertEqual(len(edit_calls), 1)
        self.assertIn("10", edit_calls[0])
        self.assertIn("aet:in-progress", self._label_names_from_cmd(edit_calls[0]))

    @mock.patch("backends.github_backend.subprocess.run")
    def test_transition_closes_terminal_issue_and_seals_history(self, mock_run):
        issue = _issue(
            number=11,
            title="Task",
            labels=["aet:awaiting-merge"],
            body="<!-- plan-file: docs/plans/task.md -->",
        )

        def side_effect(cmd, **kwargs):
            if cmd[:3] == ["gh", "label", "list"]:
                return _completed(stdout=_label_list_response([f"aet:{s}" for s in STATE_LABELS.values()]))
            if cmd[:3] == ["gh", "issue", "list"]:
                return _completed(stdout=json.dumps([issue]))
            if cmd[:3] == ["gh", "issue", "close"]:
                return _completed(stdout="")
            raise AssertionError(f"unexpected command: {cmd}")

        mock_run.side_effect = side_effect

        result = self.backend.transition("task", "awaiting_merge", "merged")
        self.assertTrue(result)

        close_calls = [
            call.args[0]
            for call in mock_run.call_args_list
            if call.args[0][:3] == ["gh", "issue", "close"]
        ]
        self.assertEqual(len(close_calls), 1)
        self.assertIn("11", close_calls[0])

        history = Path(self.history_file).read_text(encoding="utf-8").strip()
        self.assertIn("task", history)

    @mock.patch("backends.github_backend.subprocess.run")
    def test_transition_returns_false_when_task_not_found(self, mock_run):
        def side_effect(cmd, **kwargs):
            if cmd[:3] == ["gh", "label", "list"]:
                return _completed(stdout=_label_list_response([f"aet:{s}" for s in STATE_LABELS.values()]))
            if cmd[:3] == ["gh", "issue", "list"]:
                return _completed(stdout="[]")
            raise AssertionError(f"unexpected command: {cmd}")

        mock_run.side_effect = side_effect

        self.assertFalse(self.backend.transition("missing", "ready", "in_progress"))

    @mock.patch("backends.github_backend.subprocess.run")
    def test_save_creates_issue_for_new_task(self, mock_run):
        def side_effect(cmd, **kwargs):
            if cmd[:3] == ["gh", "label", "list"]:
                return _completed(stdout=_label_list_response([f"aet:{s}" for s in STATE_LABELS.values()]))
            if cmd[:3] == ["gh", "issue", "create"]:
                return _completed(stdout=json.dumps({"number": 99, "url": "https://github.com/owner/repo/issues/99"}))
            raise AssertionError(f"unexpected command: {cmd}")

        mock_run.side_effect = side_effect

        task = {
            "id": "new-task",
            "title": "New task",
            "state": "ready",
            "plan_file": "docs/plans/new-task.md",
        }
        self.backend.save([task])

        self.assertEqual(task["issue_number"], 99)
        create_calls = [
            call.args[0]
            for call in mock_run.call_args_list
            if call.args[0][:3] == ["gh", "issue", "create"]
        ]
        self.assertEqual(len(create_calls), 1)
        self.assertIn("--label", create_calls[0])
        self.assertIn("aet:ready", create_calls[0])

    @mock.patch("backends.github_backend.subprocess.run")
    def test_save_updates_labels_for_existing_task(self, mock_run):
        def side_effect(cmd, **kwargs):
            if cmd[:3] == ["gh", "label", "list"]:
                return _completed(stdout=_label_list_response([f"aet:{s}" for s in STATE_LABELS.values()]))
            if cmd[:3] == ["gh", "issue", "edit"]:
                return _completed(stdout="")
            raise AssertionError(f"unexpected command: {cmd}")

        mock_run.side_effect = side_effect

        task = {
            "id": "existing",
            "title": "Existing",
            "state": "blocked",
            "issue_number": 5,
        }
        self.backend.save([task])

        edit_calls = [
            call.args[0]
            for call in mock_run.call_args_list
            if call.args[0][:3] == ["gh", "issue", "edit"]
        ]
        self.assertEqual(len(edit_calls), 1)
        self.assertIn("5", edit_calls[0])
        self.assertIn("aet:blocked", self._label_names_from_cmd(edit_calls[0]))

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
