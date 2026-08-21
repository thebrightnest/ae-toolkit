"""Behavior-driven tests for src/aet/cli/backlog.py and src/aet/cli/gate.py."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from aet.backends.git_refs_backend import GitRefsBackend
from tests.cli._helpers import run_typer

_REPO_ROOT = Path(__file__).parents[2]
_SPRINT_PY = _REPO_ROOT / "src" / "aet" / "cli" / "sprint.py"
_GATE_PY = _REPO_ROOT / "src" / "aet" / "cli" / "gate.py"
_STATUS_PY = _REPO_ROOT / "src" / "aet" / "cli" / "status.py"

_sprint_spec = importlib.util.spec_from_loader(
    "sprint", importlib.machinery.SourceFileLoader("sprint", str(_SPRINT_PY))
)
sprint = importlib.util.module_from_spec(_sprint_spec)
_sprint_spec.loader.exec_module(sprint)

_gate_spec = importlib.util.spec_from_loader(
    "gate", importlib.machinery.SourceFileLoader("gate", str(_GATE_PY))
)
gate = importlib.util.module_from_spec(_gate_spec)
_gate_spec.loader.exec_module(gate)

_status_spec = importlib.util.spec_from_loader(
    "status", importlib.machinery.SourceFileLoader("status", str(_STATUS_PY))
)
status = importlib.util.module_from_spec(_status_spec)
_status_spec.loader.exec_module(status)

aet = importlib.import_module("aet.cli.main")

# The bin scripts above put src/aet on sys.path; the workflow loader
# lives there.
from aet.workflow import load_workflow  # noqa: E402


def _write_json_file(data) -> str:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data, f)
        return f.name


def _make_history(tasks: list[dict]) -> str:
    path = Path(tempfile.mkstemp(suffix=".jsonl")[1])
    with open(path, "w", encoding="utf-8") as f:
        for task in tasks:
            json.dump(task, f)
            f.write("\n")
    return str(path)


def _git_init(root: Path) -> None:
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(
        ["git", "-C", str(root), "config", "user.email", "test@example.com"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(root), "config", "user.name", "Test User"],
        check=True,
    )


def _make_queue(
    root: Path,
    tasks: list[dict] | None = None,
    history: list[dict] | None = None,
) -> tuple[Path, Path]:
    """Create a git-refs queue inside ``root`` and return its paths."""
    _git_init(root)
    queue_file = root / ".agents" / "aet-queue"
    history_file = root / ".agents" / "work-history.jsonl"
    queue_file.parent.mkdir(parents=True, exist_ok=True)
    if history:
        history_file.write_text(
            "".join(json.dumps(task) + "\n" for task in history),
            encoding="utf-8",
        )
    GitRefsBackend(
        queue_file=str(queue_file), history_file=str(history_file)
    ).save(tasks or [])
    return queue_file, history_file


def _read_queue(queue_file: Path, history_file: Path) -> list[dict]:
    return GitRefsBackend(
        queue_file=str(queue_file), history_file=str(history_file)
    ).load()["queue"]


def _make_plan(
    plans_dir: Path,
    name: str,
    *,
    footer_stage: str = "plan-approved",
    blocked_by: list[str] | None = None,
) -> Path:
    path = plans_dir / name
    blocked_lines = "".join(f"  - {b}\n" for b in (blocked_by or []))

    # Create a default PRD so plans pass the full intake validation suite.
    if plans_dir.name == "plans" and plans_dir.parent.name == "docs":
        repo_root = plans_dir.parent.parent
    else:
        repo_root = plans_dir.parent
    prds_dir = repo_root / "docs" / "prds"
    prds_dir.mkdir(parents=True, exist_ok=True)
    prd_path = prds_dir / "default-prd.md"
    if not prd_path.exists():
        prd_path.write_text(
            "# Default PRD\n\n## Requirements\n- **R-1**: default requirement\n",
            encoding="utf-8",
        )

    body = f"""---
id: {Path(name).stem}
size: M
blocked_by:
{blocked_lines}---

# Plan: {name}

## Context
PRD: docs/prds/default-prd.md

## Task List

1. Do something (traces: R-1).

## Files to Modify

- `src/widget.py` (new)

## Validation Steps

- [ ] test_widget_creation verifies widget.py

---

_Stage: {footer_stage}_
_Next step: run `aet-work`_
"""
    path.write_text(body, encoding="utf-8")
    return path


def _git(args: list[str], cwd: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, capture_output=True, check=True)


class TestAddCommand(unittest.TestCase):
    def test_add_plan_file_adds_task_as_ready(self):
        """add accepts a plan file path and inserts a zero-blocker task as ready."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            plans_dir = tmp_path / "plans"
            plans_dir.mkdir()
            plan = _make_plan(plans_dir, "feat-001.md")
            queue_file, history_file = _make_queue(tmp_path)

            rc = run_typer(aet.app, [
                "sprint",
                "add",
                str(plan),
                "--queue-file", str(queue_file),
                "--history-file", str(history_file),
                "--plans-dir", str(plans_dir),
            ]).exit_code

            self.assertEqual(rc, 0)
            queue = _read_queue(queue_file, history_file)
            self.assertEqual(len(queue), 1)
            self.assertEqual(queue[0]["id"], "feat-001")
            self.assertEqual(queue[0]["state"], "ready")
            self.assertEqual(queue[0]["plan_file"], str(plan))

    def test_add_blocked_plan_adds_task_as_blocked(self):
        """add inserts a task with blockers as blocked and records the actual state."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            plans_dir = tmp_path / "plans"
            plans_dir.mkdir()
            blocker = _make_plan(plans_dir, "feat-000.md")
            plan = _make_plan(plans_dir, "feat-001.md", blocked_by=["feat-000"])
            queue_file, history_file = _make_queue(tmp_path)

            rc = run_typer(aet.app, [
                "sprint",
                "add",
                str(blocker),
                "--queue-file", str(queue_file),
                "--history-file", str(history_file),
                "--plans-dir", str(plans_dir),
            ]).exit_code
            self.assertEqual(rc, 0)

            rc = run_typer(aet.app, [
                "sprint",
                "add",
                str(plan),
                "--queue-file", str(queue_file),
                "--history-file", str(history_file),
                "--plans-dir", str(plans_dir),
            ]).exit_code
            self.assertEqual(rc, 0)

            queue = _read_queue(queue_file, history_file)
            tasks = {t["id"]: t for t in queue}
            self.assertEqual(tasks["feat-001"]["state"], "blocked")
            self.assertEqual(tasks["feat-001"]["pending_blockers"], 1)
            self.assertEqual(tasks["feat-000"]["blocks"], ["feat-001"])
            self.assertEqual(tasks["feat-001"]["history"][0]["to"], "blocked")

    def test_add_task_id_adds_task(self):
        """add accepts a task ID and resolves it to the plan file."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            plans_dir = tmp_path / "plans"
            plans_dir.mkdir()
            _make_plan(plans_dir, "feat-002.md")
            queue_file, history_file = _make_queue(tmp_path)

            rc = run_typer(aet.app, [
                "sprint",
                "add",
                "feat-002",
                "--queue-file", str(queue_file),
                "--history-file", str(history_file),
                "--plans-dir", str(plans_dir),
            ]).exit_code

            self.assertEqual(rc, 0)
            queue = _read_queue(queue_file, history_file)
            self.assertEqual(len(queue), 1)
            self.assertEqual(queue[0]["id"], "feat-002")
            self.assertEqual(queue[0]["state"], "ready")

    def test_add_rejects_merged_plan(self):
        """add refuses to queue a plan whose footer stage is merged."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            plans_dir = tmp_path / "plans"
            plans_dir.mkdir()
            plan = _make_plan(plans_dir, "feat-003.md", footer_stage="merged")
            queue_file, history_file = _make_queue(tmp_path)

            result = run_typer(aet.app, [
                "sprint",
                "add",
                str(plan),
                "--queue-file", str(queue_file),
                "--history-file", str(history_file),
                "--plans-dir", str(plans_dir),
            ])

            self.assertEqual(result.exit_code, 1)
            self.assertIn("merged", result.stderr.lower())
            queue = _read_queue(queue_file, history_file)
            self.assertEqual(len(queue), 0)

    def test_add_rejects_abandoned_plan(self):
        """add refuses to queue a plan whose footer stage is abandoned."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            plans_dir = tmp_path / "plans"
            plans_dir.mkdir()
            plan = _make_plan(plans_dir, "feat-004.md", footer_stage="abandoned")
            queue_file, history_file = _make_queue(tmp_path)

            result = run_typer(aet.app, [
                "sprint",
                "add",
                str(plan),
                "--queue-file", str(queue_file),
                "--history-file", str(history_file),
                "--plans-dir", str(plans_dir),
            ])

            self.assertEqual(result.exit_code, 1)
            self.assertIn("abandoned", result.stderr.lower())

    def test_add_unknown_plan_rejected(self):
        """add exits non-zero when the plan file or task ID is unknown."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            plans_dir = tmp_path / "plans"
            plans_dir.mkdir()
            queue_file, history_file = _make_queue(tmp_path)

            rc = run_typer(aet.app, [
                "sprint",
                "add",
                "nonexistent",
                "--queue-file", str(queue_file),
                "--history-file", str(history_file),
                "--plans-dir", str(plans_dir),
            ]).exit_code

            self.assertEqual(rc, 1)

    def test_add_already_queued_is_idempotent(self):
        """add succeeds without duplicating an already-queued task."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            plans_dir = tmp_path / "plans"
            plans_dir.mkdir()
            plan = _make_plan(plans_dir, "feat-005.md")
            queue_file, history_file = _make_queue(tmp_path)

            rc1 = run_typer(aet.app, [
                "sprint",
                "add",
                str(plan),
                "--queue-file", str(queue_file),
                "--history-file", str(history_file),
                "--plans-dir", str(plans_dir),
            ]).exit_code
            self.assertEqual(rc1, 0)

            rc2 = run_typer(aet.app, [
                "sprint",
                "add",
                str(plan),
                "--queue-file", str(queue_file),
                "--history-file", str(history_file),
                "--plans-dir", str(plans_dir),
            ]).exit_code
            self.assertEqual(rc2, 0)

            queue = _read_queue(queue_file, history_file)
            self.assertEqual(len(queue), 1)

    def test_add_parks_ready_when_unblocked(self):
        """add parks a zero-blocker task at ready, never planned (curated intake)."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            plans_dir = tmp_path / "plans"
            plans_dir.mkdir()
            plan = _make_plan(plans_dir, "feat-100.md")
            queue_file, history_file = _make_queue(tmp_path)

            rc = run_typer(aet.app, [
                "sprint",
                "add",
                str(plan),
                "--queue-file", str(queue_file),
                "--history-file", str(history_file),
                "--plans-dir", str(plans_dir),
            ]).exit_code

            self.assertEqual(rc, 0)
            queue = _read_queue(queue_file, history_file)
            self.assertEqual(len(queue), 1)
            self.assertEqual(queue[0]["state"], "ready")
            self.assertEqual(queue[0]["pending_blockers"], 0)
            # Guard against the historical inversion: add used to overwrite with planned.
            self.assertNotEqual(queue[0]["state"], "planned")

    def test_add_parks_blocked_with_pending_blockers_and_builds_edges(self):
        """add parks a blocked task and rebuilds reverse blocks edges on the queue."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            plans_dir = tmp_path / "plans"
            plans_dir.mkdir()
            blocker = _make_plan(plans_dir, "feat-200.md")
            dependent = _make_plan(plans_dir, "feat-201.md", blocked_by=["feat-200"])
            queue_file, history_file = _make_queue(tmp_path)

            self.assertEqual(run_typer(aet.app, [
                "sprint",
                "add",
                str(blocker), "--queue-file", str(queue_file),
                "--history-file", str(history_file), "--plans-dir", str(plans_dir),
            ]).exit_code, 0)
            self.assertEqual(run_typer(aet.app, [
                "sprint",
                "add",
                str(dependent), "--queue-file", str(queue_file),
                "--history-file", str(history_file), "--plans-dir", str(plans_dir),
            ]).exit_code, 0)

            queue = _read_queue(queue_file, history_file)
            tasks = {t["id"]: t for t in queue}
            self.assertEqual(tasks["feat-201"]["state"], "blocked")
            self.assertEqual(tasks["feat-201"]["pending_blockers"], 1)
            # Reverse edge rebuilt by add's build_blocks call (not only by sync).
            self.assertIn("feat-201", tasks["feat-200"]["blocks"])

    def test_intake_history_records_actual_initial_state(self):
        """The intake history entry records the real initial state, not a hardcoded planned."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            plans_dir = tmp_path / "plans"
            plans_dir.mkdir()
            ready_plan = _make_plan(plans_dir, "feat-300.md")
            blocker = _make_plan(plans_dir, "feat-301.md")
            blocked_plan = _make_plan(plans_dir, "feat-302.md", blocked_by=["feat-301"])
            queue_file, history_file = _make_queue(tmp_path)

            for p in (ready_plan, blocker, blocked_plan):
                self.assertEqual(run_typer(aet.app, [
                "sprint",
                "add",
                    str(p), "--queue-file", str(queue_file),
                    "--history-file", str(history_file), "--plans-dir", str(plans_dir),
                ]).exit_code, 0)

            queue = _read_queue(queue_file, history_file)
            tasks = {t["id"]: t for t in queue}
            self.assertIsNone(tasks["feat-300"]["history"][0]["from"])
            self.assertEqual(tasks["feat-300"]["history"][0]["to"], "ready")
            self.assertEqual(tasks["feat-302"]["history"][0]["to"], "blocked")
            # Guard against the historical bug: intake used to log None -> planned.
            self.assertNotEqual(tasks["feat-300"]["history"][0]["to"], "planned")
            self.assertNotEqual(tasks["feat-302"]["history"][0]["to"], "planned")


    def test_add_ignores_merged_blockers_in_pending_count(self):
        """A blocker already merged and archived to history does not count as pending.

        Regression: add-after-merge used to seed pending_blockers from the full
        blocked_by list, deadlocking the task because the merged blocker's
        decrement event had already fired.
        """
        with tempfile.TemporaryDirectory() as tmp:
            plans_dir = Path(tmp) / "plans"
            plans_dir.mkdir()
            plan = _make_plan(plans_dir, "feat-400.md", blocked_by=["feat-399"])
            queue_file, history_file = _make_queue(
                Path(tmp), history=[{"id": "feat-399", "state": "merged"}]
            )

            rc = run_typer(aet.app, [
                "sprint",
                "add",
                str(plan),
                "--queue-file", str(queue_file),
                "--history-file", str(history_file),
                "--plans-dir", str(plans_dir),
            ]).exit_code

            self.assertEqual(rc, 0)
            queue = _read_queue(queue_file, history_file)
            self.assertEqual(len(queue), 1)
            self.assertEqual(queue[0]["state"], "ready")
            self.assertEqual(queue[0]["pending_blockers"], 0)
            # The blocked_by edge list is preserved; only the count reconciles.
            self.assertEqual(queue[0]["blocked_by"], ["feat-399"])
            self.assertEqual(queue[0]["history"][0]["to"], "ready")

    def test_add_mixed_blockers_counts_only_live(self):
        """blocked_by mixing a settled blocker and a live one parks blocked with pb=1."""
        with tempfile.TemporaryDirectory() as tmp:
            plans_dir = Path(tmp) / "plans"
            plans_dir.mkdir()
            live = _make_plan(plans_dir, "feat-500.md")
            dependent = _make_plan(
                plans_dir, "feat-501.md", blocked_by=["feat-499", "feat-500"]
            )
            queue_file, history_file = _make_queue(
                Path(tmp), history=[{"id": "feat-499", "state": "merged"}]
            )

            self.assertEqual(run_typer(aet.app, [
                "sprint",
                "add",
                str(live), "--queue-file", str(queue_file),
                "--history-file", str(history_file), "--plans-dir", str(plans_dir),
            ]).exit_code, 0)
            self.assertEqual(run_typer(aet.app, [
                "sprint",
                "add",
                str(dependent), "--queue-file", str(queue_file),
                "--history-file", str(history_file), "--plans-dir", str(plans_dir),
            ]).exit_code, 0)

            tasks = {t["id"]: t for t in _read_queue(queue_file, history_file)}
            self.assertEqual(tasks["feat-501"]["state"], "blocked")
            self.assertEqual(tasks["feat-501"]["pending_blockers"], 1)
            # The live blocker still wires a reverse edge for its decrement.
            self.assertIn("feat-501", tasks["feat-500"]["blocks"])

    def test_add_accepts_untracked_plan_in_git_repo(self):
        """Untracked plans are normal intake; sprint add queues them."""
        with tempfile.TemporaryDirectory() as tmp:
            _git(["init"], tmp)
            _git(["config", "user.email", "test@example.com"], tmp)
            _git(["config", "user.name", "Test User"], tmp)
            Path(tmp, "README.md").write_text("# test", encoding="utf-8")
            _git(["add", "."], tmp)
            _git(["commit", "-q", "-m", "init"], tmp)
            _git(["branch", "-M", "main"], tmp)
            _git(["remote", "add", "origin", tmp], tmp)
            _git(["update-ref", "refs/remotes/origin/main", "HEAD"], tmp)

            plans_dir = Path(tmp) / "docs" / "plans"
            plans_dir.mkdir(parents=True)
            plan = _make_plan(plans_dir, "feat-600.md")  # never git-added
            queue_file, history_file = _make_queue(Path(tmp))

            result = run_typer(aet.app, [
                "sprint",
                "add",
                str(plan),
                "--queue-file", str(queue_file),
                "--history-file", str(history_file),
                "--plans-dir", str(plans_dir),
            ])

            self.assertEqual(result.exit_code, 0)
            self.assertIn("queued without publishing", result.stdout)
            queue = _read_queue(queue_file, history_file)
            self.assertEqual(len(queue), 1)
            self.assertEqual(queue[0]["id"], "feat-600")

            origin_log = subprocess.run(
                ["git", "-C", tmp, "log", "origin/main", "--oneline"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout
            self.assertEqual(len(origin_log.strip().splitlines()), 1)

    def test_add_accepts_tracked_plan_in_git_repo(self):
        """A git-tracked plan queues normally and is not published at intake."""
        with tempfile.TemporaryDirectory() as tmp:
            _git(["init"], tmp)
            _git(["config", "user.email", "test@example.com"], tmp)
            _git(["config", "user.name", "Test User"], tmp)
            Path(tmp, "README.md").write_text("# test", encoding="utf-8")
            _git(["add", "."], tmp)
            _git(["commit", "-q", "-m", "init"], tmp)

            plans_dir = Path(tmp) / "docs" / "plans"
            plans_dir.mkdir(parents=True)
            plan = _make_plan(plans_dir, "feat-601.md")
            _git(["add", str(plan)], tmp)  # tracked (staged is enough)
            queue_file, history_file = _make_queue(Path(tmp))

            result = run_typer(aet.app, [
                "sprint",
                "add",
                str(plan),
                "--queue-file", str(queue_file),
                "--history-file", str(history_file),
                "--plans-dir", str(plans_dir),
            ])

            self.assertEqual(result.exit_code, 0)
            self.assertIn("queued without publishing", result.stdout)
            queue = _read_queue(queue_file, history_file)
            self.assertEqual(len(queue), 1)
            self.assertEqual(queue[0]["id"], "feat-601")


class TestReviewCommand(unittest.TestCase):
    def test_review_categorizes_plans_by_footer_stage(self):
        """review prints plans grouped into approved/queued/in-progress/awaiting-merge/closed."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            plans_dir = tmp_path / "plans"
            plans_dir.mkdir()
            _make_plan(plans_dir, "approved-1.md", footer_stage="plan-approved")
            _make_plan(plans_dir, "queued-1.md", footer_stage="synced")
            _make_plan(plans_dir, "inprog-1.md", footer_stage="implemented")
            _make_plan(plans_dir, "await-1.md", footer_stage="awaiting_merge")
            _make_plan(plans_dir, "closed-1.md", footer_stage="merged")
            _make_plan(plans_dir, "closed-2.md", footer_stage="abandoned")

            stdout = io.StringIO()
            with patch.object(sys, "stdout", stdout):
                rc = gate.run_review(plans_dir)

            self.assertEqual(rc, 0)
            output = stdout.getvalue()
            self.assertIn("approved-1", output)
            self.assertIn("queued-1", output)
            self.assertIn("inprog-1", output)
            self.assertIn("await-1", output)
            self.assertIn("closed-1", output)
            self.assertIn("closed-2", output)

    def test_review_empty_plans_dir(self):
        """review exits cleanly when no plans exist."""
        with tempfile.TemporaryDirectory() as tmp:
            plans_dir = Path(tmp) / "plans"
            plans_dir.mkdir()

            stdout = io.StringIO()
            with patch.object(sys, "stdout", stdout):
                rc = gate.run_review(plans_dir)

            self.assertEqual(rc, 0)

    def test_review_missing_plans_dir(self):
        """review exits non-zero when the plans directory does not exist."""
        stdout = io.StringIO()
        with patch.object(sys, "stdout", stdout):
            rc = run_typer(aet.app, [
                "gate",
                "review",
                "--plans-dir", "/does/not/exist",
            ]).exit_code

        self.assertEqual(rc, 1)


class TestReviewBoardColumns(unittest.TestCase):
    """Board columns derive positionally from the loaded workflow (wfd-03)."""

    def setUp(self):
        self.workflow = load_workflow(_REPO_ROOT)

    def test_entry_stage_maps_to_approved(self):
        self.assertEqual(
            gate.category_for_stage("plan-approved", self.workflow), "approved"
        )

    def test_terminal_skill_less_stage_maps_to_queued(self):
        self.assertEqual(gate.category_for_stage("synced", self.workflow), "queued")

    def test_skilled_middle_stages_map_to_in_progress(self):
        for stage in ("implemented", "qa-complete", "reviewed", "secure"):
            self.assertEqual(
                gate.category_for_stage(stage, self.workflow), "in-progress"
            )

    def test_unknown_stage_falls_back_to_in_progress(self):
        self.assertEqual(
            gate.category_for_stage("imagined-stage", self.workflow), "in-progress"
        )

    def test_queue_states_keep_their_columns(self):
        self.assertEqual(
            gate.category_for_stage("awaiting_merge", self.workflow), "awaiting-merge"
        )
        self.assertEqual(gate.category_for_stage("merged", self.workflow), "closed")
        self.assertEqual(gate.category_for_stage("abandoned", self.workflow), "closed")

    def test_missing_stage_defaults_to_approved(self):
        self.assertEqual(gate.category_for_stage(None, self.workflow), "approved")

    def test_variant_vocabulary_derives_positionally(self):
        """A variant workflow's unknown vocabulary still renders a board."""
        variant = {
            "version": 1,
            "name": "variant",
            "done_state": "done",
            "stages": [
                {"name": "scoped", "skills": ["aet-implement"], "evidence": None, "gate_key": None},
                {"name": "built", "skills": ["aet-qa"], "evidence": "qa", "gate_key": None},
                {"name": "released", "skills": [], "evidence": None, "gate_key": None},
            ],
            "execution_policy": {"session_groups": [["scoped", "built"]]},
            "routing": {"default": {"harness": "test", "model": None}, "by_stage": {}},
        }
        with tempfile.TemporaryDirectory() as repo_root:
            workflow_dir = Path(repo_root) / ".agents" / "workflows"
            workflow_dir.mkdir(parents=True)
            Path(workflow_dir, "variant.json").write_text(
                json.dumps(variant), encoding="utf-8"
            )
            wf = load_workflow(repo_root, "variant")

        self.assertEqual(gate.category_for_stage("scoped", wf), "approved")
        self.assertEqual(gate.category_for_stage("built", wf), "in-progress")
        self.assertEqual(gate.category_for_stage("released", wf), "queued")
        self.assertEqual(gate.category_for_stage("unlisted", wf), "in-progress")

    def test_without_workflow_legacy_buckets_still_render(self):
        """With no workflow available the historical map renders the same board."""
        self.assertEqual(gate.category_for_stage("plan-approved"), "approved")
        self.assertEqual(gate.category_for_stage("synced"), "queued")
        self.assertEqual(gate.category_for_stage("implemented"), "in-progress")
        self.assertEqual(gate.category_for_stage("awaiting_merge"), "awaiting-merge")
        self.assertEqual(gate.category_for_stage("merged"), "closed")
        self.assertEqual(gate.category_for_stage("imagined-stage"), "in-progress")


class TestStatusEmptyQueue(unittest.TestCase):
    def test_status_handles_empty_queue_gracefully(self):
        """status prints a clean summary when the queue exists but is empty."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            plans_dir = tmp_path / "plans"
            plans_dir.mkdir()
            queue_file, history_file = _make_queue(tmp_path)

            result = run_typer(
                aet.app,
                [
                    "status",
                    "--queue-file", str(queue_file),
                    "--history-file", str(history_file),
                    "--plans-dir", str(plans_dir),
                ],
            )

            self.assertEqual(result.exit_code, 0)
            output = result.stdout
            self.assertIn("Queue is empty.", output)
            self.assertNotIn("Queue summary:", output)
            self.assertNotIn("planned: 0", output)
            self.assertIn("No active tasks.", output)
            self.assertIn("No ready tasks.", output)
            self.assertIn("No failed tasks.", output)


if __name__ == "__main__":
    unittest.main()
