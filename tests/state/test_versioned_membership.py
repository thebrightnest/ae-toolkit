"""Tests for gib-04: versioned sprint membership derived from plan status."""

import importlib.machinery
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_REPO_ROOT = Path(__file__).resolve().parents[2]
_INIT_QUEUE_PY = _REPO_ROOT / "src" / "aet" / "cli" / "init-queue.py"
_NEXT_PY = _REPO_ROOT / "src" / "aet" / "cli" / "next.py"
_SYNC_PY = _REPO_ROOT / "src" / "aet" / "cli" / "sync.py"

_spec = importlib.util.spec_from_loader(
    "init_queue",
    importlib.machinery.SourceFileLoader("init_queue", str(_INIT_QUEUE_PY)),
)
init_queue = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(init_queue)

_spec = importlib.util.spec_from_loader(
    "next_cmd",
    importlib.machinery.SourceFileLoader("next_cmd", str(_NEXT_PY)),
)
next_cmd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(next_cmd)

_spec = importlib.util.spec_from_loader(
    "sync_cmd",
    importlib.machinery.SourceFileLoader("sync_cmd", str(_SYNC_PY)),
)
sync_cmd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sync_cmd)


class MockResult:
    def __init__(self, returncode, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _write_plan(plans_dir: Path, stem: str, status: str = "queued", blocked_by=None):
    """Write a minimal valid plan file."""
    path = plans_dir / f"{stem}.md"
    lines = ["---", f"id: {stem}", "size: S", f"status: {status}"]
    if blocked_by:
        lines.append("blocked_by:")
        for b in blocked_by:
            lines.append(f"  - {b}")
    lines.extend(
        [
            "---",
            "",
            f"# {stem}",
            "",
            "## Context",
            "PRD: docs/prds/default.md",
            "",
            "## Task List",
            "1. Do something (traces: R-1).",
            "",
            "## Files to Modify",
            "- `src/widget.py` (new)",
            "",
            "## Validation Steps",
            "- [ ] test_widget_creation verifies widget.py",
            "",
            "---",
            "",
            "*Stage: plan-approved*",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _write_default_prd(plans_dir: Path):
    prds_dir = plans_dir.parent / "prds"
    prds_dir.mkdir(parents=True, exist_ok=True)
    prds_dir / "default.md"
    (prds_dir / "default.md").write_text(
        "# Default PRD\n\n## Requirements\n- **R-1**: default\n", encoding="utf-8"
    )


def _git_init(root: Path):
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(
        ["git", "-C", str(root), "config", "user.email", "test@example.com"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(root), "config", "user.name", "Test"],
        check=True,
    )
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(root), "commit", "-q", "-m", "initial"],
        check=True,
    )


def _queue_file(root: Path) -> Path:
    return root / ".agents" / "work-queue.json"


def _history_file(root: Path) -> Path:
    return root / ".agents" / "work-history.jsonl"


class TestQueueMembershipDerivedFromStatusQueued(unittest.TestCase):
    """Sprint membership is derived from committed status: queued."""

    def test_init_queue_includes_queued_and_excludes_draft_approved(self):
        """init-queue only includes plans whose status is queued."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plans_dir = root / "docs" / "plans"
            plans_dir.mkdir(parents=True)
            _write_default_prd(plans_dir)
            _git_init(root)
            _write_plan(plans_dir, "queued", status="queued")
            _write_plan(plans_dir, "draft", status="draft")
            _write_plan(plans_dir, "approved", status="approved")
            queue_file = _queue_file(root)
            history_file = _history_file(root)
            config_file = root / ".agents" / "aet-work.json"

            with patch.object(
                sys,
                "argv",
                [
                    "init-queue",
                    "--queue-file",
                    str(queue_file),
                    "--history-file",
                    str(history_file),
                    "--plans-dir",
                    str(plans_dir),
                    "--prds-dir",
                    str(plans_dir.parent / "prds"),
                    "--config",
                    str(config_file),
                ],
            ):
                rc = init_queue.main()

            self.assertEqual(rc, 0)
            data = json.loads(queue_file.read_text(encoding="utf-8"))
            ids = {t["id"] for t in data.get("tasks", [])}
            self.assertIn("queued", ids)
            self.assertNotIn("draft", ids)
            self.assertNotIn("approved", ids)

    def test_sync_filters_non_sprint_members(self):
        """sync removes tasks whose plan is no longer a sprint member."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plans_dir = root / "docs" / "plans"
            plans_dir.mkdir(parents=True)
            _write_default_prd(plans_dir)
            _git_init(root)
            queued_plan = _write_plan(plans_dir, "queued", status="queued")
            draft_plan = _write_plan(plans_dir, "draft", status="queued")
            # Change the draft plan to status: draft after queue creation.
            content = draft_plan.read_text(encoding="utf-8")
            draft_plan.write_text(content.replace("status: queued", "status: draft"))

            queue_file = _queue_file(root)
            history_file = _history_file(root)
            queue_file.parent.mkdir(parents=True, exist_ok=True)
            queue_file.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "id": "queued",
                                "title": "Queued",
                                "plan_file": str(queued_plan),
                                "blocked_by": [],
                                "blocks": [],
                                "state": "ready",
                            },
                            {
                                "id": "draft",
                                "title": "Draft",
                                "plan_file": str(draft_plan),
                                "blocked_by": [],
                                "blocks": [],
                                "state": "ready",
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )

            with patch.object(
                sys,
                "argv",
                [
                    "sync",
                    "--queue-file",
                    str(queue_file),
                    "--history-file",
                    str(history_file),
                    "--plans-dir",
                    str(plans_dir),
                ],
            ):
                rc = sync_cmd.main()

            self.assertEqual(rc, 0)
            data = json.loads(queue_file.read_text(encoding="utf-8"))
            ids = {t["id"] for t in data.get("tasks", [])}
            self.assertIn("queued", ids)
            self.assertNotIn("draft", ids)


class TestTwoClonesSelectSameTaskAfterPull(unittest.TestCase):
    """After a pull, two clones derive the same queue membership."""

    def test_second_checkout_selects_same_task(self):
        """A simulated second checkout sees the same queued plans as the first."""
        with tempfile.TemporaryDirectory() as tmp:
            origin = Path(tmp) / "origin"
            origin.mkdir()
            plans_dir = origin / "docs" / "plans"
            plans_dir.mkdir(parents=True)
            _write_default_prd(plans_dir)
            _write_plan(plans_dir, "queued", status="queued")
            _write_plan(plans_dir, "draft", status="draft")
            _git_init(origin)

            clone_a = Path(tmp) / "clone-a"
            clone_b = Path(tmp) / "clone-b"
            subprocess.run(
                ["git", "clone", "-q", str(origin), str(clone_a)], check=True
            )
            subprocess.run(
                ["git", "clone", "-q", str(origin), str(clone_b)], check=True
            )

            for clone in (clone_a, clone_b):
                queue_file = clone / ".agents" / "work-queue.json"
                history_file = clone / ".agents" / "work-history.jsonl"
                config_file = clone / ".agents" / "aet-work.json"
                with patch.object(
                    sys,
                    "argv",
                    [
                        "init-queue",
                        "--queue-file",
                        str(queue_file),
                        "--history-file",
                        str(history_file),
                        "--plans-dir",
                        str(clone / "docs" / "plans"),
                        "--prds-dir",
                        str(clone / "docs" / "prds"),
                        "--config",
                        str(config_file),
                    ],
                ):
                    rc = init_queue.main()
                self.assertEqual(rc, 0)
                data = json.loads(queue_file.read_text(encoding="utf-8"))
                ids = {t["id"] for t in data.get("tasks", [])}
                self.assertEqual(ids, {"queued"})


class TestReadyBlockedStillComputedFromBlockedBy(unittest.TestCase):
    """R-12 guard: ready/blocked remain computed from blocked_by only."""

    def test_ready_blocked_computed_from_blocked_by(self):
        """A plan with no blockers is ready; a blocked plan is blocked."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plans_dir = root / "docs" / "plans"
            plans_dir.mkdir(parents=True)
            _write_default_prd(plans_dir)
            _git_init(root)
            _write_plan(plans_dir, "ready", status="queued")
            _write_plan(plans_dir, "blocked", status="queued", blocked_by=["ready"])
            queue_file = _queue_file(root)
            history_file = _history_file(root)
            config_file = root / ".agents" / "aet-work.json"

            with patch.object(
                sys,
                "argv",
                [
                    "init-queue",
                    "--queue-file",
                    str(queue_file),
                    "--history-file",
                    str(history_file),
                    "--plans-dir",
                    str(plans_dir),
                    "--prds-dir",
                    str(plans_dir.parent / "prds"),
                    "--config",
                    str(config_file),
                ],
            ):
                rc = init_queue.main()

            self.assertEqual(rc, 0)
            data = json.loads(queue_file.read_text(encoding="utf-8"))
            by_id = {t["id"]: t for t in data.get("tasks", [])}
            self.assertEqual(by_id["ready"]["state"], "ready")
            self.assertEqual(by_id["blocked"]["state"], "blocked")


if __name__ == "__main__":
    unittest.main()
