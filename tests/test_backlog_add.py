"""Tests for the `aet backlog add` command (R-10, R-13)."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.parent / "aet-work" / "lib"))

from backends.github_backend import GitHubBackend

_REPO_ROOT = Path(__file__).parent.parent
_BACKLOG_PY = _REPO_ROOT / "aet-work" / "bin" / "backlog"

_backlog_spec = importlib.util.spec_from_loader(
    "backlog", importlib.machinery.SourceFileLoader("backlog", str(_BACKLOG_PY))
)
backlog = importlib.util.module_from_spec(_backlog_spec)
_backlog_spec.loader.exec_module(backlog)


def _completed(stdout: str = "", returncode: int = 0, stderr: str = ""):
    return subprocess.CompletedProcess(
        args=["gh"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def _label_list_response() -> str:
    from backends.github_backend import STATE_LABELS

    return json.dumps([{"name": f"aet:{suffix}"} for suffix in STATE_LABELS.values()])


def _issue(number: int, plan_id: str, labels: list[str], state: str = "open") -> dict:
    return {
        "number": number,
        "labels": [{"name": name} for name in labels],
        "body": f"# Plan\n\n<!-- aet-id: {plan_id} -->",
        "state": state,
    }


def _git(args: list[str], cwd: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, capture_output=True, check=True)


def _make_plan(
    plans_dir: Path,
    name: str,
    *,
    status: str,
) -> Path:
    path = plans_dir / name
    body = f"""---
id: {Path(name).stem}
size: M
status: {status}
---

# Plan: {name}

## Context

PRD: docs/prds/default-prd.md

## Task List

1. Implement the thing (traces: R-10).

## Files to Modify

- `src/thing.py`

## Validation Steps

- [ ] test_thing verifies thing.py

---

_Stage: plan-approved_
_Next step: run `aet-backlog-add`_
"""
    path.write_text(body, encoding="utf-8")
    return path


def _make_config(project_dir: Path) -> Path:
    config_path = project_dir / ".agents" / "aet-work.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(
            {
                "task_backend": "json",
                "projections": [
                    {"type": "github", "repo": "owner/repo", "label_prefix": "aet"}
                ],
            }
        ),
        encoding="utf-8",
    )
    return config_path


class TestBacklogAdd(unittest.TestCase):
    def _run_backlog_add(self, cwd: str, target: str, config_path: Path, plans_dir: Path):
        """Run the backlog add command and return its exit code."""
        return backlog.main(
            [
                "add",
                target,
                "--config",
                str(config_path),
                "--plans-dir",
                str(plans_dir),
            ]
        )

    def test_backlog_add_unknown_plan_id_fails_closed(self):
        """Backlog add exits non-zero when the plan file or task ID is unknown."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            plans_dir = tmp_path / "docs" / "plans"
            plans_dir.mkdir(parents=True)
            config_path = _make_config(tmp_path)

            stderr = io.StringIO()
            with mock.patch.object(sys, "stderr", stderr):
                rc = self._run_backlog_add(tmp, "nonexistent", config_path, plans_dir)

            self.assertEqual(rc, 1)
            self.assertIn("No plan found", stderr.getvalue())

    def test_backlog_add_draft_plan_labels_aet_draft(self):
        """A draft plan is boarded with the aet:draft label."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _git(["init"], tmp)
            _git(["config", "user.email", "test@example.com"], tmp)
            _git(["config", "user.name", "Test"], tmp)

            plans_dir = tmp_path / "docs" / "plans"
            plans_dir.mkdir(parents=True)
            plan = _make_plan(plans_dir, "feat-001.md", status="draft")
            _git(["add", "-A"], tmp)
            _git(["commit", "-m", "initial"], tmp)

            config_path = _make_config(tmp_path)

            with mock.patch.object(
                GitHubBackend, "_run_gh", autospec=True
            ) as mock_run:

                def side_effect(self, args):
                    if args[:3] == ["label", "list", "--repo"]:
                        return _completed(stdout=_label_list_response())
                    if args[:3] == ["issue", "list", "--repo"]:
                        return _completed(stdout=json.dumps([]))
                    if args[:3] == ["issue", "create", "--repo"]:
                        return _completed(
                            stdout="https://github.com/owner/repo/issues/42\n"
                        )
                    raise AssertionError(f"unexpected command: {args}")

                mock_run.side_effect = side_effect
                rc = self._run_backlog_add(tmp, str(plan), config_path, plans_dir)

            self.assertEqual(rc, 0)

            plan_text = plan.read_text(encoding="utf-8")
            self.assertIn("status: draft", plan_text)
            self.assertIn("_Stage: plan-approved_", plan_text)

            create_calls = [
                call.args[1]
                for call in mock_run.call_args_list
                if call.args[1][:3] == ["issue", "create", "--repo"]
            ]
            self.assertEqual(len(create_calls), 1)
            self.assertIn("aet:draft", create_calls[0])

    def test_backlog_add_approved_plan_labels_aet_backlog(self):
        """An approved plan is boarded with the aet:backlog label."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _git(["init"], tmp)
            _git(["config", "user.email", "test@example.com"], tmp)
            _git(["config", "user.name", "Test"], tmp)

            plans_dir = tmp_path / "docs" / "plans"
            plans_dir.mkdir(parents=True)
            plan = _make_plan(plans_dir, "feat-002.md", status="approved")
            _git(["add", "-A"], tmp)
            _git(["commit", "-m", "initial"], tmp)

            config_path = _make_config(tmp_path)

            with mock.patch.object(
                GitHubBackend, "_run_gh", autospec=True
            ) as mock_run:

                def side_effect(self, args):
                    if args[:3] == ["label", "list", "--repo"]:
                        return _completed(stdout=_label_list_response())
                    if args[:3] == ["issue", "list", "--repo"]:
                        return _completed(stdout=json.dumps([]))
                    if args[:3] == ["issue", "create", "--repo"]:
                        return _completed(
                            stdout="https://github.com/owner/repo/issues/43\n"
                        )
                    raise AssertionError(f"unexpected command: {args}")

                mock_run.side_effect = side_effect
                rc = self._run_backlog_add(tmp, str(plan), config_path, plans_dir)

            self.assertEqual(rc, 0)

            create_calls = [
                call.args[1]
                for call in mock_run.call_args_list
                if call.args[1][:3] == ["issue", "create", "--repo"]
            ]
            self.assertEqual(len(create_calls), 1)
            self.assertIn("aet:backlog", create_calls[0])

    def test_backlog_add_twice_creates_no_duplicate(self):
        """Re-running backlog add finds the existing issue by plan id."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _git(["init"], tmp)
            _git(["config", "user.email", "test@example.com"], tmp)
            _git(["config", "user.name", "Test"], tmp)

            plans_dir = tmp_path / "docs" / "plans"
            plans_dir.mkdir(parents=True)
            plan = _make_plan(plans_dir, "feat-003.md", status="draft")
            _git(["add", "-A"], tmp)
            _git(["commit", "-m", "initial"], tmp)

            config_path = _make_config(tmp_path)

            existing_issues: list[dict] = []

            with mock.patch.object(
                GitHubBackend, "_run_gh", autospec=True
            ) as mock_run:

                def side_effect(self, args):
                    if args[:3] == ["label", "list", "--repo"]:
                        return _completed(stdout=_label_list_response())
                    if args[:3] == ["issue", "list", "--repo"]:
                        return _completed(stdout=json.dumps(existing_issues))
                    if args[:3] == ["issue", "create", "--repo"]:
                        existing_issues.append(_issue(44, "feat-003", ["aet:draft"]))
                        return _completed(
                            stdout="https://github.com/owner/repo/issues/44\n"
                        )
                    if args[:2] == ["issue", "view"]:
                        return _completed(
                            stdout=json.dumps({"labels": [{"name": "aet:draft"}]})
                        )
                    if args[:2] == ["issue", "edit"]:
                        return _completed(stdout="")
                    raise AssertionError(f"unexpected command: {args}")

                mock_run.side_effect = side_effect

                rc1 = self._run_backlog_add(tmp, str(plan), config_path, plans_dir)
                self.assertEqual(rc1, 0)

                rc2 = self._run_backlog_add(tmp, str(plan), config_path, plans_dir)
                self.assertEqual(rc2, 0)

            create_calls = [
                call.args[1]
                for call in mock_run.call_args_list
                if call.args[1][:3] == ["issue", "create", "--repo"]
            ]
            self.assertEqual(len(create_calls), 1)

    def test_backlog_add_second_clone_finds_existing_issue(self):
        """A fresh clone with an existing issue on GitHub reconciles labels only."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _git(["init"], tmp)
            _git(["config", "user.email", "test@example.com"], tmp)
            _git(["config", "user.name", "Test"], tmp)

            plans_dir = tmp_path / "docs" / "plans"
            plans_dir.mkdir(parents=True)
            plan = _make_plan(plans_dir, "feat-004.md", status="draft")
            _git(["add", "-A"], tmp)
            _git(["commit", "-m", "initial"], tmp)

            config_path = _make_config(tmp_path)
            existing_issues = [_issue(45, "feat-004", ["aet:backlog"])]

            with mock.patch.object(
                GitHubBackend, "_run_gh", autospec=True
            ) as mock_run:

                def side_effect(self, args):
                    if args[:3] == ["label", "list", "--repo"]:
                        return _completed(stdout=_label_list_response())
                    if args[:3] == ["issue", "list", "--repo"]:
                        return _completed(stdout=json.dumps(existing_issues))
                    if args[:3] == ["issue", "create", "--repo"]:
                        raise AssertionError(
                            "second clone must not create a duplicate issue"
                        )
                    if args[:2] == ["issue", "view"]:
                        return _completed(
                            stdout=json.dumps({"labels": [{"name": "aet:backlog"}]})
                        )
                    if args[:2] == ["issue", "edit"]:
                        return _completed(stdout="")
                    raise AssertionError(f"unexpected command: {args}")

                mock_run.side_effect = side_effect
                rc = self._run_backlog_add(tmp, str(plan), config_path, plans_dir)

            self.assertEqual(rc, 0)

            create_calls = [
                call.args[1]
                for call in mock_run.call_args_list
                if call.args[1][:3] == ["issue", "create", "--repo"]
            ]
            self.assertEqual(len(create_calls), 0)

            edit_calls = [
                call.args[1]
                for call in mock_run.call_args_list
                if call.args[1][:2] == ["issue", "edit"]
            ]
            self.assertEqual(len(edit_calls), 1)
            self.assertIn("aet:draft", edit_calls[0])
            self.assertIn("aet:backlog", edit_calls[0])

    def test_backlog_add_succeeds_and_warns_when_projection_unavailable(self):
        """A projection failure warns but does not fail the commit."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _git(["init"], tmp)
            _git(["config", "user.email", "test@example.com"], tmp)
            _git(["config", "user.name", "Test"], tmp)

            plans_dir = tmp_path / "docs" / "plans"
            plans_dir.mkdir(parents=True)
            plan = _make_plan(plans_dir, "feat-005.md", status="draft")
            _git(["add", "-A"], tmp)
            _git(["commit", "-m", "initial"], tmp)

            config_path = _make_config(tmp_path)

            stderr = io.StringIO()
            with mock.patch.object(sys, "stderr", stderr):
                with mock.patch.object(
                    GitHubBackend, "_run_gh", autospec=True
                ) as mock_run:
                    mock_run.side_effect = Exception("gh not found")
                    rc = self._run_backlog_add(
                        tmp, str(plan), config_path, plans_dir
                    )

            self.assertEqual(rc, 0)
            self.assertIn("warning:", stderr.getvalue())
            self.assertIn("GitHubBackend", stderr.getvalue())

            plan_text = plan.read_text(encoding="utf-8")
            self.assertIn("status: draft", plan_text)
            self.assertIn("_Stage: plan-approved_", plan_text)


if __name__ == "__main__":
    unittest.main()
