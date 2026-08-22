"""A live lease is not seizable, and a refusal is not a work failure.

Regression tests for the incident where a second `aet run` overwrote a live
run's lease. The incumbent kept working but could no longer record anything:
every write was refused, and the refusals were reported as task failures, so
tasks with passing QA verdicts and committed work were recorded as failed.
"""

import os
import tempfile
import unittest
from pathlib import Path

from aet import queue as queue_lib


class TestLeaseOwnership(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.queue_file = str(Path(self._tmp.name) / "aet-queue")
        self._saved_run_id = os.environ.pop("AET_RUN_ID", None)

        def _restore():
            if self._saved_run_id is None:
                os.environ.pop("AET_RUN_ID", None)
            else:
                os.environ["AET_RUN_ID"] = self._saved_run_id

        self.addCleanup(_restore)

    def test_acquire_refuses_a_live_lease_held_by_another_run(self):
        """The defect: acquisition used to overwrite the incumbent."""
        queue_lib.acquire_lease(self.queue_file, "run-A")

        with self.assertRaises(queue_lib.LeaseHeldError) as ctx:
            queue_lib.acquire_lease(self.queue_file, "run-B")

        self.assertEqual(ctx.exception.run_id, "run-A")
        # Ownership is unchanged: the incumbent can still write.
        self.assertEqual(queue_lib.read_lease(self.queue_file)["run_id"], "run-A")

    def test_incumbent_can_still_write_after_a_refused_acquisition(self):
        queue_lib.acquire_lease(self.queue_file, "run-A")
        with self.assertRaises(queue_lib.LeaseHeldError):
            queue_lib.acquire_lease(self.queue_file, "run-B")

        os.environ["AET_RUN_ID"] = "run-A"
        queue_lib.check_lease(self.queue_file)  # must not raise

    def test_same_run_may_reacquire_its_own_lease(self):
        queue_lib.acquire_lease(self.queue_file, "run-A")
        os.environ["AET_RUN_ID"] = "run-A"
        lease = queue_lib.acquire_lease(self.queue_file, "run-A")
        self.assertEqual(lease["run_id"], "run-A")

    def test_force_overrides_a_live_lease(self):
        queue_lib.acquire_lease(self.queue_file, "run-A")
        lease = queue_lib.acquire_lease(self.queue_file, "run-B", force=True)
        self.assertEqual(lease["run_id"], "run-B")

    def test_stale_lease_from_a_dead_pid_is_reclaimed(self):
        """A dead run must not block the queue forever."""
        queue_lib.acquire_lease(self.queue_file, "run-dead")
        path = queue_lib.lease_path(self.queue_file)
        import json

        data = json.loads(Path(path).read_text(encoding="utf-8"))
        data["pid"] = 2**30  # a pid that does not exist
        Path(path).write_text(json.dumps(data), encoding="utf-8")

        lease = queue_lib.acquire_lease(self.queue_file, "run-new")
        self.assertEqual(lease["run_id"], "run-new")

    def test_lease_refusal_has_a_distinct_exit_code(self):
        """A refusal must be distinguishable from a failure of the work."""
        self.assertNotEqual(queue_lib.LEASE_HELD_EXIT_CODE, 0)
        self.assertNotEqual(queue_lib.LEASE_HELD_EXIT_CODE, 1)


class TestRefusalIsNotAWorkFailure(unittest.TestCase):
    """_record_stage must not report a refused write as failed work."""

    @staticmethod
    def _mock_run(set_stage_rc: int, stderr: str):
        """Answer the ref-existence probe, then the set-stage write."""

        class _Result:
            def __init__(self, returncode, stderr=""):
                self.returncode = returncode
                self.stdout = ""
                self.stderr = stderr

        def run(cmd, **kwargs):
            if "rev-parse" in cmd:
                return _Result(0)  # the task ref exists
            return _Result(set_stage_rc, stderr)

        return run

    def test_record_stage_raises_lease_refused_on_refusal(self):
        from unittest.mock import patch

        from aet.cli import orchestrator

        task = {"id": "t1", "stage": "implemented"}
        mock = self._mock_run(
            queue_lib.LEASE_HELD_EXIT_CODE,
            "\u26d4 Refusing to mutate the queue: owned by run run-B.",
        )

        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(orchestrator.subprocess, "run", side_effect=mock):
                with self.assertRaises(orchestrator.LeaseRefusedError) as ctx:
                    orchestrator._record_stage(task, "qa-complete", tmp)

        self.assertIn("qa-complete", str(ctx.exception))
        # The stage was not claimed as recorded.
        self.assertEqual(task["stage"], "implemented")

    def test_record_stage_still_returns_false_for_a_real_failure(self):
        """A genuine write failure keeps its existing behavior."""
        from unittest.mock import patch

        from aet.cli import orchestrator

        task = {"id": "t1", "stage": "implemented"}
        mock = self._mock_run(1, "Task not found: t1")

        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(orchestrator.subprocess, "run", side_effect=mock):
                self.assertFalse(orchestrator._record_stage(task, "qa-complete", tmp))
        self.assertEqual(task["stage"], "implemented")


if __name__ == "__main__":
    unittest.main()
