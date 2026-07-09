"""Behavior-driven tests for aet-work/bin/add and aet-work/bin/review."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_REPO_ROOT = Path(__file__).parent.parent
_ADD_PY = _REPO_ROOT / "aet-work" / "bin" / "add"
_REVIEW_PY = _REPO_ROOT / "aet-work" / "bin" / "review"
_STATUS_PY = _REPO_ROOT / "aet-work" / "bin" / "status"

_add_spec = importlib.util.spec_from_loader(
    "add", importlib.machinery.SourceFileLoader("add", str(_ADD_PY))
)
add = importlib.util.module_from_spec(_add_spec)
_add_spec.loader.exec_module(add)

_review_spec = importlib.util.spec_from_loader(
    "review", importlib.machinery.SourceFileLoader("review", str(_REVIEW_PY))
)
review = importlib.util.module_from_spec(_review_spec)
_review_spec.loader.exec_module(review)

_status_spec = importlib.util.spec_from_loader(
    "status", importlib.machinery.SourceFileLoader("status", str(_STATUS_PY))
)
status = importlib.util.module_from_spec(_status_spec)
_status_spec.loader.exec_module(status)


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
    blocked_by: list[str] | None = None,
) -> Path:
    path = plans_dir / name
    blocked_lines = "".join(f"  - {b}\n" for b in (blocked_by or []))
    body = f"""---
id: {Path(name).stem}
size: M
blocked_by:
{blocked_lines}---

# Plan: {name}

## Task List

1. Do something.

---

_Stage: {footer_stage}_
_Next step: run `aet-work`_
"""
    path.write_text(body, encoding="utf-8")
    return path


class TestAddCommand(unittest.TestCase):
    def test_add_plan_file_adds_task_as_planned(self):
        """add accepts a plan file path and inserts the task as planned."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            plans_dir = tmp_path / "plans"
            plans_dir.mkdir()
            plan = _make_plan(plans_dir, "feat-001.md")
            queue_file = _write_json_file([])
            history_file = _make_history([])

            rc = add.main([
                str(plan),
                "--queue-file", queue_file,
                "--history-file", history_file,
                "--plans-dir", str(plans_dir),
            ])

            self.assertEqual(rc, 0)
            with open(queue_file, "r", encoding="utf-8") as f:
                queue = json.load(f)
            self.assertEqual(len(queue), 1)
            self.assertEqual(queue[0]["id"], "feat-001")
            self.assertEqual(queue[0]["state"], "planned")
            self.assertEqual(queue[0]["plan_file"], str(plan))

    def test_add_task_id_adds_task_as_planned(self):
        """add accepts a task ID and resolves it to the plan file."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            plans_dir = tmp_path / "plans"
            plans_dir.mkdir()
            _make_plan(plans_dir, "feat-002.md")
            queue_file = _write_json_file([])
            history_file = _make_history([])

            rc = add.main([
                "feat-002",
                "--queue-file", queue_file,
                "--history-file", history_file,
                "--plans-dir", str(plans_dir),
            ])

            self.assertEqual(rc, 0)
            with open(queue_file, "r", encoding="utf-8") as f:
                queue = json.load(f)
            self.assertEqual(len(queue), 1)
            self.assertEqual(queue[0]["id"], "feat-002")

    def test_add_rejects_merged_plan(self):
        """add refuses to queue a plan whose footer stage is merged."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            plans_dir = tmp_path / "plans"
            plans_dir.mkdir()
            plan = _make_plan(plans_dir, "feat-003.md", footer_stage="merged")
            queue_file = _write_json_file([])
            history_file = _make_history([])

            stderr = io.StringIO()
            with patch.object(sys, "stderr", stderr):
                rc = add.main([
                    str(plan),
                    "--queue-file", queue_file,
                    "--history-file", history_file,
                    "--plans-dir", str(plans_dir),
                ])

            self.assertEqual(rc, 1)
            output = stderr.getvalue()
            self.assertIn("merged", output.lower())
            with open(queue_file, "r", encoding="utf-8") as f:
                queue = json.load(f)
            self.assertEqual(len(queue), 0)

    def test_add_rejects_abandoned_plan(self):
        """add refuses to queue a plan whose footer stage is abandoned."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            plans_dir = tmp_path / "plans"
            plans_dir.mkdir()
            plan = _make_plan(plans_dir, "feat-004.md", footer_stage="abandoned")
            queue_file = _write_json_file([])
            history_file = _make_history([])

            stderr = io.StringIO()
            with patch.object(sys, "stderr", stderr):
                rc = add.main([
                    str(plan),
                    "--queue-file", queue_file,
                    "--history-file", history_file,
                    "--plans-dir", str(plans_dir),
                ])

            self.assertEqual(rc, 1)
            output = stderr.getvalue()
            self.assertIn("abandoned", output.lower())

    def test_add_unknown_plan_rejected(self):
        """add exits non-zero when the plan file or task ID is unknown."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            plans_dir = tmp_path / "plans"
            plans_dir.mkdir()
            queue_file = _write_json_file([])
            history_file = _make_history([])

            rc = add.main([
                "nonexistent",
                "--queue-file", queue_file,
                "--history-file", history_file,
                "--plans-dir", str(plans_dir),
            ])

            self.assertEqual(rc, 1)

    def test_add_already_queued_is_idempotent(self):
        """add succeeds without duplicating an already-queued task."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            plans_dir = tmp_path / "plans"
            plans_dir.mkdir()
            plan = _make_plan(plans_dir, "feat-005.md")
            queue_file = _write_json_file([])
            history_file = _make_history([])

            rc1 = add.main([
                str(plan),
                "--queue-file", queue_file,
                "--history-file", history_file,
                "--plans-dir", str(plans_dir),
            ])
            self.assertEqual(rc1, 0)

            rc2 = add.main([
                str(plan),
                "--queue-file", queue_file,
                "--history-file", history_file,
                "--plans-dir", str(plans_dir),
            ])
            self.assertEqual(rc2, 0)

            with open(queue_file, "r", encoding="utf-8") as f:
                queue = json.load(f)
            self.assertEqual(len(queue), 1)


class TestReviewCommand(unittest.TestCase):
    def test_review_categorizes_plans_by_footer_stage(self):
        """review prints plans grouped into approved/queued/in-progress/awaiting-merge/closed."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            plans_dir = tmp_path / "plans"
            plans_dir.mkdir()
            _make_plan(plans_dir, "approved-1.md", footer_stage="plan-approved")
            _make_plan(plans_dir, "queued-1.md", footer_stage="synced")
            _make_plan(plans_dir, "inprog-1.md", footer_stage="implemented")
            _make_plan(plans_dir, "await-1.md", footer_stage="awaiting_merge")
            _make_plan(plans_dir, "closed-1.md", footer_stage="merged")
            _make_plan(plans_dir, "closed-2.md", footer_stage="abandoned")

            stdout = io.StringIO()
            with patch.object(sys, "stdout", stdout):
                rc = review.main([
                    "--plans-dir", str(plans_dir),
                ])

            self.assertEqual(rc, 0)
            output = stdout.getvalue()
            self.assertIn("approved-1", output)
            self.assertIn("queued-1", output)
            self.assertIn("inprog-1", output)
            self.assertIn("await-1", output)
            self.assertIn("closed-1", output)
            self.assertIn("closed-2", output)

    def test_review_empty_plans_dir(self):
        """review exits cleanly when no plans exist."""
        with tempfile.TemporaryDirectory() as tmp:
            plans_dir = Path(tmp) / "plans"
            plans_dir.mkdir()

            stdout = io.StringIO()
            with patch.object(sys, "stdout", stdout):
                rc = review.main([
                    "--plans-dir", str(plans_dir),
                ])

            self.assertEqual(rc, 0)

    def test_review_missing_plans_dir(self):
        """review exits non-zero when the plans directory does not exist."""
        stdout = io.StringIO()
        with patch.object(sys, "stdout", stdout):
            rc = review.main([
                "--plans-dir", "/does/not/exist",
            ])

        self.assertEqual(rc, 1)


class TestStatusEmptyQueue(unittest.TestCase):
    def test_status_handles_empty_queue_gracefully(self):
        """status prints a clean summary when the queue exists but is empty."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            plans_dir = tmp_path / "plans"
            plans_dir.mkdir()
            queue_file = _write_json_file([])
            history_file = _make_history([])

            stdout = io.StringIO()
            with patch.object(sys, "stdout", stdout):
                with patch.object(sys, "argv", [
                    "status",
                    "--queue-file", queue_file,
                    "--history-file", history_file,
                    "--plans-dir", str(plans_dir),
                ]):
                    rc = status.main()

            self.assertEqual(rc, 0)
            output = stdout.getvalue()
            self.assertIn("planned: 0", output)
            self.assertIn("ready: 0", output)
            self.assertIn("blocked: 0", output)


if __name__ == "__main__":
    unittest.main()
