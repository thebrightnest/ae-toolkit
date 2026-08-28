"""A task-record write the orchestrator makes directly must survive `aet state`.

`aet state` fetches ``+refs/aet/*:refs/aet/*`` before every transition, which
force-resets local task refs to origin's copy (ADR-055). A write the
orchestrator persists without replicating it is therefore discarded by the next
transition. That is what let `pub-03` requeue 22 times while the per-task
breaker, whose threshold is 3, never counted past one
(`docs/bugs/20260828-fetch-discards-unpushed-record-writes.md`).

Shared posture is the precondition: pushes are suppressed without an in-tree
project config, so origin carries no `refs/aet/*`, the fetch has nothing to
overwrite with, and a fixture without that config cannot observe the defect.
Every test here therefore builds a repo with both a remote and a committed
config, and one test pins that premise.

The child/parent process boundary of a real batch is not reproduced: the write
and the transition that would discard it run in one process, because the loss
happens in the ref store rather than at the process boundary. What a child
writes, a fetch overwrites regardless of who runs it.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pytest

from aet import breaker
from aet.backends.base import SHARED_POSTURE
from aet.cli import orchestrator
from aet.failure import FailureClass

pytestmark = pytest.mark.xdist_group("git-repo")

# The tail is stable across attempts so every attempt produces the same
# signature: the breaker counts occurrences of one signature, not failures.
TAIL = "AssertionError: expected 2 but got 3"
STAGE = "implement"


def _shared_posture_repo(root: Path) -> tuple[Path, str, object]:
    """Build a repo with an origin remote and an in-tree config, seed one task.

    Returns ``(repo, queue_file, backend)`` with the task in ``in_progress`` and
    its pre-attempt record already pushed, which is the state the batch parent
    leaves behind before it spawns a child (``orchestrator.py:3311-3321``).
    """
    origin = root / "origin.git"
    repo = root / "repo"
    subprocess.run(["git", "init", "--bare", "-q", str(origin)], check=True)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    for key, value in (("user.email", "test@example.com"), ("user.name", "Test User")):
        subprocess.run(["git", "-C", str(repo), "config", key, value], check=True)
    (repo / "README.md").write_text("# test\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "initial"], check=True)
    subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", str(origin)], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "push", "-q", "origin", "HEAD:refs/heads/main"], check=True
    )

    agents = repo / ".agents"
    agents.mkdir()
    # An in-tree project-scope config is what resolves the posture to shared.
    (agents / "aet-config.json").write_text(
        '{"integration_mode": "pr-per-task", "integration_branch": "main"}\n',
        encoding="utf-8",
    )

    queue_file = str(agents / "aet-queue")
    backend = orchestrator._make_backend(queue_file)
    backend.save(
        [
            {
                "id": "t1",
                "state": "in_progress",
                "plan_file": "docs/plans/t1.md",
                "stage": "plan-approved",
            }
        ]
    )
    backend.push()
    return repo, queue_file, backend


def _reload(queue_file: str) -> dict:
    """Read t1 through a fresh backend, as a separate process would."""
    queue = orchestrator._make_backend(queue_file).load()["queue"]
    return next(t for t in queue if t.get("id") == "t1")


def _signatures(queue_file: str) -> list[dict]:
    return _reload(queue_file).get("failure_signatures", [])


class TestTaskRecordReplication(unittest.TestCase):
    """Direct orchestrator writes survive the state transitions that follow."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.repo, self.queue_file, self.backend = _shared_posture_repo(self.root)
        self.aet_state_bin = str(orchestrator._SCRIPT_DIR / "aet_state.py")

    def tearDown(self):
        self.tmp.cleanup()

    def _transition(self, from_state: str, to_state: str) -> None:
        result = subprocess.run(
            [
                sys.executable,
                self.aet_state_bin,
                "transition",
                "t1",
                from_state,
                to_state,
                self.queue_file,
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def _record_failure(self) -> None:
        """Record one failure the way a child session does."""
        backend = orchestrator._make_backend(self.queue_file)
        task = next(t for t in backend.load()["queue"] if t.get("id") == "t1")
        orchestrator._record_failure_on_task(
            backend, task, FailureClass.FLAKY, STAGE, TAIL
        )

    def test_the_fixture_is_in_shared_posture(self):
        """Without shared posture these tests cannot observe the defect."""
        self.assertEqual(self.backend.posture, SHARED_POSTURE)

    def test_a_failure_signature_survives_the_failed_transition(self):
        """`_mark_failed` fetches before transitioning; the write must outlive it."""
        self._record_failure()
        self.assertEqual(len(_signatures(self.queue_file)), 1)

        orchestrator._mark_failed(self.backend, self.queue_file, "t1", "in_progress")

        self.assertEqual(len(_signatures(self.queue_file)), 1)

    def test_three_attempts_accumulate_and_trip_the_breaker(self):
        """The breaker counts across attempts, which is the point of a threshold."""
        for attempt in range(breaker.PER_TASK_BREAKER_THRESHOLD):
            self._record_failure()
            orchestrator._mark_failed(self.backend, self.queue_file, "t1", "in_progress")
            if attempt < breaker.PER_TASK_BREAKER_THRESHOLD - 1:
                self._transition("failed", "ready")
                self._transition("ready", "in_progress")

        record = _reload(self.queue_file)
        self.assertEqual(
            len(record.get("failure_signatures", [])),
            breaker.PER_TASK_BREAKER_THRESHOLD,
        )
        self.assertTrue(breaker.should_quarantine_task(record))

    def test_a_direct_record_write_survives_the_failed_transition(self):
        """The loss is not specific to signatures: any direct write is at risk.

        Exercises the helper's contract with the field its production callers
        write — ``_write_task_cost`` and ``_attach_delivered_size`` — without
        standing up the telemetry archive those two read their values from.
        """
        backend = orchestrator._make_backend(self.queue_file)
        queue = backend.load()["queue"]
        next(t for t in queue if t.get("id") == "t1")["cost"] = {
            "tokens": 999,
            "usd": 1.5,
        }
        orchestrator._save_task_record(backend, queue)

        orchestrator._mark_failed(backend, self.queue_file, "t1", "in_progress")

        self.assertEqual(_reload(self.queue_file).get("cost"), {"tokens": 999, "usd": 1.5})
