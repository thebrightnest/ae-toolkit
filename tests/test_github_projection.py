"""Tests for the GitHub Issues projection."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.parent / "aet-work" / "lib"))

from aet_queue import STATES
from backends.github_backend import STATE_LABELS, BackendError, GitHubBackend
from projections.base import Projection


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


class TestGitHubProjection(unittest.TestCase):
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

    def _aet_labels_from_cmd(self, cmd: list[str]) -> set[str]:
        """Return aet:* labels added or removed by an issue edit command."""
        names = set()
        for i, arg in enumerate(cmd):
            if arg in ("--add-label", "--remove-label") and i + 1 < len(cmd):
                names.add(cmd[i + 1])
        return names

    def _issued_label(self, cmd: list[str]) -> str:
        """Return the label applied to a newly created issue."""
        return cmd[cmd.index("--label") + 1]

    def test_backend_is_projection(self):
        self.assertTrue(issubclass(GitHubBackend, Projection))

    def test_state_labels_cover_all_states(self):
        """Every AET state plus draft/backlog has a GitHub label."""
        expected = STATES | {"draft", "backlog"}
        self.assertEqual(set(STATE_LABELS), expected)

    @mock.patch("backends.github_backend.subprocess.run")
    def test_create_issue_embeds_plan_id_marker(self, mock_run):
        def side_effect(cmd, **kwargs):
            if cmd[:3] == ["gh", "label", "list"]:
                return _completed(
                    stdout=_label_list_response(
                        [f"aet:{STATE_LABELS[s]}" for s in STATE_LABELS]
                    )
                )
            if cmd[:3] == ["gh", "issue", "create"]:
                return _completed(
                    stdout="https://github.com/owner/repo/issues/42\n"
                )
            raise AssertionError(f"unexpected command: {cmd}")

        mock_run.side_effect = side_effect
        task = {
            "id": "feat-001",
            "title": "First task",
            "status": "draft",
            "state": "planned",
            "plan_file": "docs/plans/feat-001.md",
        }

        self.backend.on_add(task, is_new=True)

        create_calls = [
            call.args[0]
            for call in mock_run.call_args_list
            if call.args[0][:3] == ["gh", "issue", "create"]
        ]
        self.assertEqual(len(create_calls), 1)
        create_call = create_calls[0]
        body = create_call[create_call.index("--body") + 1]
        self.assertIn("<!-- aet-id: feat-001 -->", body)
        self.assertIn("aet:draft", create_call)

    @mock.patch("backends.github_backend.subprocess.run")
    def test_issue_identity_is_plan_id_not_title(self, mock_run):
        """A refreshed task is matched by the aet-id marker, not by title."""

        def side_effect(cmd, **kwargs):
            if cmd[:3] == ["gh", "label", "list"]:
                return _completed(
                    stdout=_label_list_response(
                        [f"aet:{STATE_LABELS[s]}" for s in STATE_LABELS]
                    )
                )
            if cmd[:3] == ["gh", "issue", "list"]:
                return _completed(
                    stdout=json.dumps(
                        [
                            {
                                "number": 7,
                                "body": "<!-- aet-id: feat-001 -->",
                                "title": "Old title",
                            }
                        ]
                    )
                )
            if cmd[:3] == ["gh", "issue", "view"]:
                return _completed(
                    stdout='{"labels": [{"name": "aet:draft"}]}'
                )
            if cmd[:3] == ["gh", "issue", "edit"]:
                return _completed(stdout="")
            raise AssertionError(f"unexpected command: {cmd}")

        mock_run.side_effect = side_effect

        task = {
            "id": "feat-001",
            "title": "Renamed task",
            "state": "ready",
            "plan_file": "docs/plans/feat-001.md",
        }

        self.backend.on_add(task, is_new=False)

        list_calls = [
            call.args[0]
            for call in mock_run.call_args_list
            if call.args[0][:3] == ["gh", "issue", "list"]
        ]
        self.assertEqual(len(list_calls), 1)
        self.assertIn("--json", list_calls[0])
        self.assertTrue(
            any("body" in arg for arg in list_calls[0]),
            "issue list should fetch the issue body",
        )

        edit_calls = [
            call.args[0]
            for call in mock_run.call_args_list
            if call.args[0][:3] == ["gh", "issue", "edit"]
        ]
        self.assertEqual(len(edit_calls), 1)
        self.assertIn("7", edit_calls[0])
        self.assertEqual(task["github_issue_number"], 7)

    @mock.patch("backends.github_backend.subprocess.run")
    def test_ensure_labels_runs_on_first_use(self, mock_run):
        existing = ["aet:ready"]
        created = []

        def side_effect(cmd, **kwargs):
            if cmd[:3] == ["gh", "label", "list"]:
                return _completed(stdout=_label_list_response(existing))
            if cmd[:3] == ["gh", "label", "create"]:
                created.append(cmd)
                return _completed(stdout="")
            if cmd[:3] == ["gh", "issue", "create"]:
                return _completed(
                    stdout="https://github.com/owner/repo/issues/42\n"
                )
            raise AssertionError(f"unexpected command: {cmd}")

        mock_run.side_effect = side_effect

        task = {
            "id": "feat-001",
            "title": "First task",
            "status": "draft",
            "state": "planned",
            "plan_file": "docs/plans/feat-001.md",
        }

        self.backend.on_add(task, is_new=True)

        self.assertTrue(created, "ensure_labels should create missing labels")
        self.assertEqual(mock_run.call_args_list[0].args[0][:3], ["gh", "label", "list"])
        created_names = {cmd[5] for cmd in created}
        missing = {f"aet:{STATE_LABELS[s]}" for s in STATE_LABELS}
        self.assertEqual(created_names, missing - set(existing))

    @mock.patch("backends.github_backend.subprocess.run")
    def test_draft_and_backlog_labels_from_plan_status(self, mock_run):
        """Backlog add labels issues by plan status, not queue state."""

        def side_effect(cmd, **kwargs):
            if cmd[:3] == ["gh", "label", "list"]:
                return _completed(
                    stdout=_label_list_response(
                        [f"aet:{STATE_LABELS[s]}" for s in STATE_LABELS]
                    )
                )
            if cmd[:3] == ["gh", "issue", "create"]:
                return _completed(
                    stdout="https://github.com/owner/repo/issues/42\n"
                )
            raise AssertionError(f"unexpected command: {cmd}")

        mock_run.side_effect = side_effect

        for status, expected_label in (("draft", "aet:draft"), ("approved", "aet:backlog")):
            with self.subTest(status=status):
                mock_run.reset_mock()
                self.backend._labels_ensured = False
                task = {
                    "id": f"feat-{status}",
                    "title": f"{status} task",
                    "status": status,
                    "state": "planned",
                    "plan_file": f"docs/plans/feat-{status}.md",
                }

                self.backend.on_add(task, is_new=True)

                create_call = mock_run.call_args[0][0]
                self.assertEqual(self._issued_label(create_call), expected_label)

    @mock.patch("backends.github_backend.subprocess.run")
    def test_transition_relabels_and_removes_prior(self, mock_run):
        _write_queue(
            self.queue_file,
            [
                {
                    "id": "task",
                    "state": "in_progress",
                    "status": "queued",
                    "github_issue_number": 10,
                    "plan_file": "docs/plans/task.md",
                }
            ],
        )

        def side_effect(cmd, **kwargs):
            if cmd[:3] == ["gh", "label", "list"]:
                return _completed(
                    stdout=_label_list_response(
                        [f"aet:{STATE_LABELS[s]}" for s in STATE_LABELS]
                    )
                )
            if cmd[:3] == ["gh", "issue", "view"]:
                return _completed(
                    stdout='{"labels": [{"name": "aet:ready"}]}'
                )
            if cmd[:3] == ["gh", "issue", "edit"]:
                return _completed(stdout="")
            raise AssertionError(f"unexpected command: {cmd}")

        mock_run.side_effect = side_effect

        self.backend.on_transition("task", "ready", "in_progress")

        edit_calls = [
            call.args[0]
            for call in mock_run.call_args_list
            if call.args[0][:3] == ["gh", "issue", "edit"]
        ]
        self.assertEqual(len(edit_calls), 1)
        labels = self._aet_labels_from_cmd(edit_calls[0])
        self.assertIn("aet:in-progress", labels)
        self.assertIn("aet:ready", labels)

    @mock.patch("backends.github_backend.subprocess.run")
    def test_terminal_closes_issue(self, mock_run):
        _write_queue(
            self.queue_file,
            [
                {
                    "id": "task",
                    "state": "merged",
                    "status": "queued",
                    "github_issue_number": 11,
                    "plan_file": "docs/plans/task.md",
                }
            ],
        )

        def side_effect(cmd, **kwargs):
            if cmd[:3] == ["gh", "label", "list"]:
                return _completed(
                    stdout=_label_list_response(
                        [f"aet:{STATE_LABELS[s]}" for s in STATE_LABELS]
                    )
                )
            if cmd[:3] == ["gh", "issue", "close"]:
                return _completed(stdout="")
            raise AssertionError(f"unexpected command: {cmd}")

        mock_run.side_effect = side_effect

        self.backend.on_close("task")

        close_calls = [
            call.args[0]
            for call in mock_run.call_args_list
            if call.args[0][:3] == ["gh", "issue", "close"]
        ]
        self.assertEqual(len(close_calls), 1)
        self.assertIn("11", close_calls[0])

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
    def test_missing_gh_cli_raises_clear_error(self, mock_run):
        mock_run.side_effect = FileNotFoundError("No such file or directory: 'gh'")

        with self.assertRaises(BackendError) as ctx:
            self.backend.ensure_labels()

        self.assertIn("gh auth login", str(ctx.exception))

    @mock.patch("backends.github_backend.subprocess.run")
    def test_failed_gh_command_raises_clear_error(self, mock_run):
        mock_run.return_value = _completed(
            returncode=1,
            stderr="HTTP 401: Bad credentials\n",
        )

        with self.assertRaises(BackendError) as ctx:
            self.backend.ensure_labels()

        self.assertIn("Bad credentials", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
