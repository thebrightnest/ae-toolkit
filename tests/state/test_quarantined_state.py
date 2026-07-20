"""Tests for the quarantined task state (nsr-02)."""

import importlib.machinery
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_AET_STATE_PY = Path(__file__).parents[2] / "src" / "aet" / "cli" / "aet-state.py"
_spec = importlib.util.spec_from_loader(
    "aet_state", importlib.machinery.SourceFileLoader("aet_state", str(_AET_STATE_PY))
)
aet_state = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(aet_state)

_AET_QUEUE_PY = Path(__file__).parents[2] / "src" / "aet" / "queue.py"
_queue_spec = importlib.util.spec_from_loader(
    "aet_queue", importlib.machinery.SourceFileLoader("aet_queue", str(_AET_QUEUE_PY))
)
aet_queue = importlib.util.module_from_spec(_queue_spec)
_queue_spec.loader.exec_module(aet_queue)

_ORCHESTRATOR_PY = Path(__file__).parents[2] / "src" / "aet" / "cli" / "orchestrator.py"
_orchestrator_spec = importlib.util.spec_from_loader(
    "orchestrator", importlib.machinery.SourceFileLoader("orchestrator", str(_ORCHESTRATOR_PY))
)
orchestrator = importlib.util.module_from_spec(_orchestrator_spec)
_orchestrator_spec.loader.exec_module(orchestrator)


def _git_mock(responses):
    """Return a mock subprocess.run that answers git commands."""

    def mock_run(cmd, **kwargs):
        args = tuple(cmd[1:])
        rc, out, err = responses.get(args, (1, "", ""))
        return type("MockResult", (), {"returncode": rc, "stdout": out, "stderr": err})()

    return mock_run


class TestQuarantinedTransitionTable(unittest.TestCase):
    """Unit tests for the quarantined transitions in LEGAL_TRANSITIONS."""

    def test_quarantined_legal_targets(self):
        """in_progress and failed may enter quarantined."""
        self.assertIn("quarantined", aet_queue.LEGAL_TRANSITIONS["in_progress"])
        self.assertIn("quarantined", aet_queue.LEGAL_TRANSITIONS["failed"])

    def test_quarantined_legal_sources(self):
        """quarantined may only exit to ready or abandoned."""
        self.assertEqual(
            aet_queue.LEGAL_TRANSITIONS["quarantined"],
            {"ready", "abandoned"},
        )

    def test_quarantined_is_not_terminal(self):
        """quarantined is not in TERMINAL_STATES and does not satisfy blockers."""
        self.assertNotIn("quarantined", aet_queue.TERMINAL_STATES)
        self.assertNotIn("quarantined", aet_queue.HISTORY_TERMINAL_STATES)

    def test_quarantined_to_in_progress_rejected(self):
        """quarantined -> in_progress is illegal."""
        task = {"id": "t1", "state": "quarantined"}
        ok, msg = aet_state.validate_transition(task, "quarantined", "in_progress")
        self.assertFalse(ok)
        self.assertIn("Illegal transition", msg)


class TestQuarantinedStateApplication(unittest.TestCase):
    """Integration tests for applying quarantined transitions via aet-state."""

    def _write_queue(self, tasks):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump({"tasks": tasks}, f)
        f.close()
        return f.name

    def _load_task(self, queue_path):
        with open(queue_path, "r", encoding="utf-8") as f:
            return json.load(f)["tasks"][0]

    def test_in_progress_to_quarantined(self):
        """A task can transition from in_progress to quarantined."""
        queue_path = self._write_queue([{"id": "t1", "state": "in_progress"}])

        args = aet_state.argparse.Namespace(
            command="transition",
            task_id="t1",
            from_stage="in_progress",
            to_stage="quarantined",
            queue=queue_path,
            dry_run=False,
            reason="deterministic failure",
        )

        rc = aet_state.cmd_transition(args)
        self.assertEqual(rc, 0)

        task = self._load_task(queue_path)
        self.assertEqual(task["state"], "quarantined")
        self.assertEqual(len(task["history"]), 1)
        self.assertEqual(task["history"][0]["from"], "in_progress")
        self.assertEqual(task["history"][0]["to"], "quarantined")

    def test_failed_to_quarantined(self):
        """A task can transition from failed to quarantined."""
        queue_path = self._write_queue([{"id": "t1", "state": "failed"}])

        args = aet_state.argparse.Namespace(
            command="transition",
            task_id="t1",
            from_stage="failed",
            to_stage="quarantined",
            queue=queue_path,
            dry_run=False,
            reason="deterministic failure",
        )

        rc = aet_state.cmd_transition(args)
        self.assertEqual(rc, 0)

        task = self._load_task(queue_path)
        self.assertEqual(task["state"], "quarantined")

    def test_quarantined_to_ready(self):
        """A quarantined task can be manually cleared to ready."""
        queue_path = self._write_queue([{"id": "t1", "state": "quarantined"}])

        args = aet_state.argparse.Namespace(
            command="transition",
            task_id="t1",
            from_stage="quarantined",
            to_stage="ready",
            queue=queue_path,
            dry_run=False,
            reason="human un-quarantine",
        )

        rc = aet_state.cmd_transition(args)
        self.assertEqual(rc, 0)

        task = self._load_task(queue_path)
        self.assertEqual(task["state"], "ready")

    def test_quarantined_to_abandoned_is_terminal(self):
        """quarantined -> abandoned seals the task and promotes dependents."""
        with tempfile.TemporaryDirectory() as tmpdir:
            queue_path = Path(tmpdir) / "work-queue.json"
            history_file = queue_path.with_name("work-history.jsonl")
            queue = {
                "tasks": [
                    {
                        "id": "blocker",
                        "state": "quarantined",
                        "blocks": ["dependent"],
                    },
                    {
                        "id": "dependent",
                        "state": "blocked",
                        "blocked_by": ["blocker"],
                        "pending_blockers": 1,
                    },
                ]
            }
            queue_path.write_text(json.dumps(queue), encoding="utf-8")

            args = aet_state.argparse.Namespace(
                command="transition",
                task_id="blocker",
                from_stage="quarantined",
                to_stage="abandoned",
                queue=str(queue_path),
                dry_run=False,
                reason="give up",
            )

            rc = aet_state.cmd_transition(args)
            self.assertEqual(rc, 0)

            with open(queue_path, "r", encoding="utf-8") as f:
                after = json.load(f)
            by_id = {t["id"]: t for t in after["tasks"]}
            self.assertNotIn("blocker", by_id)
            self.assertEqual(by_id["dependent"]["state"], "ready")

            with open(history_file, "r", encoding="utf-8") as f:
                settled = json.loads(f.readline())
            self.assertEqual(settled["id"], "blocker")
            self.assertEqual(settled["state"], "abandoned")

    def test_quarantined_to_ready_does_not_promote_dependents(self):
        """Un-quarantining to ready does not satisfy blockers."""
        queue_path = self._write_queue(
            [
                {
                    "id": "blocker",
                    "state": "quarantined",
                    "blocks": ["dependent"],
                },
                {
                    "id": "dependent",
                    "state": "blocked",
                    "blocked_by": ["blocker"],
                    "pending_blockers": 1,
                },
            ]
        )

        args = aet_state.argparse.Namespace(
            command="transition",
            task_id="blocker",
            from_stage="quarantined",
            to_stage="ready",
            queue=queue_path,
            dry_run=False,
            reason="human un-quarantine",
        )

        rc = aet_state.cmd_transition(args)
        self.assertEqual(rc, 0)

        with open(queue_path, "r", encoding="utf-8") as f:
            after = json.load(f)
        by_id = {t["id"]: t for t in after["tasks"]}
        self.assertEqual(by_id["blocker"]["state"], "ready")
        self.assertEqual(by_id["dependent"]["state"], "blocked")
        self.assertEqual(by_id["dependent"]["pending_blockers"], 1)


class TestQuarantinedHeal(unittest.TestCase):
    """Heal must never auto-derive a quarantined task away."""

    def _write_queue(self, tmpdir, tasks):
        plans_dir = Path(tmpdir) / "plans"
        plans_dir.mkdir(parents=True)
        for task in tasks:
            plan = plans_dir / f"{task['id']}.md"
            plan.write_text("# Plan\n", encoding="utf-8")
            task.setdefault("plan_file", str(plan))
            task.setdefault("branch", None)
        queue_path = Path(tmpdir) / "work-queue.json"
        queue_path.write_text(json.dumps({"tasks": tasks}), encoding="utf-8")
        return queue_path

    def _run_heal(self, queue_path, apply):
        args = aet_state.argparse.Namespace(
            command="heal",
            queue=str(queue_path),
            apply=apply,
            force=False,
        )
        with patch.object(aet_state.subprocess, "run", side_effect=_git_mock({})):
            return aet_state.cmd_heal(args)

    def test_heal_preserves_quarantined(self):
        """A quarantined task is left untouched even when git would derive ready."""
        with tempfile.TemporaryDirectory() as tmpdir:
            queue_path = self._write_queue(
                tmpdir,
                [{"id": "t1", "state": "quarantined"}],
            )

            self.assertEqual(self._run_heal(queue_path, apply=True), 0)

            with open(queue_path, "r", encoding="utf-8") as f:
                after = json.load(f)
            self.assertEqual(after["tasks"][0]["state"], "quarantined")


class TestQuarantinedNotActionable(unittest.TestCase):
    """The batch spawn selector must never treat quarantined as actionable."""

    def test_quarantined_not_actionable(self):
        """has_actionable_tasks ignores quarantined tasks."""
        queue = [
            {"id": "t1", "state": "quarantined"},
            {"id": "t2", "state": "awaiting_merge"},
            {"id": "t3", "state": "blocked"},
        ]
        self.assertFalse(orchestrator.has_actionable_tasks(queue))

    def test_quarantined_appears_in_leftovers(self):
        """leftover_counts reports quarantined as a stranded non-terminal state."""
        queue = [
            {"id": "t1", "state": "quarantined"},
            {"id": "t2", "state": "failed"},
        ]
        counts = orchestrator.leftover_counts(queue)
        self.assertIn("quarantined", counts)
        self.assertEqual(counts["quarantined"], 1)

    def test_spawn_selector_skips_quarantined(self):
        """get_next_ready_task never returns a quarantined task."""
        queue = [
            {"id": "t1", "state": "quarantined"},
            {"id": "t2", "state": "ready"},
        ]
        task = orchestrator.get_next_ready_task(queue)
        self.assertIsNotNone(task)
        self.assertEqual(task["id"], "t2")


if __name__ == "__main__":
    unittest.main()
