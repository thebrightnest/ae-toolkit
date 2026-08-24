"""A closed provider window stops the run instead of burning the queue.

A rate limit is not the task's fault and not transient within a retry interval.
Classifying it as `flaky` requeued the task immediately, which failed again for
the same reason; the per-task breaker capped that at three attempts and then
quarantined a task that was never broken.
"""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from aet import breaker
from aet.backends.git_refs_backend import GitRefsBackend
from aet.cli import orchestrator
from aet.failure import FailureClass


def _repo(root: Path) -> tuple[GitRefsBackend, Path]:
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    for key, value in (("user.email", "t@example.com"), ("user.name", "T")):
        subprocess.run(["git", "-C", str(root), "config", key, value], check=True)
    queue_file = root / ".agents" / "aet-queue"
    queue_file.parent.mkdir(parents=True, exist_ok=True)
    return (
        GitRefsBackend(
            queue_file=str(queue_file),
            history_file=str(root / ".agents" / "work-history.jsonl"),
        ),
        queue_file,
    )


class TestBreakerEvidence(unittest.TestCase):
    """The breaker judges the task; a throttle says nothing about the task."""

    def test_a_throttled_failure_is_not_breaker_evidence(self):
        record: dict = {}

        recorded = breaker.append_failure_if_countable(
            record, FailureClass.THROTTLED, "sig"
        )

        self.assertFalse(recorded)
        self.assertEqual(record.get("failure_signatures", []), [])

    def test_a_canceled_failure_is_still_not_breaker_evidence(self):
        record: dict = {}

        self.assertFalse(
            breaker.append_failure_if_countable(record, FailureClass.CANCELED, "sig")
        )

    def test_a_flaky_failure_still_counts(self):
        record: dict = {}

        self.assertTrue(
            breaker.append_failure_if_countable(record, FailureClass.FLAKY, "sig")
        )
        self.assertEqual(len(record["failure_signatures"]), 1)

    def test_three_throttles_never_quarantine(self):
        """The 185-attempt cycle became three wasted attempts; now it is none."""
        record: dict = {}
        for _ in range(3):
            breaker.append_failure_if_countable(record, FailureClass.THROTTLED, "sig")

        self.assertFalse(breaker.should_quarantine_task(record))


class TestRunStops(unittest.TestCase):
    """Requeue the task, stop the shift, name the remedy."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.backend, self.queue_file = _repo(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def _finalize(self, failure_class: str, on_failure: str = "triage"):
        self.backend.save(
            [
                {
                    "id": "t1",
                    "state": "failed",
                    "plan_file": "docs/plans/t1.md",
                    "failure_signatures": [
                        {"signature": "s", "class": failure_class, "stage": "implement"}
                    ],
                }
            ]
        )
        with patch.object(orchestrator, "_mark_failed", return_value=True):
            with patch.object(orchestrator, "_requeue_task", return_value=True) as requeue:
                with patch.object(orchestrator, "_consult_triage_session") as triage:
                    result = orchestrator._finalize_task(
                        self.backend,
                        str(self.queue_file),
                        "t1",
                        ret=1,
                        on_failure=on_failure,
                        adapter=None,
                        repo_root=str(self.root),
                        worktree_dir=None,
                    )
        return result, requeue, triage

    def test_a_throttle_stops_spawning_and_requeues(self):
        result, requeue, _ = self._finalize(FailureClass.THROTTLED.value)

        self.assertTrue(result["stop_spawn"])
        self.assertEqual(result["failures"], 0)
        requeue.assert_called_once()

    def test_a_throttle_does_not_spend_a_triage_session(self):
        """Triaging a closed window is a session spent on a known answer."""
        _result, _requeue, triage = self._finalize(FailureClass.THROTTLED.value)

        triage.assert_not_called()

    def test_a_throttle_overrides_on_failure_continue(self):
        """Continuing would burn the rest of the queue on the same limit."""
        result, _requeue, _ = self._finalize(
            FailureClass.THROTTLED.value, on_failure="continue"
        )

        self.assertTrue(result["stop_spawn"])

    def test_a_flaky_failure_still_keeps_spawning(self):
        result, _requeue, _ = self._finalize(
            FailureClass.FLAKY.value, on_failure="continue"
        )

        self.assertFalse(result["stop_spawn"])

    def test_the_default_action_for_a_throttle_is_requeue_not_quarantine(self):
        self.assertEqual(
            orchestrator._TRIAGE_DEFAULT_ACTIONS[FailureClass.THROTTLED.value],
            "requeue",
        )

    def test_every_failure_class_has_a_default_action(self):
        """A class with no entry falls through to an untested default."""
        for member in FailureClass:
            self.assertIn(member.value, orchestrator._TRIAGE_DEFAULT_ACTIONS)


if __name__ == "__main__":
    unittest.main()
