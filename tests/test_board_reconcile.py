"""Tests for the board reconcile command (R-17)."""

from __future__ import annotations

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


def _label_list_response() -> str:
    return json.dumps([{"name": f"aet:{suffix}"} for suffix in STATE_LABELS.values()])


def _issue_list_response(issues: list[dict]) -> str:
    return json.dumps(issues)


def _make_plan(
    plans_dir: Path,
    name: str,
    *,
    status: str = "approved",
    blocked_by: list[str] | None = None,
) -> Path:
    blocked_lines = "".join(f"  - {b}\n" for b in (blocked_by or []))
    body = f"""---
id: {Path(name).stem}
status: {status}
blocked_by:
{blocked_lines}---

# Plan: {name}

## Context

## Task List

1. Do something (traces: R-1).
"""
    path = plans_dir / name
    path.write_text(body, encoding="utf-8")
    return path


def _issue(number: int, plan_id: str, labels: list[str], state: str = "open") -> dict:
    return {
        "number": number,
        "labels": [{"name": name} for name in labels],
        "body": f"# Plan\n\n<!-- aet-id: {plan_id} -->",
        "state": state,
    }


class TestBoardReconcile(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.plans_dir = self.tmp_path / "docs" / "plans"
        self.plans_dir.mkdir(parents=True)
        self.queue_file = str(self.tmp_path / "work-queue.json")
        self.history_file = str(self.tmp_path / "work-history.jsonl")
        self.backend = GitHubBackend(
            repo="owner/repo",
            queue_file=self.queue_file,
            history_file=self.history_file,
            plans_dir=str(self.plans_dir),
        )
        Path(self.queue_file).write_text("[]", encoding="utf-8")
        Path(self.history_file).write_text("", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def _run_gh_calls(self, mock_run):
        """Return all gh argv lists issued during a test."""
        return [call.args[0] for call in mock_run.call_args_list]

    @mock.patch("backends.github_backend.subprocess.run")
    def test_dryrun_reports_missing_issues_and_mutates_nothing(self, mock_run):
        """A dry run prints missing drift and never creates or edits issues."""
        _make_plan(self.plans_dir, "feat-001.md", status="approved")

        def side_effect(cmd, **kwargs):
            if cmd[:3] == ["gh", "label", "list"]:
                return _completed(stdout=_label_list_response())
            if cmd[:3] == ["gh", "issue", "list"]:
                return _completed(stdout=_issue_list_response([]))
            if cmd[:3] == ["gh", "issue", "create"]:
                raise AssertionError("dry-run should not create issues")
            if cmd[:3] == ["gh", "issue", "edit"]:
                raise AssertionError("dry-run should not edit issues")
            raise AssertionError(f"unexpected command: {cmd}")

        mock_run.side_effect = side_effect

        report = self.backend.reconcile(apply=False)

        self.assertEqual(report["apply"], False)
        self.assertEqual(len(report["drift"]), 1)
        self.assertEqual(report["drift"][0]["type"], "missing")
        self.assertEqual(report["drift"][0]["plan_id"], "feat-001")
        self.assertEqual(report["drift"][0]["expected_label"], "aet:backlog")

    @mock.patch("backends.github_backend.subprocess.run")
    def test_apply_creates_missing_and_corrects_labels(self, mock_run):
        """--apply creates missing issues and relabels mislabeled ones."""
        _make_plan(self.plans_dir, "feat-001.md", status="approved")
        _make_plan(self.plans_dir, "feat-002.md", status="queued")

        existing_issues = [_issue(7, "feat-002", ["aet:draft"])]

        def side_effect(cmd, **kwargs):
            if cmd[:3] == ["gh", "label", "list"]:
                return _completed(stdout=_label_list_response())
            if cmd[:3] == ["gh", "issue", "list"]:
                return _completed(stdout=_issue_list_response(existing_issues))
            if cmd[:3] == ["gh", "issue", "create"]:
                return _completed(
                    stdout="https://github.com/owner/repo/issues/42\n"
                )
            if cmd[:3] == ["gh", "issue", "edit"]:
                return _completed(stdout="")
            raise AssertionError(f"unexpected command: {cmd}")

        mock_run.side_effect = side_effect

        report = self.backend.reconcile(apply=True)

        self.assertEqual(report["apply"], True)
        drift_types = {item["type"]: item for item in report["drift"]}
        self.assertIn("missing", drift_types)
        self.assertIn("mislabeled", drift_types)

        calls = self._run_gh_calls(mock_run)
        create_calls = [c for c in calls if c[:3] == ["gh", "issue", "create"]]
        edit_calls = [c for c in calls if c[:3] == ["gh", "issue", "edit"]]

        self.assertEqual(len(create_calls), 1)
        self.assertIn("aet:backlog", create_calls[0])

        self.assertEqual(len(edit_calls), 1)
        self.assertIn("aet:ready", edit_calls[0])
        self.assertIn("--remove-label", edit_calls[0])

    @mock.patch("backends.github_backend.subprocess.run")
    def test_reports_hand_closed_live_issue(self, mock_run):
        """A live plan whose issue was hand-closed is reported; --apply reopens it."""
        _make_plan(self.plans_dir, "feat-003.md", status="queued")
        existing_issues = [_issue(8, "feat-003", ["aet:ready"], state="closed")]

        def side_effect(cmd, **kwargs):
            if cmd[:3] == ["gh", "label", "list"]:
                return _completed(stdout=_label_list_response())
            if cmd[:3] == ["gh", "issue", "list"]:
                return _completed(stdout=_issue_list_response(existing_issues))
            if cmd[:3] == ["gh", "issue", "reopen"]:
                return _completed(stdout="")
            if cmd[:3] == ["gh", "issue", "edit"]:
                return _completed(stdout="")
            raise AssertionError(f"unexpected command: {cmd}")

        mock_run.side_effect = side_effect

        dry_report = self.backend.reconcile(apply=False)
        self.assertEqual(len(dry_report["drift"]), 1)
        self.assertEqual(dry_report["drift"][0]["type"], "closed-live")
        self.assertEqual(dry_report["drift"][0]["issue_number"], 8)
        reopen_before = [
            c for c in self._run_gh_calls(mock_run) if c[:3] == ["gh", "issue", "reopen"]
        ]
        self.assertEqual(len(reopen_before), 0)

        apply_report = self.backend.reconcile(apply=True)
        self.assertEqual(len(apply_report["drift"]), 1)
        calls = self._run_gh_calls(mock_run)
        reopen_calls = [c for c in calls if c[:3] == ["gh", "issue", "reopen"]]
        self.assertEqual(len(reopen_calls), 1)
        self.assertIn("8", reopen_calls[0])

    @mock.patch("backends.github_backend.subprocess.run")
    def test_orphan_issue_reported_not_deleted(self, mock_run):
        """An issue for a non-live plan is reported and never deleted."""
        _make_plan(self.plans_dir, "feat-004.md", status="merged")
        existing_issues = [_issue(9, "feat-099", ["aet:backlog"])]

        def side_effect(cmd, **kwargs):
            if cmd[:3] == ["gh", "label", "list"]:
                return _completed(stdout=_label_list_response())
            if cmd[:3] == ["gh", "issue", "list"]:
                return _completed(stdout=_issue_list_response(existing_issues))
            if cmd[:3] == ["gh", "issue", "close"]:
                raise AssertionError("orphan issues must not be auto-deleted")
            raise AssertionError(f"unexpected command: {cmd}")

        mock_run.side_effect = side_effect

        report = self.backend.reconcile(apply=True)

        self.assertEqual(len(report["drift"]), 1)
        self.assertEqual(report["drift"][0]["type"], "orphan")
        self.assertEqual(report["drift"][0]["plan_id"], "feat-099")

    @mock.patch("backends.github_backend.subprocess.run")
    def test_second_apply_is_empty(self, mock_run):
        """After a successful --apply, the next reconcile reports no drift."""
        _make_plan(self.plans_dir, "feat-005.md", status="approved")

        existing_issues: list[dict] = []

        def side_effect(cmd, **kwargs):
            if cmd[:3] == ["gh", "label", "list"]:
                return _completed(stdout=_label_list_response())
            if cmd[:3] == ["gh", "issue", "list"]:
                return _completed(stdout=_issue_list_response(existing_issues))
            if cmd[:3] == ["gh", "issue", "create"]:
                existing_issues.append(_issue(10, "feat-005", ["aet:backlog"]))
                return _completed(
                    stdout="https://github.com/owner/repo/issues/10\n"
                )
            if cmd[:3] == ["gh", "issue", "edit"]:
                return _completed(stdout="")
            raise AssertionError(f"unexpected command: {cmd}")

        mock_run.side_effect = side_effect

        first = self.backend.reconcile(apply=True)
        self.assertEqual(len(first["drift"]), 1)

        second = self.backend.reconcile(apply=True)
        self.assertEqual(second["drift"], [])


if __name__ == "__main__":
    unittest.main()
