"""Tests for the circuit breaker (nsr-03).

Per-task breaker: the same signature 3x on a single task => quarantine.
Systemic breaker: the same signature across 3 distinct tasks => stop shift.
"""

import importlib.machinery
import importlib.util
import json
import os
import subprocess
from pathlib import Path

import pytest

from aet import breaker
from aet.failure import FailureClass, classify, signature

_ORCHESTRATOR_PY = Path(__file__).parents[2] / "src" / "aet" / "cli" / "orchestrator.py"
_orchestrator_spec = importlib.util.spec_from_loader(
    "orchestrator",
    importlib.machinery.SourceFileLoader("orchestrator", str(_ORCHESTRATOR_PY)),
)
orchestrator = importlib.util.module_from_spec(_orchestrator_spec)
_orchestrator_spec.loader.exec_module(orchestrator)

pytestmark = pytest.mark.xdist_group("git-repo")


SIG_A = "sig-a" * 4
SIG_B = "sig-b" * 4


class TestPerTaskBreaker:
    """Unit tests for should_quarantine_task."""

    def test_same_signature_thrice_quarantines(self):
        """A task with the same signature 3x crosses the per-task threshold."""
        record = {"id": "t1"}
        for _ in range(breaker.PER_TASK_BREAKER_THRESHOLD):
            breaker.record_failure_signature(record, SIG_A)

        assert breaker.should_quarantine_task(record) is True

    def test_differing_signatures_do_not_quarantine(self):
        """Three different signatures do not trip the per-task breaker."""
        record = {"id": "t1"}
        breaker.record_failure_signature(record, SIG_A)
        breaker.record_failure_signature(record, SIG_B)
        breaker.record_failure_signature(record, "sig-c" * 4)

        assert breaker.should_quarantine_task(record) is False

    def test_two_of_same_is_not_quarantine(self):
        """Two identical signatures stay below the threshold."""
        record = {"id": "t1"}
        breaker.record_failure_signature(record, SIG_A)
        breaker.record_failure_signature(record, SIG_A)

        assert breaker.should_quarantine_task(record) is False


class TestSystemicBreaker:
    """Unit tests for systemic_tripped."""

    def test_systemic_trip_at_n_distinct_tasks(self):
        """A signature seen across N distinct tasks trips the systemic breaker."""
        tally = {}
        for i in range(breaker.SYSTEMIC_BREAKER_THRESHOLD):
            tally = breaker.update_systemic_tally(tally, f"t{i}", SIG_A)

        tripped = breaker.systemic_tripped(tally)
        assert tripped == SIG_A

    def test_systemic_not_tripped_below_threshold(self):
        """A signature seen across fewer than N tasks does not trip."""
        tally = {}
        for i in range(breaker.SYSTEMIC_BREAKER_THRESHOLD - 1):
            tally = breaker.update_systemic_tally(tally, f"t{i}", SIG_A)

        assert breaker.systemic_tripped(tally) is None

    def test_systemic_counts_distinct_task_ids(self):
        """Repeated failures from the same task only count once."""
        tally = {}
        for _ in range(breaker.SYSTEMIC_BREAKER_THRESHOLD + 2):
            tally = breaker.update_systemic_tally(tally, "t1", SIG_A)

        assert breaker.systemic_tripped(tally) is None

    def test_systemic_multiple_signatures(self):
        """Only the signature reaching threshold is reported."""
        tally = {}
        tally = breaker.update_systemic_tally(tally, "t1", SIG_A)
        tally = breaker.update_systemic_tally(tally, "t2", SIG_B)
        tally = breaker.update_systemic_tally(tally, "t3", SIG_B)

        assert breaker.systemic_tripped(tally) is None
        tally = breaker.update_systemic_tally(tally, "t4", SIG_B)
        assert breaker.systemic_tripped(tally) == SIG_B


class TestCanceledExclusion:
    """Canceled-class failures are excluded from breaker tallies."""

    def test_canceled_excluded_from_tallies(self):
        """A canceled failure does not append to failure_signatures."""
        record = {"id": "t1"}
        failure_class = FailureClass.CANCELED

        breaker.append_failure_if_countable(record, failure_class, SIG_A)

        assert record.get("failure_signatures", []) == []

    def test_non_canceled_recorded(self):
        """A non-canceled failure appends to failure_signatures."""
        record = {"id": "t1"}
        breaker.append_failure_if_countable(record, FailureClass.DESIGN, SIG_A)

        assert len(record["failure_signatures"]) == 1
        assert record["failure_signatures"][0]["signature"] == SIG_A


class TestBreakerStore:
    """Integration tests for refs/aet/breaker persistence."""

    @pytest.fixture
    def git_repo(self, tmp_path):
        """Create a git repo with an initial commit."""
        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        (repo / "file.txt").write_text("init")
        subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "init"],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        return repo

    def test_breaker_counts_persist_across_reload(self, git_repo):
        """The systemic tally survives a store save/load cycle via git refs."""
        store = breaker.BreakerStore(str(git_repo))
        tally = {}
        for i in range(breaker.SYSTEMIC_BREAKER_THRESHOLD):
            tally = breaker.update_systemic_tally(tally, f"t{i}", SIG_A)

        store.save(tally)
        reloaded = store.load()

        assert breaker.systemic_tripped(reloaded) == SIG_A

    def test_store_load_missing_returns_empty(self, git_repo):
        """Loading before any breaker ref exists returns an empty tally."""
        store = breaker.BreakerStore(str(git_repo))
        assert store.load() == {}

    def test_store_update_preserves_existing(self, git_repo):
        """Saving again merges with existing signatures."""
        store = breaker.BreakerStore(str(git_repo))
        store.save({SIG_A: {"t1", "t2"}})
        store.save({SIG_A: {"t1", "t2", "t3"}})

        reloaded = store.load()
        assert len(reloaded[SIG_A]) == 3

    def test_store_clear_removes_ref(self, git_repo):
        """Clearing an existing breaker deletes the ref and returns True."""
        store = breaker.BreakerStore(str(git_repo))
        store.save({SIG_A: {"t1", "t2", "t3"}})
        assert store.load() != {}

        result = store.clear()
        assert result is True
        assert store.load() == {}
        assert store._ref_sha(breaker.BREAKER_REF) is None

    def test_store_clear_when_missing_returns_false(self, git_repo):
        """Clearing when no breaker ref exists returns False."""
        store = breaker.BreakerStore(str(git_repo))
        assert store.clear() is False

    def test_store_reset_alias_for_clear(self, git_repo):
        """reset() is an alias for clear()."""
        store = breaker.BreakerStore(str(git_repo))
        store.save({SIG_A: {"t1", "t2", "t3"}})
        assert store.reset() is True
        assert store.load() == {}


class TestOrchestratorBreakerWiring:
    """Integration tests for the orchestrator finalize/batch wiring."""

    def test_finalize_failure_records_signature(self, tmp_path):
        """A failed task has its failure signature recorded on the record."""
        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True, capture_output=True)
        (repo / "file.txt").write_text("init")
        subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)

        backend = orchestrator._make_backend(
            str(repo / "aet-queue")
        )
        task = {
            "id": "t1",
            "state": "in_progress",
            "plan_file": str(repo / "plan.md"),
        }
        backend.save([task])

        tail = "AssertionError: expected 2 but got 3"
        stage = "implement"
        sig = signature(stage=stage, tail=tail)
        failure_class = classify(
            exit_code=1,
            tail=tail,
            stage=stage,
            verdict_recorded=False,
            shutdown=False,
            killed_by_timeout=False,
        )

        orchestrator._record_failure_on_task(
            backend, task, failure_class, stage, tail
        )

        assert task["failure_signatures"][-1]["signature"] == sig

    def test_third_identical_gate_failure_quarantines_task(self, tmp_path):
        """The third identical gate failure trips the per-task breaker and quarantines the task."""
        from aet import telemetry

        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
        (repo / "file.txt").write_text("init")
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo, check=True)
        subprocess.run(["git", "update-ref", "refs/remotes/origin/main", "HEAD"], cwd=repo, check=True)

        queue_file = str(repo / "queue.json")
        backend = orchestrator._make_backend(queue_file)
        task = {
            "id": "t1",
            "title": "Task 1",
            "state": "in_progress",
            "failure_signatures": [],
        }
        backend.save([task])

        logger = telemetry.RunLogger(str(repo), run_id="r-breaker")

        # Simulate 3 identical gate failures (missing verdict for qa)
        for _ in range(3):
            passed = orchestrator._require_passing_verdict(
                "t1",
                "qa",
                str(repo),
                "docs/plans/t1.md",
                "qa-complete",
                logger,
                task=task,
                backend=backend,
            )
            assert passed is False

        assert len(task["failure_signatures"]) == 3
        assert breaker.should_quarantine_task(task) is True

        deltas = orchestrator._finalize_task(
            backend,
            queue_file,
            "t1",
            ret=1,
            repo_root=str(repo),
        )

        assert deltas["failures"] == 1
        assert deltas["stop_spawn"] is True
        data = backend.load()
        task_after = next(t for t in data["queue"] if t["id"] == "t1")
        assert task_after["state"] == "quarantined"

    def test_finalize_canceled_does_not_record(self, tmp_path):
        """A canceled task does not get a failure signature."""
        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True, capture_output=True)
        (repo / "file.txt").write_text("init")
        subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)

        backend = orchestrator._make_backend(
            str(repo / "aet-queue")
        )
        task = {"id": "t1", "state": "in_progress"}
        backend.save([task])

        orchestrator._record_failure_on_task(
            backend,
            task,
            FailureClass.CANCELED,
            "implement",
            "shutdown requested",
        )

        assert "failure_signatures" not in task

    def test_three_operator_stops_do_not_quarantine_or_raise_systemic_tally(self, tmp_path):
        """Three operator stops of one task neither quarantine it nor raise the systemic tally."""
        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True, capture_output=True)
        (repo / "file.txt").write_text("init")
        subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)

        queue_file = str(repo / "aet-queue")
        backend = orchestrator._make_backend(queue_file)
        task = {"id": "t1", "state": "in_progress", "failure_signatures": []}
        backend.save([task])

        systemic_tally: dict[str, set[str]] = {}
        for _ in range(3):
            # Task is spawned into in_progress
            task = next(x for x in backend.load()["queue"] if x["id"] == "t1")
            task["state"] = "in_progress"
            backend.save([task])

            deltas = orchestrator._finalize_task(
                backend,
                queue_file,
                "t1",
                ret=-1,
                repo_root=str(repo),
                canceled=True,
            )
            assert deltas["failures"] == 0
            assert deltas["stop_spawn"] is False
            queue = backend.load()["queue"]
            t = next(x for x in queue if x["id"] == "t1")
            assert t["state"] == "ready"
            assert t.get("failure_signatures") == []
            assert not breaker.should_quarantine_task(t)

        assert systemic_tally == {}

    def test_systemic_breaker_stops_spawn_in_batch(self, tmp_path):
        """run_batch stops spawning once the systemic breaker trips."""
        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        (repo / "file.txt").write_text("init")
        subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "init"],
            cwd=repo,
            check=True,
            capture_output=True,
        )

        queue_file = str(repo / ".agents" / "aet-queue")
        os.makedirs(os.path.dirname(queue_file), exist_ok=True)
        backend = orchestrator._make_backend(queue_file)

        tail = "AssertionError: deterministic"
        stage = "implement"
        sig = signature(stage=stage, tail=tail)

        tasks = []
        for i in range(breaker.SYSTEMIC_BREAKER_THRESHOLD):
            tasks.append(
                {
                    "id": f"t{i}",
                    "state": "failed",
                    "failure_signatures": [{"signature": sig}],
                }
            )
        # One more ready task that should never be spawned.
        tasks.append({"id": "victim", "state": "ready"})
        backend.save(tasks)

        tally = {}
        for t in tasks[: breaker.SYSTEMIC_BREAKER_THRESHOLD]:
            tally = breaker.update_systemic_tally(tally, t["id"], sig)

        store = breaker.BreakerStore(str(repo))
        store.save(tally)

        # run_batch with max_jobs=0 ensures no tasks are spawned; the loop should
        # still observe the systemic breaker and exit cleanly.
        args = orchestrator.argparse.Namespace(
            queue_file=queue_file,
            repo_root=str(repo),
            max_jobs=0,
            isolation="minimal",
            task_timeout=3600,
            heartbeat_interval=60,
            on_failure="continue",
        )

        class FakeAdapter:
            name = "fake"
            bin = "fake"

        exit_code = orchestrator.run_batch(args, FakeAdapter())
        # A tripped systemic breaker is a controlled safety stop; the batch
        # returns non-zero so the caller knows the shift did not complete.
        assert exit_code == 1

        # The ready victim should remain ready (not spawned and not failed).
        queue = backend.load()["queue"]
        victim = next(t for t in queue if t["id"] == "victim")
        assert victim["state"] == "ready"

    def test_epic_mismatch_does_not_count_as_failure(self, tmp_path):
        """Task 5 (R-9): Epic mismatch halt leaves per-task and systemic breaker tallies unchanged."""
        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        subprocess.run(
            ["git", "-C", str(repo), "config", "user.email", "test@example.com"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(repo), "config", "user.name", "Test User"],
            check=True,
        )
        (repo / "README.md").write_text("# test", encoding="utf-8")
        subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
        subprocess.run(
            ["git", "-C", str(repo), "commit", "-q", "-m", "initial"],
            check=True,
        )
        subprocess.run(["git", "-C", str(repo), "branch", "-M", "main"], check=True)

        config_file = repo / ".agents" / "aet-config.json"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(
            json.dumps(
                {
                    "trunk_branch": "main",
                    "integration_branch": "epic-02",
                    "integration_mode": "single-pr",
                }
            ),
            encoding="utf-8",
        )

        queue_file = str(repo / ".agents" / "aet-queue")
        backend = orchestrator._make_backend(queue_file)
        task = {
            "id": "t1",
            "state": "ready",
            "integration_branch": "epic-01",
        }
        backend.save([task])

        store = breaker.BreakerStore(str(repo))
        assert store.load() == {}

        args = orchestrator.argparse.Namespace(
            queue_file=queue_file,
            repo_root=str(repo),
            max_jobs=1,
            isolation="minimal",
            task_timeout=3600,
            heartbeat_interval=60,
            on_failure="continue",
            cli_bin=None,
            base=None,
        )

        class FakeAdapter:
            name = "fake"
            bin = "fake"

        exit_code = orchestrator.run_batch(args, FakeAdapter())
        assert exit_code == 1

        # Check breaker store tally is still empty (no failure recorded)
        assert store.load() == {}

        # Check task record has no failure signatures
        queue = backend.load()["queue"]
        t1 = next(t for t in queue if t["id"] == "t1")
        assert "failure_signatures" not in t1 or not t1["failure_signatures"]

    def test_three_skips_do_not_trip_systemic_breaker(self, tmp_path, capsys):
        """R-6, R-9: three skipped tasks add no failure and leave the breaker untripped."""
        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
        subprocess.run(
            ["git", "-C", str(repo), "config", "user.email", "test@example.com"], check=True
        )
        subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test User"], check=True)
        (repo / "README.md").write_text("# test", encoding="utf-8")
        subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "initial"], check=True)
        config_file = repo / ".agents" / "aet-config.json"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(
            json.dumps(
                {
                    "trunk_branch": "main",
                    "integration_branch": "epic-02",
                    "integration_mode": "single-pr",
                }
            ),
            encoding="utf-8",
        )
        queue_file = str(repo / ".agents" / "aet-queue")
        backend = orchestrator._make_backend(queue_file)
        backend.save(
            [
                {"id": f"t{i}", "state": "ready", "integration_branch": "epic-01"}
                for i in range(breaker.SYSTEMIC_BREAKER_THRESHOLD)
            ]
        )
        store = breaker.BreakerStore(str(repo))
        args = orchestrator.argparse.Namespace(
            queue_file=queue_file,
            repo_root=str(repo),
            max_jobs=1,
            isolation="minimal",
            task_timeout=3600,
            heartbeat_interval=60,
            on_failure="continue",
            cli_bin=None,
            base=None,
        )

        class FakeAdapter:
            name = "fake"
            bin = "fake"

        exit_code = orchestrator.run_batch(args, FakeAdapter())

        output = capsys.readouterr().out
        assert exit_code == 1
        assert breaker.systemic_tripped(store.load()) is None
        assert "Failed:    0" in output
        assert f"Skipped:   {breaker.SYSTEMIC_BREAKER_THRESHOLD}" in output
        states = {t["id"]: t["state"] for t in backend.load()["queue"]}
        assert set(states.values()) == {"ready"}

    def test_attempt_cap_quarantines_after_five_failures_with_different_signatures(
        self, tmp_path, capsys
    ):
        """R-6, R-7: A task that fails 5 times with different signatures is quarantined on the 5th failure."""
        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        (repo / "file.txt").write_text("init")
        subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)

        queue_file = str(repo / "queue.json")
        backend = orchestrator._make_backend(queue_file)
        task = {
            "id": "t1",
            "title": "Task 1",
            "state": "in_progress",
            "failure_signatures": [],
        }
        backend.save([task])
        attempt_counts = {}

        # 4 distinct failures should be requeued
        for i in range(4):
            orchestrator._record_failure_on_task(
                backend,
                task,
                FailureClass.ENVIRONMENT,
                f"stage-{i}",
                f"unique error tail {i}",
            )
            deltas = orchestrator._finalize_task(
                backend,
                queue_file,
                "t1",
                ret=1,
                repo_root=str(repo),
                attempt_counts=attempt_counts,
            )
            assert deltas["stop_spawn"] is False
            data = backend.load()
            task = next(t for t in data["queue"] if t["id"] == "t1")
            assert task["state"] == "ready"

        # 5th failure with yet another signature hits the attempt cap
        orchestrator._record_failure_on_task(
            backend,
            task,
            FailureClass.ENVIRONMENT,
            "stage-4",
            "unique error tail 4",
        )
        deltas = orchestrator._finalize_task(
            backend,
            queue_file,
            "t1",
            ret=1,
            repo_root=str(repo),
            attempt_counts=attempt_counts,
        )

        assert deltas["failures"] == 1
        assert deltas["stop_spawn"] is True
        data = backend.load()
        task = next(t for t in data["queue"] if t["id"] == "t1")
        assert task["state"] == "quarantined"

        output = capsys.readouterr().out
        cap = breaker.MAX_TASK_ATTEMPTS_PER_RUN
        assert f"t1 reached the attempt cap ({cap} of {cap}); quarantined" in output

    def test_throttled_failure_followed_by_four_others_does_not_quarantine(
        self, tmp_path
    ):
        """R-6: A throttled failure followed by four other failures does not hit the cap."""
        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        (repo / "file.txt").write_text("init")
        subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)

        queue_file = str(repo / "queue.json")
        backend = orchestrator._make_backend(queue_file)
        task = {
            "id": "t1",
            "title": "Task 1",
            "state": "in_progress",
            "failure_signatures": [],
        }
        backend.save([task])
        attempt_counts = {}

        # 1 throttled failure
        orchestrator._record_failure_on_task(
            backend,
            task,
            FailureClass.THROTTLED,
            "implement",
            "rate limit exceeded",
        )
        deltas = orchestrator._finalize_task(
            backend,
            queue_file,
            "t1",
            ret=1,
            repo_root=str(repo),
            attempt_counts=attempt_counts,
        )
        assert attempt_counts.get("t1", 0) == 0
        data = backend.load()
        task = next(t for t in data["queue"] if t["id"] == "t1")
        assert task["state"] == "ready"

        # Followed by 4 other distinct failures
        for i in range(4):
            orchestrator._record_failure_on_task(
                backend,
                task,
                FailureClass.ENVIRONMENT,
                f"stage-{i}",
                f"unique error tail {i}",
            )
            deltas = orchestrator._finalize_task(
                backend,
                queue_file,
                "t1",
                ret=1,
                repo_root=str(repo),
                attempt_counts=attempt_counts,
            )
            data = backend.load()
            task = next(t for t in data["queue"] if t["id"] == "t1")

        assert attempt_counts["t1"] == 4
        assert task["state"] == "ready"
        assert deltas["stop_spawn"] is False



if __name__ == "__main__":
    pytest.main([__file__])
