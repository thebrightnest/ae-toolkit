"""Tests for `aet gate review` rendering the board from live task records."""

from __future__ import annotations

import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from aet.cli import gate as gate_cli


def _task(
    task_id: str,
    state: str,
    title: str = "",
    stage: str | None = None,
    spec: dict | None = None,
) -> dict:
    task: dict = {"id": task_id, "state": state}
    if title:
        task["title"] = title
    if stage is not None:
        task["stage"] = stage
    if spec is not None:
        task["spec"] = spec
    return task


class TestBoardReview(unittest.TestCase):
    """`gate review` reads the board from open work, not from plan files."""

    def _capture(self, queue: list[dict]) -> tuple[int, str]:
        stdout = io.StringIO()
        with patch.object(sys, "stdout", stdout):
            rc = gate_cli.run_board_review(queue)
        return rc, stdout.getvalue()

    def test_board_lists_open_tasks_by_state(self):
        """Open tasks are grouped into the canonical board columns."""
        queue = [
            _task("approved-1", "planned", "Planned task"),
            _task("approved-2", "blocked", "Blocked task"),
            _task("queued-1", "ready", "Ready task"),
            _task("inprog-1", "in_progress", "In-progress task"),
            _task("await-1", "awaiting_merge", "Awaiting merge"),
        ]

        rc, output = self._capture(queue)

        self.assertEqual(rc, 0)
        self.assertIn("Approved (2):", output)
        self.assertIn("Queued (1):", output)
        self.assertIn("In Progress (1):", output)
        self.assertIn("Awaiting Merge (1):", output)
        self.assertIn("approved-1: Planned task", output)
        self.assertIn("approved-2: Blocked task", output)
        self.assertIn("queued-1: Ready task", output)
        self.assertIn("inprog-1: In-progress task", output)
        self.assertIn("await-1: Awaiting merge", output)

    def test_terminal_tasks_are_closed_not_open(self):
        """Merged and abandoned tasks appear only in the closed column."""
        queue = [
            _task("live", "ready", "Live task"),
            _task("done", "merged", "Merged task"),
            _task("dropped", "abandoned", "Abandoned task"),
        ]

        rc, output = self._capture(queue)

        self.assertEqual(rc, 0)
        self.assertIn("Queued (1):", output)
        self.assertIn("live: Live task", output)
        self.assertIn("Closed (2):", output)
        self.assertIn("done: Merged task", output)
        self.assertIn("dropped: Abandoned task", output)
        # They must not leak into any open column.
        self.assertNotIn("done: Live task", output)
        self.assertNotIn("dropped: Live task", output)

    def test_title_falls_back_to_spec(self):
        """If the task record has no title, the spec title is used."""
        queue = [
            _task("t1", "planned", spec={"title": "Spec title"}),
        ]

        rc, output = self._capture(queue)

        self.assertEqual(rc, 0)
        self.assertIn("t1: Spec title", output)

    def test_title_falls_back_to_id(self):
        """A task with no title or spec prints the id only."""
        queue = [
            {"id": "t1", "state": "planned"},
        ]

        rc, output = self._capture(queue)

        self.assertEqual(rc, 0)
        self.assertIn("t1: t1", output)

    def test_empty_board_prints_zero_counts(self):
        """An empty queue still renders all five columns with zero counts."""
        rc, output = self._capture([])

        self.assertEqual(rc, 0)
        for column in ("Approved", "Queued", "In Progress", "Awaiting Merge", "Closed"):
            self.assertIn(f"{column} (0):", output)

    def test_stage_field_takes_precedence_when_present(self):
        """A task with an explicit pipeline stage maps via the workflow vocabulary."""
        queue = [
            _task("t1", "planned", stage="implemented"),
            _task("t2", "planned", stage="synced"),
        ]

        rc, output = self._capture(queue)

        self.assertEqual(rc, 0)
        self.assertIn("In Progress (1):", output)
        self.assertIn("Queued (1):", output)


class TestLegacyPlanDirReview(unittest.TestCase):
    """The `--plans-dir` escape hatch still renders from plan files."""

    def _make_plan(self, path: Path, footer_stage: str) -> None:
        path.write_text(
            "---\n"
            f"id: {path.stem}\n"
            "size: S\n"
            "---\n\n"
            f"# Plan {path.stem}\n\n"
            "---\n\n"
            f"*Stage: {footer_stage}*\n",
            encoding="utf-8",
        )

    def test_plans_dir_renders_footer_stage_board(self):
        with tempfile.TemporaryDirectory() as tmp:
            plans_dir = Path(tmp) / "plans"
            plans_dir.mkdir()
            self._make_plan(plans_dir / "approved-1.md", "plan-approved")

            stdout = io.StringIO()
            with patch.object(sys, "stdout", stdout):
                rc = gate_cli.run_review(plans_dir)

            self.assertEqual(rc, 0)
            self.assertIn("approved-1", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
