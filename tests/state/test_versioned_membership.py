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
_INIT_QUEUE_PY = _REPO_ROOT / "src" / "aet" / "cli" / "init_queue.py"
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


def _write_plan(plans_dir: Path, stem: str, blocked_by=None):
    """Write a minimal valid plan file without frontmatter status."""
    path = plans_dir / f"{stem}.md"
    lines = ["---", f"id: {stem}", "size: S"]
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


def _write_queue_file(queue_file: Path, tasks: list[dict]) -> None:
    """Write a queue file with the given task list."""
    queue_file.parent.mkdir(parents=True, exist_ok=True)
    queue_file.write_text(json.dumps({"tasks": tasks}), encoding="utf-8")


class TestQueueMembershipFromExplicitRecord(unittest.TestCase):
    """Sprint membership is the explicit queue record, never frontmatter status."""

    def test_init_queue_does_not_auto_add_from_status(self):
        """init-queue preserves explicit members; status no longer selects membership."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plans_dir = root / "docs" / "plans"
            plans_dir.mkdir(parents=True)
            _write_default_prd(plans_dir)
            _git_init(root)
            queued_plan = _write_plan(plans_dir, "queued")
            draft_plan = _write_plan(plans_dir, "draft")
            approved_plan = _write_plan(plans_dir, "approved")
            queue_file = _queue_file(root)
            history_file = _history_file(root)
            config_file = root / ".agents" / "aet-config.json"
            _write_queue_file(
                queue_file,
                [
                    {
                        "id": "queued",
                        "title": "Queued",
                        "plan_file": str(queued_plan),
                        "blocked_by": [],
                        "blocks": [],
                        "state": "planned",
                    },
                    {
                        "id": "draft",
                        "title": "Draft",
                        "plan_file": str(draft_plan),
                        "blocked_by": [],
                        "blocks": [],
                        "state": "planned",
                    },
                    {
                        "id": "approved",
                        "title": "Approved",
                        "plan_file": str(approved_plan),
                        "blocked_by": [],
                        "blocks": [],
                        "state": "planned",
                    },
                ],
            )

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
            self.assertEqual(ids, {"queued", "draft", "approved"})

    def test_sync_preserves_explicit_members_regardless_of_status(self):
        """sync does not remove tasks based on frontmatter status changes."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plans_dir = root / "docs" / "plans"
            plans_dir.mkdir(parents=True)
            _write_default_prd(plans_dir)
            _git_init(root)
            queued_plan = _write_plan(plans_dir, "queued")
            draft_plan = _write_plan(plans_dir, "draft")
            # Inject a stale status line into one plan; membership is still explicit.
            content = draft_plan.read_text(encoding="utf-8")
            draft_plan.write_text(content.replace("---\n", "---\nstatus: draft\n", 1))

            queue_file = _queue_file(root)
            history_file = _history_file(root)
            _write_queue_file(
                queue_file,
                [
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
                ],
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
            self.assertEqual(ids, {"queued", "draft"})


class TestTwoClonesSelectSameTaskAfterPull(unittest.TestCase):
    """After a pull, two clones derive the same queue membership."""

    def test_second_checkout_selects_same_task(self):
        """A simulated second checkout rebuilds the same explicit queue members."""
        with tempfile.TemporaryDirectory() as tmp:
            origin = Path(tmp) / "origin"
            origin.mkdir()
            plans_dir = origin / "docs" / "plans"
            plans_dir.mkdir(parents=True)
            _write_default_prd(plans_dir)
            queued_plan = _write_plan(plans_dir, "queued")
            _write_plan(plans_dir, "draft")
            queue_file = _queue_file(origin)
            history_file = _history_file(origin)
            _write_queue_file(
                queue_file,
                [
                    {
                        "id": "queued",
                        "title": "Queued",
                        "plan_file": str(queued_plan),
                        "blocked_by": [],
                        "blocks": [],
                        "state": "planned",
                    }
                ],
            )
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
                config_file = clone / ".agents" / "aet-config.json"
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
            ready_plan = _write_plan(plans_dir, "ready")
            blocked_plan = _write_plan(plans_dir, "blocked", blocked_by=["ready"])
            queue_file = _queue_file(root)
            history_file = _history_file(root)
            config_file = root / ".agents" / "aet-config.json"
            _write_queue_file(
                queue_file,
                [
                    {
                        "id": "ready",
                        "title": "Ready",
                        "plan_file": str(ready_plan),
                        "blocked_by": [],
                        "blocks": [],
                        "state": "planned",
                    },
                    {
                        "id": "blocked",
                        "title": "Blocked",
                        "plan_file": str(blocked_plan),
                        "blocked_by": ["ready"],
                        "blocks": [],
                        "state": "planned",
                    },
                ],
            )

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
