"""Blocker resolution at intake is fail-closed (ADR-011 d4, ADR-059).

Regression test for the incident where a task dispatched in parallel with its
own blocker: the intake filter treated a blocker that was not on the board as
satisfied, so a task whose blocker had not been added yet was admitted `ready`
with `pending_blockers: 0`.
"""

import tempfile
import unittest
from pathlib import Path

from aet.plan_parser import new_task_from_plan


def _plan(tmpdir: Path, task_id: str, blocked_by: list[str]) -> Path:
    path = tmpdir / f"{task_id}.md"
    path.write_text(
        f"---\nid: {task_id}\nblocked_by: {blocked_by}\nsize: S\n---\n\n# {task_id}\n",
        encoding="utf-8",
    )
    return path


class TestBlockerFailClosed(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmpdir = Path(self._tmp.name)

    def test_blocker_absent_from_board_is_pending(self):
        """The defect: an unknown blocker used to read as satisfied."""
        plan = _plan(self.tmpdir, "e40-07", ["e40-06"])
        task = new_task_from_plan(plan, live_tasks=[], settled_ids=set())
        self.assertEqual(task["state"], "blocked")
        self.assertEqual(task["pending_blockers"], 1)

    def test_blocker_with_a_tombstone_is_satisfied(self):
        """Positive evidence of settling still unblocks the task."""
        plan = _plan(self.tmpdir, "e40-07", ["e40-06"])
        task = new_task_from_plan(plan, live_tasks=[], settled_ids={"e40-06"})
        self.assertEqual(task["state"], "ready")
        self.assertEqual(task["pending_blockers"], 0)

    def test_blocker_terminal_on_the_board_is_satisfied(self):
        plan = _plan(self.tmpdir, "e40-07", ["e40-06"])
        task = new_task_from_plan(
            plan, live_tasks=[{"id": "e40-06", "state": "merged"}], settled_ids=set()
        )
        self.assertEqual(task["state"], "ready")

    def test_blocker_in_progress_on_the_board_is_pending(self):
        plan = _plan(self.tmpdir, "e40-07", ["e40-06"])
        task = new_task_from_plan(
            plan,
            live_tasks=[{"id": "e40-06", "state": "in_progress"}],
            settled_ids=set(),
        )
        self.assertEqual(task["state"], "blocked")
        self.assertEqual(task["pending_blockers"], 1)

    def test_mixed_blockers_count_only_the_unsatisfied(self):
        plan = _plan(self.tmpdir, "e40-07", ["e40-01", "e40-06", "e40-09"])
        task = new_task_from_plan(
            plan,
            live_tasks=[{"id": "e40-06", "state": "in_progress"}],
            settled_ids={"e40-01"},
        )
        # e40-01 settled, e40-06 in progress, e40-09 absent -> two pending.
        self.assertEqual(task["pending_blockers"], 2)
        self.assertEqual(task["state"], "blocked")

    def test_no_blockers_is_ready(self):
        plan = _plan(self.tmpdir, "e40-01", [])
        task = new_task_from_plan(plan, live_tasks=[], settled_ids=set())
        self.assertEqual(task["state"], "ready")
        self.assertEqual(task["pending_blockers"], 0)


class TestSettledIdSources(unittest.TestCase):
    """Settled-ness is read from every positive source, not just tombstones."""

    def test_history_settled_blocker_counts_as_settled(self):
        """A blocker merged and archived before the dependent was added.

        Reading only ADR-059 tombstones misses it and deadlocks the dependent,
        which is the add-after-merge regression.
        """
        import json

        from aet.cli.sprint import _settled_ids

        with tempfile.TemporaryDirectory() as tmp:
            history = Path(tmp) / "work-history.jsonl"
            history.write_text(
                json.dumps({"id": "feat-399", "state": "merged"}) + "\n",
                encoding="utf-8",
            )
            self.assertIn("feat-399", _settled_ids(None, str(history)))

    def test_non_terminal_history_record_is_not_settled(self):
        import json

        from aet.cli.sprint import _settled_ids

        with tempfile.TemporaryDirectory() as tmp:
            history = Path(tmp) / "work-history.jsonl"
            history.write_text(
                json.dumps({"id": "feat-399", "state": "in_progress"}) + "\n",
                encoding="utf-8",
            )
            self.assertNotIn("feat-399", _settled_ids(None, str(history)))

    def test_missing_history_yields_nothing_settled(self):
        """No evidence means nothing is settled: fail closed, never crash."""
        from aet.cli.sprint import _settled_ids

        self.assertEqual(_settled_ids(None, "/nonexistent/work-history.jsonl"), set())


if __name__ == "__main__":
    unittest.main()
