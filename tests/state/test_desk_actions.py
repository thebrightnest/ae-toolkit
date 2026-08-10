"""Tests for aet-work desk actions — merge and abandon subcommands."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import io
import json
import sys
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).parents[2]
_DESK_PY = REPO_ROOT / "src" / "aet" / "cli" / "desk.py"

_desk_spec = importlib.util.spec_from_loader(
    "desk_bin", importlib.machinery.SourceFileLoader("desk_bin", str(_DESK_PY))
)
desk = importlib.util.module_from_spec(_desk_spec)
_desk_spec.loader.exec_module(desk)



def _plan_path(tmp_path: Path, plan_id: str) -> Path:
    return tmp_path / "plans" / f"{plan_id}.md"


def _write_plan(tmp_path: Path, plan_id: str, status: str = "approved") -> Path:
    plan_dir = tmp_path / "plans"
    plan_dir.mkdir(exist_ok=True)
    lines = [
        "---",
        f"id: {plan_id}",
        "size: M",
        "---",
        "",
        f"# {plan_id}",
        "",
        "_Stage: implemented_\n",
    ]
    path = _plan_path(tmp_path, plan_id)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _write_queue(tmp_path: Path, tasks: list[dict]) -> str:
    path = tmp_path / "queue.json"
    path.write_text(json.dumps(tasks), encoding="utf-8")
    return str(path)


def _write_history(tmp_path: Path) -> str:
    # aet-state derives the history file as <queue-file>.with_name('work-history.jsonl'),
    # so tests that exercise aet-state must use that filename.
    path = tmp_path / "work-history.jsonl"
    path.write_text("", encoding="utf-8")
    return str(path)


def _run_desk_action(*args: str, queue_file: str, history_file: str) -> tuple[int, str, str]:
    argv = ["desk", *args, "--queue-file", queue_file, "--history-file", history_file]
    stdout = io.StringIO()
    stderr = io.StringIO()
    with patch.object(sys, "argv", argv), redirect_stderr(stderr):
        try:
            rc = desk.main()
        except SystemExit as exc:
            rc = exc.code if isinstance(exc.code, int) else 1
    return rc, stdout.getvalue(), stderr.getvalue()


@pytest.fixture(autouse=True)
def _isolate_reports_dir(monkeypatch, tmp_path):
    """Point the evidence archive at a per-test tmp dir."""
    monkeypatch.setenv("AET_REPORTS_DIR", str(tmp_path / "reports"))


class TestMergeFailClosed:
    def test_merge_unknown_id_fails_closed_nonzero(self, tmp_path):
        plan = _write_plan(tmp_path, "t1")
        queue_file = _write_queue(
            tmp_path,
            [
                {
                    "id": "t1",
                    "state": "awaiting_merge",
                    "title": "One",
                    "plan_file": str(plan),
                    "branch": "t1-branch",
                }
            ],
        )
        history_file = _write_history(tmp_path)
        rc, _out, err = _run_desk_action(
            "merge", "unknown", queue_file=queue_file, history_file=history_file
        )
        assert rc != 0
        assert "unknown" in err.lower()

    def test_merge_non_awaiting_merge_task_fails_closed(self, tmp_path):
        plan = _write_plan(tmp_path, "t1")
        queue_file = _write_queue(
            tmp_path,
            [
                {
                    "id": "t1",
                    "state": "ready",
                    "title": "One",
                    "plan_file": str(plan),
                    "branch": "t1-branch",
                }
            ],
        )
        history_file = _write_history(tmp_path)
        rc, _out, err = _run_desk_action(
            "merge", "t1", queue_file=queue_file, history_file=history_file
        )
        assert rc != 0
        assert "awaiting_merge" in err.lower()


class TestAbandonFailClosed:
    def test_abandon_missing_reason_fails_closed(self, tmp_path):
        plan = _write_plan(tmp_path, "t1")
        queue_file = _write_queue(
            tmp_path,
            [
                {
                    "id": "t1",
                    "state": "awaiting_merge",
                    "title": "One",
                    "plan_file": str(plan),
                    "branch": "t1-branch",
                }
            ],
        )
        history_file = _write_history(tmp_path)
        rc, _out, err = _run_desk_action(
            "abandon", "t1", queue_file=queue_file, history_file=history_file
        )
        assert rc != 0
        assert "reason" in err.lower()


class TestAbandonSuccess:
    def test_abandon_records_terminal_transition_with_reason(self, tmp_path):
        plan = _write_plan(tmp_path, "t1")
        queue_file = _write_queue(
            tmp_path,
            [
                {
                    "id": "t1",
                    "state": "awaiting_merge",
                    "title": "One",
                    "plan_file": str(plan),
                    "branch": "t1-branch",
                }
            ],
        )
        history_file = _write_history(tmp_path)
        rc, _out, _err = _run_desk_action(
            "abandon", "t1", "--reason", "no longer needed",
            queue_file=queue_file, history_file=history_file,
        )
        assert rc == 0

        queue = json.loads(Path(queue_file).read_text(encoding="utf-8"))
        assert [t["id"] for t in queue] == []

        history_lines = Path(history_file).read_text(encoding="utf-8").strip().splitlines()
        assert len(history_lines) == 1
        settled = json.loads(history_lines[0])
        assert settled["id"] == "t1"
        assert settled["state"] == "abandoned"

        # The transition history entry should record the reason as evidence.
        transition_entry = next(
            (e for e in settled.get("history", []) if e.get("to") == "abandoned"),
            None,
        )
        assert transition_entry is not None
        assert transition_entry["evidence"]["reason"] == "no longer needed"

        # Plan file should reflect the terminal state.
        assert "status:" not in plan.read_text(encoding="utf-8")
        assert "_Stage: abandoned_" in plan.read_text(encoding="utf-8")


def _merge_subprocess_runner(cwd: str | None):
    """Return a mock subprocess.run side_effect for a successful desk merge."""

    def _git_subcommand(cmd):
        """Return the git subcommand, skipping an optional -C <path> prefix."""
        if cmd[0] != "git":
            return None
        idx = 1
        if idx < len(cmd) and cmd[idx] == "-C":
            idx += 2
        return cmd[idx] if idx < len(cmd) else None

    def _run(cmd, **kwargs):
        class _Result:
            def __init__(self, rc, stdout="", stderr=""):
                self.returncode = rc
                self.stdout = stdout
                self.stderr = stderr

        sub = _git_subcommand(cmd)

        if cmd[0] == "gh" and cmd[1:3] == ["pr", "merge"]:
            return _Result(0, "https://github.com/org/repo/pull/1\n", "")
        if sub == "fetch":
            return _Result(0, "", "")
        if sub == "symbolic-ref":
            return _Result(0, "refs/remotes/origin/main\n", "")
        if sub == "rev-parse":
            return _Result(0, "abc123def456\n", "")
        if sub == "merge-base":
            # Success means the tip is an ancestor of origin/main.
            return _Result(0, "", "")
        if sub == "add":
            return _Result(0, "", "")
        if sub == "diff":
            # 1 means there are staged changes to commit.
            return _Result(1, "", "")
        if sub == "commit":
            return _Result(0, "", "")
        if sub == "push":
            return _Result(0, "", "")
        # Fail closed on any unexpected external call so the test surfaces drift.
        raise AssertionError(f"Unexpected subprocess call in desk merge test: {cmd}")

    return _run


class TestMergeSuccess:
    def test_merge_drives_closure_path_to_merged(self, tmp_path, monkeypatch):
        plan = _write_plan(tmp_path, "t1")
        queue_file = _write_queue(
            tmp_path,
            [
                {
                    "id": "t1",
                    "state": "awaiting_merge",
                    "title": "One",
                    "plan_file": str(plan),
                    "branch": "t1-branch",
                }
            ],
        )
        history_file = _write_history(tmp_path)
        monkeypatch.setattr(
            desk.subprocess,
            "run",
            _merge_subprocess_runner(cwd=str(tmp_path)),
        )
        rc, _out, _err = _run_desk_action(
            "merge", "t1", queue_file=queue_file, history_file=history_file
        )
        assert rc == 0

        queue = json.loads(Path(queue_file).read_text(encoding="utf-8"))
        assert [t["id"] for t in queue] == []

        history_lines = Path(history_file).read_text(encoding="utf-8").strip().splitlines()
        assert len(history_lines) == 1
        settled = json.loads(history_lines[0])
        assert settled["id"] == "t1"
        assert settled["state"] == "merged"
        assert settled.get("merge_commit") == "abc123def456"

        # Plan file should reflect the terminal state.
        plan_text = plan.read_text(encoding="utf-8")
        assert "status:" not in plan_text
        assert "_Stage: merged_" in plan_text

    def test_no_second_closure_writer(self, tmp_path, monkeypatch):
        plan = _write_plan(tmp_path, "t1")
        queue_file = _write_queue(
            tmp_path,
            [
                {
                    "id": "t1",
                    "state": "awaiting_merge",
                    "title": "One",
                    "plan_file": str(plan),
                    "branch": "t1-branch",
                }
            ],
        )
        history_file = _write_history(tmp_path)
        monkeypatch.setattr(
            desk.subprocess,
            "run",
            _merge_subprocess_runner(cwd=str(tmp_path)),
        )
        _run_desk_action("merge", "t1", queue_file=queue_file, history_file=history_file)

        history_lines = Path(history_file).read_text(encoding="utf-8").strip().splitlines()
        settled = json.loads(history_lines[0])
        transition_entry = next(
            (e for e in settled.get("history", []) if e.get("to") == "merged"),
            None,
        )
        assert transition_entry is not None
        # The merged transition must still be recorded by aet-state record-merge,
        # proving desk merge did not introduce a second closure writer.
        assert transition_entry["by"] == "record-merge"
