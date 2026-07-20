"""Tests for the --on-failure=triage runtime path (nsr-04)."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Ensure src/aet is on the path.
from aet import failure, triage

# Load the orchestrator script (no .py extension) as a module.
_ORCHESTRATOR_BIN = Path(__file__).parent.parent / "src" / "aet" / "cli" / "orchestrator.py"
_orchestrator_loader = importlib.machinery.SourceFileLoader("orchestrator", str(_ORCHESTRATOR_BIN))
_spec = importlib.util.spec_from_loader("orchestrator", _orchestrator_loader)
orchestrator = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(orchestrator)


PER_TASK_BREAKER_THRESHOLD = 3


def _init_git_repo(repo_root: str) -> None:
    """Initialize a git repo with a clean main branch tracking origin."""
    subprocess.run(["git", "init", "-q", repo_root], check=True)
    subprocess.run(
        ["git", "-C", repo_root, "config", "user.email", "test@example.com"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", repo_root, "config", "user.name", "Test User"],
        check=True,
    )
    Path(repo_root, "README.md").write_text("# test", encoding="utf-8")
    subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
    subprocess.run(
        ["git", "-C", repo_root, "commit", "-q", "-m", "initial"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", repo_root, "update-ref", "refs/remotes/origin/main", "HEAD"],
        check=True,
    )


def _write_queue(repo_root: str, tasks: list[dict]) -> str:
    """Write a wrapper-format queue file and return its path."""
    queue_file = os.path.join(repo_root, ".agents", "work-queue.json")
    Path(queue_file).parent.mkdir(parents=True, exist_ok=True)
    with open(queue_file, "w", encoding="utf-8") as f:
        json.dump(
            {
                "queue_updated_at": "2026-06-18T00:00:00Z",
                "source_prd": "docs/prds/demo-prd.md",
                "tasks": tasks,
            },
            f,
            indent=2,
        )
    return queue_file


def _failure_entry(
    *,
    signature: str = "abc123",
    cls: failure.FailureClass = failure.FailureClass.ENVIRONMENT,
    stage: str = "implement",
    tail: str = "command not found",
) -> dict:
    """Build a failure-signatures entry as recorded by run_stage/run_stage_group."""
    return {
        "signature": signature,
        "class": cls.value,
        "stage": stage,
        "tail_preview": tail,
    }


class TestTriagePrompt(unittest.TestCase):
    def test_prompt_includes_task_stage_class_tail_and_signature(self):
        prompt = triage.build_triage_prompt(
            task_id="demo",
            stage="implement",
            failure_class=failure.FailureClass.ENVIRONMENT.value,
            tail="command not found: pyright",
            signature="abc123",
        )
        self.assertIn("demo", prompt)
        self.assertIn("implement", prompt)
        self.assertIn("environment", prompt)
        self.assertIn("command not found: pyright", prompt)
        self.assertIn("abc123", prompt)
        self.assertIn("requeue", prompt)
        self.assertIn("quarantine", prompt)


class TestTriageVerdictParser(unittest.TestCase):
    def test_parses_plain_json_line(self):
        output = '{"class": "environment", "action": "requeue"}\n'
        self.assertEqual(triage.parse_triage_verdict(output), {"action": "requeue"})

    def test_parses_json_inside_markdown_block(self):
        output = "```json\n{\"class\": \"design\", \"action\": \"quarantine\"}\n```\n"
        self.assertEqual(triage.parse_triage_verdict(output), {"action": "quarantine"})

    def test_parses_last_json_line_when_agent_adds_chatter(self):
        output = (
            "Looking at this failure, I see an assertion error.\n"
            "{\"class\": \"design\", \"action\": \"quarantine\"}\n"
        )
        self.assertEqual(triage.parse_triage_verdict(output), {"action": "quarantine"})

    def test_returns_none_for_unparseable_output(self):
        self.assertIsNone(triage.parse_triage_verdict("I think we should retry"))

    def test_returns_none_for_unknown_action(self):
        self.assertIsNone(triage.parse_triage_verdict('{\"class\": \"design\", \"action\": \"investigate\"}'))


class TestFinalizeOnFailureTriage(unittest.TestCase):
    def _run_finalize(
        self,
        repo_root: str,
        task: dict,
        *,
        ret: int = 1,
        on_failure: str = "triage",
        triage_verdict: dict | None = None,
        triage_raises: bool = False,
    ) -> tuple[dict, dict]:
        """Run _finalize_task with a patched triage session.

        Returns (deltas, task_record_after).
        """
        queue_file = _write_queue(repo_root, [task])
        backend = orchestrator._make_backend(queue_file)

        def fake_consult(*args, **kwargs):
            if triage_raises:
                raise RuntimeError("triage session crashed")
            return triage_verdict

        with patch.object(orchestrator, "_consult_triage_session", side_effect=fake_consult):
            deltas = orchestrator._finalize_task(
                backend,
                queue_file,
                task["id"],
                ret,
                repo_root=repo_root,
                on_failure=on_failure,
            )

        data = backend.load()
        task_after = next((t for t in data["queue"] if t.get("id") == task["id"]), None)
        return deltas, task_after

    def test_triage_requeues_flaky_environment(self):
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            task = {
                "id": "demo",
                "title": "Demo",
                "state": "in_progress",
                "failure_signatures": [
                    _failure_entry(
                        cls=failure.FailureClass.FLAKY,
                        tail="pytest: flaky timeout",
                    )
                ],
            }
            deltas, task_after = self._run_finalize(
                repo_root,
                task,
                triage_verdict={"action": "requeue"},
            )
            self.assertEqual(deltas["failures"], 0)
            self.assertEqual(deltas["successes"], 0)
            self.assertFalse(deltas["stop_spawn"])
            self.assertEqual(task_after["state"], "ready")

    def test_triage_quarantines_design(self):
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            task = {
                "id": "demo",
                "title": "Demo",
                "state": "in_progress",
                "failure_signatures": [
                    _failure_entry(
                        cls=failure.FailureClass.DESIGN,
                        tail="AssertionError: expected 200",
                    )
                ],
            }
            deltas, task_after = self._run_finalize(
                repo_root,
                task,
                triage_verdict={"action": "quarantine"},
            )
            self.assertEqual(deltas["failures"], 1)
            self.assertEqual(task_after["state"], "quarantined")

    def test_triage_error_falls_back_to_classifier_default(self):
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            task = {
                "id": "demo",
                "title": "Demo",
                "state": "in_progress",
                "failure_signatures": [
                    _failure_entry(
                        cls=failure.FailureClass.ENVIRONMENT,
                        tail="command not found: pyright",
                    )
                ],
            }
            deltas, task_after = self._run_finalize(
                repo_root,
                task,
                triage_verdict=None,
                triage_raises=False,
            )
            self.assertEqual(task_after["state"], "ready")

    def test_triage_requeue_bounded_by_breaker(self):
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            sig = "repeatme"
            task = {
                "id": "demo",
                "title": "Demo",
                "state": "in_progress",
                "failure_signatures": [
                    _failure_entry(signature=sig, cls=failure.FailureClass.FLAKY),
                    _failure_entry(signature=sig, cls=failure.FailureClass.FLAKY),
                    _failure_entry(signature=sig, cls=failure.FailureClass.FLAKY),
                ],
            }
            deltas, task_after = self._run_finalize(
                repo_root,
                task,
                triage_verdict={"action": "requeue"},
            )
            self.assertEqual(deltas["failures"], 1)
            self.assertEqual(task_after["state"], "quarantined")

    def test_on_failure_continue_matches_legacy(self):
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            task = {
                "id": "demo",
                "title": "Demo",
                "state": "in_progress",
                "failure_signatures": [
                    _failure_entry(cls=failure.FailureClass.DESIGN)
                ],
            }
            deltas, task_after = self._run_finalize(
                repo_root,
                task,
                on_failure="continue",
            )
            self.assertEqual(deltas["failures"], 1)
            self.assertEqual(task_after["state"], "failed")
            self.assertFalse(deltas["stop_spawn"])

    def test_on_failure_halt_stops_shift(self):
        with tempfile.TemporaryDirectory() as repo_root:
            _init_git_repo(repo_root)
            task = {
                "id": "demo",
                "title": "Demo",
                "state": "in_progress",
                "failure_signatures": [
                    _failure_entry(cls=failure.FailureClass.FLAKY)
                ],
            }
            deltas, task_after = self._run_finalize(
                repo_root,
                task,
                on_failure="halt",
            )
            self.assertEqual(deltas["failures"], 1)
            self.assertEqual(task_after["state"], "failed")
            self.assertTrue(deltas["stop_spawn"])


class TestOnFailureArgument(unittest.TestCase):
    def test_parser_defaults_to_triage(self):
        parser = orchestrator.build_parser()
        args = parser.parse_args(["--queue-file", "q.json"])
        self.assertEqual(args.on_failure, "triage")

    def test_parser_rejects_invalid_mode(self):
        parser = orchestrator.build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(["--queue-file", "q.json", "--on-failure", "ignore"])


if __name__ == "__main__":
    unittest.main()
