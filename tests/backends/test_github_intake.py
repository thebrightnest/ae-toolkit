"""Tests for the GitHubBackend sprint-intake read path (R-13, R-14)."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from aet.backends.github_backend import BackendError, GitHubBackend


def _completed(stdout: str = "", returncode: int = 0, stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=["gh"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def _label_list_response(labels: list[str]) -> str:
    return json.dumps([{"name": name} for name in labels])


class TestFindSprintCandidates(unittest.TestCase):
    """GitHubBackend can enumerate aet:sprint issues and extract task ids."""

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

    @mock.patch("aet.backends.github_backend.subprocess.run")
    def test_find_candidates_returns_task_ids(self, mock_run):
        labels = [
            f"aet:{s}"
            for s in (
                "planned",
                "ready",
                "blocked",
                "in-progress",
                "awaiting-merge",
                "merged",
                "abandoned",
                "failed",
                "quarantined",
                "draft",
                "backlog",
                "sprint",
            )
        ]

        def side_effect(cmd, **kwargs):
            if cmd[:3] == ["gh", "label", "list"]:
                return _completed(stdout=_label_list_response(labels))
            if cmd[:3] == ["gh", "issue", "list"]:
                return _completed(
                    stdout=json.dumps(
                        [
                            {
                                "number": 7,
                                "body": "<!-- aet-id: feat-001 -->\nPlan file: docs/plans/feat-001.md",
                                "labels": [{"name": "aet:sprint"}],
                                "state": "open",
                            }
                        ]
                    )
                )
            raise AssertionError(f"unexpected command: {cmd}")

        mock_run.side_effect = side_effect

        candidates = self.backend.find_sprint_candidates()

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["task_id"], "feat-001")
        self.assertEqual(candidates[0]["issue_number"], 7)

    @mock.patch("aet.backends.github_backend.subprocess.run")
    def test_find_candidates_ignores_issues_without_marker(self, mock_run):
        labels = [
            f"aet:{s}"
            for s in (
                "planned",
                "ready",
                "blocked",
                "in-progress",
                "awaiting-merge",
                "merged",
                "abandoned",
                "failed",
                "quarantined",
                "draft",
                "backlog",
                "sprint",
            )
        ]

        def side_effect(cmd, **kwargs):
            if cmd[:3] == ["gh", "label", "list"]:
                return _completed(stdout=_label_list_response(labels))
            if cmd[:3] == ["gh", "issue", "list"]:
                return _completed(
                    stdout=json.dumps(
                        [
                            {
                                "number": 8,
                                "body": "No marker here",
                                "labels": [{"name": "aet:sprint"}],
                                "state": "open",
                            }
                        ]
                    )
                )
            raise AssertionError(f"unexpected command: {cmd}")

        mock_run.side_effect = side_effect

        candidates = self.backend.find_sprint_candidates()

        self.assertEqual(candidates, [])


class TestRunGhWithRetry(unittest.TestCase):
    """Transient forge failures are retried with backoff; permanent ones are not."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.backend = GitHubBackend(
            repo="owner/repo",
            queue_file=str(Path(self.tmp.name) / "work-queue.json"),
            history_file=str(Path(self.tmp.name) / "work-history.jsonl"),
        )

    def tearDown(self):
        self.tmp.cleanup()

    @mock.patch("aet.backends.github_backend.subprocess.run")
    def test_retry_exhausts_then_raises(self, mock_run):
        mock_run.return_value = _completed(
            returncode=1, stderr="HTTP 403: Forbidden\n"
        )

        with self.assertRaises(BackendError):
            self.backend._run_gh_with_retry(["issue", "list"], max_retries=2, base_delay=0.01)

        self.assertEqual(mock_run.call_count, 2)

    @mock.patch("aet.backends.github_backend.subprocess.run")
    def test_success_after_retry(self, mock_run):
        mock_run.side_effect = [
            _completed(returncode=1, stderr="HTTP 502: Bad Gateway\n"),
            _completed(returncode=1, stderr="HTTP 503: Service Unavailable\n"),
            _completed(stdout="[]"),
        ]

        result = self.backend._run_gh_with_retry(["issue", "list"], max_retries=3, base_delay=0.01)

        self.assertEqual(result.stdout, "[]")
        self.assertEqual(mock_run.call_count, 3)

    @mock.patch("aet.backends.github_backend.subprocess.run")
    def test_non_transient_error_does_not_retry(self, mock_run):
        mock_run.return_value = _completed(
            returncode=1, stderr="HTTP 422: Unprocessable Entity\n"
        )

        with self.assertRaises(BackendError):
            self.backend._run_gh_with_retry(["issue", "list"], max_retries=3, base_delay=0.01)

        self.assertEqual(mock_run.call_count, 1)


if __name__ == "__main__":
    unittest.main()
