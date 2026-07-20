"""Tests for noun-scoped command groups (`aet sprint`, `aet backlog`)."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

_REPO_ROOT = Path(__file__).parent.parent
_SPRINT_PY = _REPO_ROOT / "src" / "aet" / "cli" / "sprint.py"
_BACKLOG_PY = _REPO_ROOT / "src" / "aet" / "cli" / "backlog.py"
_AET_PY = _REPO_ROOT / "aet-work" / "bin" / "aet"

_sprint_spec = importlib.util.spec_from_loader(
    "sprint", importlib.machinery.SourceFileLoader("sprint", str(_SPRINT_PY))
)
sprint = importlib.util.module_from_spec(_sprint_spec)
_sprint_spec.loader.exec_module(sprint)

_backlog_spec = importlib.util.spec_from_loader(
    "backlog", importlib.machinery.SourceFileLoader("backlog", str(_BACKLOG_PY))
)
backlog = importlib.util.module_from_spec(_backlog_spec)
_backlog_spec.loader.exec_module(backlog)

_aet_spec = importlib.util.spec_from_loader(
    "aet_dispatcher",
    importlib.machinery.SourceFileLoader("aet_dispatcher", str(_AET_PY)),
)
aet = importlib.util.module_from_spec(_aet_spec)
_aet_spec.loader.exec_module(aet)


def _write_json_file(data) -> str:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data, f)
        return f.name


def _make_history(tasks: list[dict]) -> str:
    path = Path(tempfile.mkstemp(suffix=".jsonl")[1])
    with open(path, "w", encoding="utf-8") as f:
        for task in tasks:
            json.dump(task, f)
            f.write("\n")
    return str(path)


def _make_plan(
    plans_dir: Path,
    name: str,
    *,
    footer_stage: str = "plan-approved",
    status: str = "approved",
    blocked_by: list[str] | None = None,
) -> Path:
    path = plans_dir / name
    blocked_lines = "".join(f"  - {b}\n" for b in (blocked_by or []))
    body = f"""---
id: {Path(name).stem}
size: M
status: {status}
blocked_by:
{blocked_lines}---

# Plan: {name}

## Context
PRD: docs/prds/default-prd.md

## Task List

1. Do something (traces: R-1).

## Files to Modify

- `src/widget.py` (new)

## Validation Steps

- [ ] test_widget_creation verifies widget.py

---

_Stage: {footer_stage}_
_Next step: run `aet-work`_
"""
    path.write_text(body, encoding="utf-8")
    return path


def _git(args: list[str], cwd: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, capture_output=True, check=True)


class TestSprintAdd(unittest.TestCase):
    def test_sprint_add_promotes_and_commits(self):
        """sprint add sets status: queued, commits, and adds the task to the queue."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _git(["init"], tmp)
            _git(["config", "user.email", "test@example.com"], tmp)
            _git(["config", "user.name", "Test"], tmp)

            plans_dir = tmp_path / "docs" / "plans"
            plans_dir.mkdir(parents=True)
            prds_dir = tmp_path / "docs" / "prds"
            prds_dir.mkdir(parents=True)
            (prds_dir / "default-prd.md").write_text(
                "# Default PRD\n\n## Requirements\n- **R-1**: default requirement\n",
                encoding="utf-8",
            )
            plan = _make_plan(plans_dir, "feat-001.md")
            _git(["add", "-A"], tmp)
            _git(["commit", "-m", "initial"], tmp)

            queue_file = _write_json_file([])
            history_file = _make_history([])

            mock_projections = MagicMock()

            with patch.object(sprint, "resolve_projections", return_value=mock_projections):
                with patch.object(sprint, "resolve_config", return_value={}):
                    rc = sprint.main([
                        "add", str(plan),
                        "--queue-file", queue_file,
                        "--history-file", history_file,
                        "--plans-dir", str(plans_dir),
                    ])

            self.assertEqual(rc, 0)

            # Plan file promoted to queued; footer pipeline stage is preserved.
            plan_text = plan.read_text(encoding="utf-8")
            self.assertIn("status: queued", plan_text)
            self.assertIn("_Stage: plan-approved_", plan_text)

            # Commit was made.
            result = subprocess.run(
                ["git", "log", "--format=%s"],
                cwd=tmp,
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertIn("chore(feat-001): mark plan as queued", result.stdout)

            # Task added to queue as ready.
            with open(queue_file, "r", encoding="utf-8") as f:
                queue = json.load(f)
            self.assertEqual(len(queue), 1)
            self.assertEqual(queue[0]["id"], "feat-001")
            self.assertEqual(queue[0]["state"], "ready")
            self.assertNotIn("status", queue[0])

            # Projection notified.
            mock_projections.on_add.assert_called_once()
            args, kwargs = mock_projections.on_add.call_args
            self.assertEqual(args[0]["id"], "feat-001")
            self.assertTrue(kwargs.get("is_new"))  # is_new=True

    def test_sprint_add_blocked_plan_computes_state(self):
        """sprint add parks a plan with pending blockers as blocked."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _git(["init"], tmp)
            _git(["config", "user.email", "test@example.com"], tmp)
            _git(["config", "user.name", "Test"], tmp)

            plans_dir = tmp_path / "docs" / "plans"
            plans_dir.mkdir(parents=True)
            prds_dir = tmp_path / "docs" / "prds"
            prds_dir.mkdir(parents=True)
            (prds_dir / "default-prd.md").write_text(
                "# Default PRD\n\n## Requirements\n- **R-1**: default requirement\n",
                encoding="utf-8",
            )
            blocker = _make_plan(plans_dir, "feat-000.md")
            plan = _make_plan(plans_dir, "feat-001.md", blocked_by=["feat-000"])
            _git(["add", "-A"], tmp)
            _git(["commit", "-m", "initial"], tmp)

            queue_file = _write_json_file([])
            history_file = _make_history([])

            mock_projections = MagicMock()

            with patch.object(sprint, "resolve_projections", return_value=mock_projections):
                with patch.object(sprint, "resolve_config", return_value={}):
                    self.assertEqual(sprint.main([
                        "add", str(blocker),
                        "--queue-file", queue_file,
                        "--history-file", history_file,
                        "--plans-dir", str(plans_dir),
                    ]), 0)
                    self.assertEqual(sprint.main([
                        "add", str(plan),
                        "--queue-file", queue_file,
                        "--history-file", history_file,
                        "--plans-dir", str(plans_dir),
                    ]), 0)

            with open(queue_file, "r", encoding="utf-8") as f:
                queue = json.load(f)
            tasks = {t["id"]: t for t in queue}
            self.assertEqual(tasks["feat-001"]["state"], "blocked")
            self.assertEqual(tasks["feat-001"]["pending_blockers"], 1)

    def test_sprint_add_unknown_id_fails_closed(self):
        """sprint add exits non-zero when the plan file or task ID is unknown."""
        with tempfile.TemporaryDirectory() as tmp:
            plans_dir = Path(tmp) / "docs" / "plans"
            plans_dir.mkdir(parents=True)
            queue_file = _write_json_file([])
            history_file = _make_history([])

            stderr = io.StringIO()
            with patch.object(sys, "stderr", stderr):
                rc = sprint.main([
                    "add", "nonexistent",
                    "--queue-file", queue_file,
                    "--history-file", history_file,
                    "--plans-dir", str(plans_dir),
                ])

            self.assertEqual(rc, 1)
            self.assertIn("No plan found", stderr.getvalue())
            with open(queue_file, "r", encoding="utf-8") as f:
                self.assertEqual(len(json.load(f)), 0)

    def test_sprint_add_refuses_non_approved_plan(self):
        """Only plan-approved plans may enter the sprint."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _git(["init"], tmp)
            _git(["config", "user.email", "test@example.com"], tmp)
            _git(["config", "user.name", "Test"], tmp)

            plans_dir = tmp_path / "docs" / "plans"
            plans_dir.mkdir(parents=True)
            prds_dir = tmp_path / "docs" / "prds"
            prds_dir.mkdir(parents=True)
            (prds_dir / "default-prd.md").write_text(
                "# Default PRD\n\n## Requirements\n- **R-1**: default requirement\n",
                encoding="utf-8",
            )
            plan = _make_plan(plans_dir, "feat-002.md", footer_stage="draft")
            _git(["add", "-A"], tmp)
            _git(["commit", "-m", "initial"], tmp)

            queue_file = _write_json_file([])
            history_file = _make_history([])

            stderr = io.StringIO()
            with patch.object(sys, "stderr", stderr):
                rc = sprint.main([
                    "add", str(plan),
                    "--queue-file", queue_file,
                    "--history-file", history_file,
                    "--plans-dir", str(plans_dir),
                ])

            self.assertEqual(rc, 1)
            self.assertIn("plan-approved", stderr.getvalue())

    def test_sprint_add_refuses_untracked_plan(self):
        """The intake durability guard refuses untracked plans."""
        with tempfile.TemporaryDirectory() as tmp:
            _git(["init"], tmp)
            plans_dir = Path(tmp) / "docs" / "plans"
            plans_dir.mkdir(parents=True)
            plan = _make_plan(plans_dir, "feat-003.md")
            queue_file = _write_json_file([])
            history_file = _make_history([])

            stderr = io.StringIO()
            with patch.object(sys, "stderr", stderr):
                rc = sprint.main([
                    "add", str(plan),
                    "--queue-file", queue_file,
                    "--history-file", history_file,
                    "--plans-dir", str(plans_dir),
                ])

            self.assertEqual(rc, 1)
            self.assertIn("track", stderr.getvalue().lower())


class TestBacklogGroup(unittest.TestCase):
    def test_backlog_group_registered(self):
        """The backlog binary parses `add` and resolves unknown plans."""
        with tempfile.TemporaryDirectory() as tmp:
            plans_dir = Path(tmp) / "docs" / "plans"
            plans_dir.mkdir(parents=True)
            stderr = io.StringIO()
            with patch.object(sys, "stderr", stderr):
                rc = backlog.main(["add", "feat-001", "--plans-dir", str(plans_dir)])
            self.assertEqual(rc, 1)
            self.assertIn("No plan found", stderr.getvalue())


class TestTopLevelAddRetired(unittest.TestCase):
    def test_top_level_add_is_unknown_subcommand(self):
        """Bare `aet add` no longer resolves through the dispatcher."""
        import io as stdlib_io

        stderr = stdlib_io.StringIO()
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp) / "bin"
            with patch.object(sys, "argv", ["aet", "add", "docs/plans/x.md"]):
                with patch.object(sys, "stderr", stderr):
                    with patch.dict(os.environ, {"AET_BIN_DIR": str(bin_dir)}):
                        with patch.object(aet.os, "execvp") as mock_exec:
                            rc = aet.main()
        self.assertEqual(rc, 2)
        mock_exec.assert_not_called()
        self.assertIn("unknown subcommand 'add'", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
