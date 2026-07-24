"""Tests for aet-work read-side commands (status, next)."""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.cli._helpers import run_typer

_REPO_ROOT = Path(__file__).parents[2]
_STATUS_PY = _REPO_ROOT / "src" / "aet" / "cli" / "status.py"

aet = importlib.import_module("aet.cli.main")


def _write_json_file(data) -> str:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data, f)
        return f.name


def _make_queue(tasks: list[dict]) -> str:
    return _write_json_file(tasks)


def _make_history(tasks: list[dict]) -> str:
    path = Path(tempfile.mkstemp(suffix=".jsonl")[1])
    with open(path, "w", encoding="utf-8") as f:
        for task in tasks:
            json.dump(task, f)
            f.write("\n")
    return str(path)


def _make_plans_dir(plan_names: list[str]) -> tempfile.TemporaryDirectory:
    tmp = tempfile.TemporaryDirectory()
    for name in plan_names:
        stem = Path(name).stem
        Path(tmp.name, name).write_text(
            f"---\nid: {stem}\nstatus: queued\n---\n\n# Plan\n",
            encoding="utf-8",
        )
    return tmp


def _resolve_plan_files(tasks: list[dict], plans_dir: str) -> list[dict]:
    """Replace bare plan filenames with absolute paths inside plans_dir."""
    resolved = []
    for task in tasks:
        copy = dict(task)
        plan_file = copy.get("plan_file", "")
        if plan_file and not Path(plan_file).is_absolute():
            copy["plan_file"] = str(Path(plans_dir) / Path(plan_file).name)
        resolved.append(copy)
    return resolved


class TestStatusStoredState(unittest.TestCase):
    def test_counts_use_stored_state(self):
        """status uses stored state for the summary counts."""
        plans_dir_tmp = _make_plans_dir(["t1.md", "t2.md"])
        plans_dir = plans_dir_tmp.name
        queue_file = _make_queue(_resolve_plan_files([
            {"id": "t1", "state": "ready", "title": "One", "plan_file": "docs/plans/t1.md"},
            {"id": "t2", "state": "blocked", "title": "Two", "plan_file": "docs/plans/t2.md"},
        ], plans_dir))
        history_file = _make_history([])

        result = run_typer(aet.app, [
            "status",
            "--queue-file", queue_file,
            "--history-file", history_file,
            "--plans-dir", plans_dir,
        ])

        self.assertEqual(result.exit_code, 0)
        output = result.stdout
        self.assertIn("ready: 1", output)
        self.assertIn("blocked: 1", output)

    def test_counts_include_awaiting_merge(self):
        """status summary includes awaiting_merge tasks."""
        plans_dir_tmp = _make_plans_dir(["t1.md"])
        plans_dir = plans_dir_tmp.name
        queue_file = _make_queue(_resolve_plan_files([
            {"id": "t1", "state": "awaiting_merge", "title": "Done-ish", "plan_file": "docs/plans/t1.md"},
        ], plans_dir))
        history_file = _make_history([])

        result = run_typer(aet.app, [
            "status",
            "--queue-file", queue_file,
            "--history-file", history_file,
            "--plans-dir", plans_dir,
        ])

        self.assertEqual(result.exit_code, 0)
        output = result.stdout
        self.assertIn("awaiting_merge: 1", output)

    def test_failed_tasks_reported_from_stored_status(self):
        """Failed tasks are reported from stored state."""
        plans_dir_tmp = _make_plans_dir(["t1.md"])
        plans_dir = plans_dir_tmp.name
        queue_file = _make_queue(_resolve_plan_files([
            {"id": "t1", "state": "failed", "title": "Broke", "plan_file": "docs/plans/t1.md"},
        ], plans_dir))
        history_file = _make_history([])

        result = run_typer(aet.app, [
            "status",
            "--queue-file", queue_file,
            "--history-file", history_file,
            "--plans-dir", plans_dir,
        ])

        self.assertEqual(result.exit_code, 0)
        output = result.stdout
        self.assertIn("Failed tasks:", output)
        self.assertIn("Broke", output)

    def test_next_ready_tasks_use_stored_state(self):
        """The 'Next ready tasks' list uses stored state."""
        plans_dir_tmp = _make_plans_dir(["t1.md", "t2.md"])
        plans_dir = plans_dir_tmp.name
        queue_file = _make_queue(_resolve_plan_files([
            {"id": "t1", "state": "ready", "title": "One", "plan_file": "docs/plans/t1.md"},
            {"id": "t2", "state": "blocked", "title": "Two", "plan_file": "docs/plans/t2.md"},
        ], plans_dir))
        history_file = _make_history([])

        result = run_typer(aet.app, [
            "status",
            "--queue-file", queue_file,
            "--history-file", history_file,
            "--plans-dir", plans_dir,
        ])

        self.assertEqual(result.exit_code, 0)
        output = result.stdout
        self.assertIn("Next ready tasks:", output)
        self.assertIn("One", output)
        ready_section = output.split("Next ready tasks:")[1].split("\n\n")[0]
        self.assertNotIn("Two", ready_section)

    def test_works_when_queue_file_is_missing(self):
        """status exits cleanly and hides empty sections when files are missing."""
        plans_dir_tmp = _make_plans_dir([])
        plans_dir = plans_dir_tmp.name
        queue_file = str(Path(tempfile.mkdtemp()) / "missing-queue.json")
        history_file = str(Path(tempfile.mkdtemp()) / "missing-history.jsonl")

        result = run_typer(aet.app, [
            "status",
            "--queue-file", queue_file,
            "--history-file", history_file,
            "--plans-dir", plans_dir,
        ])

        self.assertEqual(result.exit_code, 0)
        output = result.stdout
        self.assertIn("No plan drift detected", output)
        self.assertIn("Queue is empty.", output)
        self.assertNotIn("Queue summary:", output)
        self.assertIn("No ready tasks.", output)
        self.assertNotIn("Next ready tasks:", output)
        self.assertNotIn("None.", output)

    def test_plan_drift_is_informational(self):
        """status exits 0 and still reports active queue state when plan drift exists."""
        plans_dir_tmp = _make_plans_dir(["orphan.md", "t1.md"])
        plans_dir = plans_dir_tmp.name
        queue_file = _make_queue(_resolve_plan_files([
            {"id": "t1", "state": "ready", "title": "One", "plan_file": "docs/plans/t1.md"},
        ], plans_dir))
        history_file = _make_history([])

        result = run_typer(aet.app, [
            "status",
            "--queue-file", queue_file,
            "--history-file", history_file,
            "--plans-dir", plans_dir,
        ])

        self.assertEqual(result.exit_code, 0)
        output = result.stdout
        self.assertIn("Plan drift detected", output)
        self.assertIn("ready: 1", output)
        self.assertIn("Next ready tasks:", output)
        self.assertIn("One", output)

    def test_status_binary_displays_canonical_state(self):
        """status summary uses canonical state labels, not legacy status strings."""
        plans_dir_tmp = _make_plans_dir(["t1.md", "t2.md", "t3.md"])
        plans_dir = plans_dir_tmp.name
        queue_file = _make_queue(_resolve_plan_files([
            {"id": "t1", "state": "ready", "title": "One", "plan_file": "docs/plans/t1.md"},
            {"id": "t2", "state": "in_progress", "title": "Two", "plan_file": "docs/plans/t2.md"},
            {"id": "t3", "state": "blocked", "title": "Three", "plan_file": "docs/plans/t3.md"},
        ], plans_dir))
        history_file = _make_history([])

        result = run_typer(aet.app, [
            "status",
            "--queue-file", queue_file,
            "--history-file", history_file,
            "--plans-dir", plans_dir,
        ])

        self.assertEqual(result.exit_code, 0)
        output = result.stdout
        self.assertIn("ready: 1", output)
        self.assertIn("in_progress: 1", output)
        self.assertIn("blocked: 1", output)
        self.assertNotIn("unblocked: 1", output)
        self.assertNotIn("in-progress: 1", output)


class TestStatusJson(unittest.TestCase):
    def test_json_summary_counts_and_human_output_suppressed(self):
        """status --json prints a machine-readable summary and no human report."""
        plans_dir_tmp = _make_plans_dir(["t1.md", "t2.md"])
        plans_dir = plans_dir_tmp.name
        queue_file = _make_queue(_resolve_plan_files([
            {"id": "t1", "state": "ready", "title": "One", "plan_file": "docs/plans/t1.md"},
            {"id": "t2", "state": "blocked", "title": "Two", "plan_file": "docs/plans/t2.md"},
        ], plans_dir))
        history_file = _make_history([])

        result = run_typer(aet.app, [
            "status",
            "--json",
            "--queue-file", queue_file,
            "--history-file", history_file,
            "--plans-dir", plans_dir,
        ])

        self.assertEqual(result.exit_code, 0)
        output = result.stdout
        payload = json.loads(output)
        self.assertEqual(payload["summary"]["ready"], 1)
        self.assertEqual(payload["summary"]["blocked"], 1)
        self.assertNotIn("Queue summary", output)
        self.assertNotIn("Next ready tasks", output)
        self.assertNotIn("plan drift", output.lower())

    def test_json_tasks_carry_projection_fields(self):
        """Each task entry carries id/state/stage/blocked_by/pending_blockers/plan_file."""
        plans_dir_tmp = _make_plans_dir(["t1.md"])
        plans_dir = plans_dir_tmp.name
        queue_file = _make_queue(_resolve_plan_files([
            {
                "id": "t1",
                "state": "blocked",
                "stage": "plan-approved",
                "title": "One",
                "plan_file": "docs/plans/t1.md",
                "blocked_by": ["t0"],
            },
        ], plans_dir))
        history_file = _make_history([])

        result = run_typer(aet.app, [
            "status",
            "--json",
            "--queue-file", queue_file,
            "--history-file", history_file,
            "--plans-dir", plans_dir,
        ])

        self.assertEqual(result.exit_code, 0)
        payload = json.loads(result.stdout)
        self.assertEqual(len(payload["tasks"]), 1)
        entry = payload["tasks"][0]
        self.assertEqual(entry["id"], "t1")
        self.assertEqual(entry["state"], "blocked")
        self.assertEqual(entry["stage"], "plan-approved")
        self.assertEqual(entry["blocked_by"], ["t0"])
        self.assertEqual(entry["pending_blockers"], 1)
        self.assertTrue(entry["plan_file"].endswith("t1.md"))

    def test_json_queue_updated_at_from_wrapper(self):
        """queue_updated_at is projected from the queue file wrapper metadata."""
        plans_dir_tmp = _make_plans_dir(["t1.md"])
        plans_dir = plans_dir_tmp.name
        tasks = _resolve_plan_files([
            {"id": "t1", "state": "ready", "title": "One", "plan_file": "docs/plans/t1.md"},
        ], plans_dir)
        queue_file = _write_json_file({
            "queue_updated_at": "2026-07-10T12:00:00Z",
            "tasks": tasks,
        })
        history_file = _make_history([])

        result = run_typer(aet.app, [
            "status",
            "--json",
            "--queue-file", queue_file,
            "--history-file", history_file,
            "--plans-dir", plans_dir,
        ])

        self.assertEqual(result.exit_code, 0)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["queue_updated_at"], "2026-07-10T12:00:00Z")

    def test_json_output_round_trips_through_json_tool(self):
        """The real binary's --json output parses cleanly via python3 -m json.tool."""
        plans_dir_tmp = _make_plans_dir(["t1.md"])
        plans_dir = plans_dir_tmp.name
        queue_file = _make_queue(_resolve_plan_files([
            {"id": "t1", "state": "ready", "title": "One", "plan_file": "docs/plans/t1.md"},
        ], plans_dir))
        history_file = _make_history([])

        proc = subprocess.run(
            [
                sys.executable, str(_STATUS_PY),
                "--json",
                "--queue-file", queue_file,
                "--history-file", history_file,
                "--plans-dir", plans_dir,
            ],
            capture_output=True,
            text=True,
            cwd=_REPO_ROOT,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        tool = subprocess.run(
            [sys.executable, "-m", "json.tool"],
            input=proc.stdout,
            capture_output=True,
            text=True,
        )
        self.assertEqual(tool.returncode, 0, tool.stderr)
        payload = json.loads(tool.stdout)
        self.assertEqual(payload["summary"]["ready"], 1)
        self.assertEqual(payload["tasks"][0]["id"], "t1")


class TestNextStoredState(unittest.TestCase):
    def test_warns_but_picks_ready_on_plan_drift(self):
        """next warns about plan drift but still picks a stored-ready task."""
        plans_dir_tmp = _make_plans_dir(["orphan.md", "t1.md"])
        plans_dir = plans_dir_tmp.name
        queue_file = _make_queue(_resolve_plan_files([
            {"id": "t1", "state": "ready", "title": "One", "plan_file": "docs/plans/t1.md"},
        ], plans_dir))
        history_file = _make_history([])

        transition_calls = []

        def mock_run(cmd, **_kwargs):
            transition_calls.append(list(cmd))
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        with patch.object(subprocess, "run", side_effect=mock_run):
            result = run_typer(aet.app, [
                "next",
                "--queue-file", queue_file,
                "--history-file", history_file,
                "--plans-dir", plans_dir,
            ])

        self.assertEqual(result.exit_code, 0)
        self.assertTrue(
            any("t1" in c and "transition" in c and "in_progress" in c for c in transition_calls),
            f"Expected transition to in_progress for t1, got {transition_calls}",
        )
        self.assertIn("Plan drift detected", result.stdout)

    def test_picks_first_stored_ready_and_transitions(self):
        """next picks the first stored-ready task and transitions it to in_progress."""
        plans_dir_tmp = _make_plans_dir(["t1.md", "t2.md"])
        plans_dir = plans_dir_tmp.name
        queue_file = _make_queue(_resolve_plan_files([
            {"id": "t1", "state": "blocked", "title": "One", "plan_file": "docs/plans/t1.md"},
            {"id": "t2", "state": "ready", "title": "Two", "plan_file": "docs/plans/t2.md"},
        ], plans_dir))
        history_file = _make_history([])

        transition_calls = []

        def mock_run(cmd, **_kwargs):
            transition_calls.append(list(cmd))
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        with patch.object(subprocess, "run", side_effect=mock_run):
            result = run_typer(aet.app, [
                "next",
                "--queue-file", queue_file,
                "--history-file", history_file,
                "--plans-dir", plans_dir,
            ])

        self.assertEqual(result.exit_code, 0)
        self.assertTrue(
            any("t2" in c and "transition" in c and "in_progress" in c for c in transition_calls),
            f"Expected transition to in_progress for t2, got {transition_calls}",
        )

    def test_topological_order_respected(self):
        """next picks the earliest stored-ready task in topological order."""
        plans_dir_tmp = _make_plans_dir(["t1.md", "t2.md"])
        plans_dir = plans_dir_tmp.name
        queue_file = _make_queue(_resolve_plan_files([
            {"id": "t1", "state": "ready", "title": "One", "plan_file": "docs/plans/t1.md", "blocked_by": []},
            {"id": "t2", "state": "ready", "title": "Two", "plan_file": "docs/plans/t2.md", "blocked_by": ["t1"]},
        ], plans_dir))
        history_file = _make_history([])

        transition_calls = []

        def mock_run(cmd, **_kwargs):
            transition_calls.append(list(cmd))
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        with patch.object(subprocess, "run", side_effect=mock_run):
            result = run_typer(aet.app, [
                "next",
                "--queue-file", queue_file,
                "--history-file", history_file,
                "--plans-dir", plans_dir,
            ])

        self.assertEqual(result.exit_code, 0)
        self.assertTrue(
            any("t1" in c and "transition" in c and "in_progress" in c for c in transition_calls),
            f"Expected transition to in_progress for t1, got {transition_calls}",
        )


if __name__ == "__main__":
    unittest.main()
