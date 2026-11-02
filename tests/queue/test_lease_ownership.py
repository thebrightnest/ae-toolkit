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

    def test_lease_refusal_writes_summary_with_reason(self):
        """R-16: a lease refusal writes last-run.json with reason: lease_refused and tasks_failed: 0."""
        import json
        import subprocess
        from unittest.mock import MagicMock, patch

        from aet import telemetry
        from aet.backends.git_refs_backend import GitRefsBackend
        from aet.cli import orchestrator

        repo_dir = Path(self._tmp.name) / "lease_refusal_repo"
        repo_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init", "-q", str(repo_dir)], check=True)
        subprocess.run(["git", "-C", str(repo_dir), "config", "user.email", "t@example.com"], check=True)
        subprocess.run(["git", "-C", str(repo_dir), "config", "user.name", "T"], check=True)
        (repo_dir / "README.md").write_text("hello", encoding="utf-8")
        subprocess.run(["git", "-C", str(repo_dir), "add", "."], check=True)
        subprocess.run(["git", "-C", str(repo_dir), "commit", "-q", "-m", "init"], check=True)
        subprocess.run(["git", "-C", str(repo_dir), "update-ref", "refs/remotes/origin/main", "HEAD"], check=True)

        q_file = str(repo_dir / ".agents" / "aet-queue")
        h_file = str(repo_dir / ".agents" / "work-history.jsonl")
        backend = GitRefsBackend(queue_file=q_file, history_file=h_file, repo_root=str(repo_dir))
        backend.save([{"id": "t1", "state": "ready", "title": "t1"}])

        archive_dir = Path(self._tmp.name) / "archive"
        archive_dir.mkdir(parents=True, exist_ok=True)
        env = {
            "AET_TELEMETRY_ARCHIVE_DIR": str(archive_dir),
            "AET_PROJECT_ID": "test-repo/main",
        }
        with patch.dict(os.environ, env):
            # A live run holds the lease and wrote its last-run.json
            queue_lib.acquire_lease(q_file, "run-live")
            live_logger = telemetry.RunLogger(repo_dir, run_id="run-live")
            live_summary_record = telemetry.run_summary_record(
                run_id="run-live",
                start_time="2026-06-20T00:00:00Z",
                end_time="2026-06-20T00:05:00Z",
                tasks_spawned=1,
                tasks_succeeded=1,
                tasks_failed=0,
                exit_code=0,
            )
            live_logger.write_last_run(live_summary_record)
            live_last_run_bytes = (live_logger.run_dir / "last-run.json").read_bytes()

            # A second run attempts to acquire lease via run_batch
            args = MagicMock()
            args.queue_file = q_file
            args.repo_root = str(repo_dir)
            args.run_id = "run-refused"
            args.max_jobs = 1
            args.force = False
            fake_adapter = MagicMock()
            fake_adapter.bin = "fake"

            rc = orchestrator.run_batch(args, fake_adapter)
            self.assertEqual(rc, 1)

            # Refused run's summary
            refused_logger = telemetry.RunLogger(repo_dir, run_id="run-refused")
            refused_last_run = json.loads((refused_logger.run_dir / "last-run.json").read_text(encoding="utf-8"))
            self.assertEqual(refused_last_run["reason"], "lease_refused")
            self.assertEqual(refused_last_run["tasks_spawned"], 0)
            self.assertEqual(refused_last_run["tasks_failed"], 0)
            self.assertEqual(refused_last_run["outcome"], "failure")
            self.assertEqual(refused_last_run["exit_code"], 1)

            # Live run's last-run.json is unchanged
            self.assertEqual((live_logger.run_dir / "last-run.json").read_bytes(), live_last_run_bytes)

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

    def test_linked_worktree_acquire_refuses_when_held_by_sibling_worktree(self):
        """With a lease held from one linked worktree, acquire_lease from a second worktree raises."""
        import subprocess
        main_repo = Path(self._tmp.name) / "repo"
        main_repo.mkdir()
        subprocess.run(["git", "init", "-q", str(main_repo)], check=True)
        subprocess.run(["git", "-C", str(main_repo), "config", "user.email", "t@example.com"], check=True)
        subprocess.run(["git", "-C", str(main_repo), "config", "user.name", "T"], check=True)
        (main_repo / "README.md").write_text("main", encoding="utf-8")
        subprocess.run(["git", "-C", str(main_repo), "add", "."], check=True)
        subprocess.run(["git", "-C", str(main_repo), "commit", "-q", "-m", "init"], check=True)

        wt_dir = Path(self._tmp.name) / "linked-wt"
        subprocess.run(
            ["git", "-C", str(main_repo), "worktree", "add", "-q", str(wt_dir), "-b", "wt-branch"],
            check=True,
        )

        q1 = str(main_repo / ".agents" / "aet-queue")
        q2 = str(wt_dir / ".agents" / "aet-queue")

        # Acquire lease from main_repo
        queue_lib.acquire_lease(q1, "run-primary")

        # Attempt to acquire lease from linked worktree
        with self.assertRaises(queue_lib.LeaseHeldError) as ctx:
            queue_lib.acquire_lease(q2, "run-secondary")

        self.assertEqual(ctx.exception.run_id, "run-primary")
        self.assertIn("run-primary", str(ctx.exception))
        self.assertIn(str(main_repo.resolve()), str(ctx.exception))

    def test_live_lease_at_legacy_path_blocks_acquire(self):
        """A live lease at the legacy per-checkout path blocks acquire_lease."""
        import json
        import subprocess
        repo_dir = Path(self._tmp.name) / "repo-legacy"
        repo_dir.mkdir()
        subprocess.run(["git", "init", "-q", str(repo_dir)], check=True)
        qf = repo_dir / ".agents" / "aet-queue"
        qf.parent.mkdir(parents=True, exist_ok=True)
        legacy_lp = repo_dir / ".agents" / "work-queue.lease"
        legacy_lp.write_text(
            json.dumps({
                "run_id": "legacy-run",
                "pid": os.getpid(),
                "started_at": "2099-01-01T00:00:00Z",
                "checkout_path": str(repo_dir),
            }),
            encoding="utf-8",
        )

        with self.assertRaises(queue_lib.LeaseHeldError) as ctx:
            queue_lib.acquire_lease(str(qf), "new-run")

        self.assertEqual(ctx.exception.run_id, "legacy-run")
        self.assertIn("legacy-run", str(ctx.exception))


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
