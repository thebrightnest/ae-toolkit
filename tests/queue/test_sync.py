"""Behavior-driven tests for src/aet/cli/sync.py."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]


def _seed_queue_from_plans(queue_file, plans_dir):
    """Create a minimal queue file containing every plan in ``plans_dir``."""
    tasks = []
    for pf in sorted(Path(plans_dir).glob("*.md")):
        tasks.append(
            {
                "id": pf.stem,
                "title": pf.stem,
                "plan_file": str(pf),
                "blocked_by": [],
                "blocks": [],
                "state": "planned",
                "merge_commit": None,
                "branch": None,
                "worktree": None,
                "completed_at": None,
                "merged_at": None,
            }
        )
    Path(queue_file).write_text(json.dumps({"tasks": tasks}), encoding="utf-8")


def run_sync(cwd, queue_file, history_file, plans_dir):
    """Run the sync script in an isolated environment and return its result."""
    env = os.environ.copy()
    fake_bin = Path(cwd) / "fakebin"
    fake_bin.mkdir(exist_ok=True)
    fake_python3 = fake_bin / "python3"
    log_file = Path(cwd) / "fake_python3_calls.txt"
    fake_python3.write_text(
        "#!/usr/bin/env python3\n"
        "import sys, os\n"
        f"log = {str(log_file)!r}\n"
        "with open(log, 'a') as f:\n"
        "    f.write(repr(sys.argv[1:]) + '\\n')\n"
        "print('{}')\n"
    )
    fake_python3.chmod(0o755)
    env["PATH"] = str(fake_bin) + os.pathsep + env["PATH"]
    env["FAKE_PYTHON3_LOG"] = str(log_file)

    cmd = [
        sys.executable,
        str(REPO_ROOT / "src" / "aet" / "cli" / "sync.py"),
        "--queue-file",
        str(queue_file),
        "--history-file",
        str(history_file),
        "--plans-dir",
        str(plans_dir),
    ]
    result = subprocess.run(cmd, cwd=str(cwd), env=env, capture_output=True, text=True)
    return result, log_file


def read_queue_dict(queue_file):
    """Read the queue file, returning the raw dict/list."""
    with open(queue_file, "r", encoding="utf-8") as f:
        return json.load(f)


def read_tasks(queue_file):
    """Read the task list from a queue file, regardless of wrapper format."""
    data = read_queue_dict(queue_file)
    if isinstance(data, dict):
        return data.get("tasks", [])
    return data


def _ensure_default_prd(path: Path) -> None:
    """Create a default PRD so tests can produce intake-valid plans."""
    if path.parent.name == "plans" and path.parent.parent.name == "docs":
        repo_root = path.parent.parent.parent
    else:
        repo_root = path.parent.parent
    prds_dir = repo_root / "docs" / "prds"
    prds_dir.mkdir(parents=True, exist_ok=True)
    prd_path = prds_dir / "default-prd.md"
    if not prd_path.exists():
        prd_path.write_text(
            "# Default PRD\n\n## Requirements\n- **R-1**: default requirement\n",
            encoding="utf-8",
        )


def make_plan(path, title, blocked_by=None, size="M", extra_body="", status=None):
    """Write a plan markdown file that passes the full intake validation suite."""
    stem = path.stem
    lines = ["---", f"id: {stem}", f"size: {size}"]
    if status is not None:
        lines.append(f"status: {status}")
    if blocked_by:
        lines.append("blocked_by:")
        for blocker in blocked_by:
            lines.append(f"  - {blocker}")
    lines.extend(["---", "", f"# {title}", ""])

    _ensure_default_prd(path)
    lines.extend(["## Context", "PRD: docs/prds/default-prd.md", ""])

    if extra_body:
        lines.extend([extra_body, ""])

    lines.extend(["## Task List", "1. Do something (traces: R-1).", ""])
    lines.extend(["## Files to Modify", "- `src/widget.py` (new)", ""])
    lines.extend(
        ["## Validation Steps", "- [ ] test_widget_creation verifies widget.py", ""]
    )
    lines.extend(["---", "", "*Stage: plan-approved*"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class TestSync(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.plans_dir = self.root / "plans"
        self.prds_dir = self.root / "prds"
        self.queue_file = self.root / "work-queue.json"
        self.history_file = self.root / "work-history.jsonl"
        self.plans_dir.mkdir()
        self.prds_dir.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_preserves_existing_and_does_not_auto_add(self):
        """sync reconciles existing entries and never auto-adds new plans."""
        existing_plan = self.plans_dir / "existing.md"
        make_plan(existing_plan, "Existing task")
        initial = {
            "source_prd": "docs/prds/p.md",
            "queue_updated_at": "2026-01-01T00:00:00Z",
            "tasks": [
                {
                    "id": "existing",
                    "title": "Existing task",
                    "plan_file": str(existing_plan),
                    "blocked_by": [],
                    "blocks": [],
                    "state": "in_progress",
                    "merge_commit": None,
                    "branch": "feat-existing",
                    "worktree": "/worktrees/existing",
                    "completed_at": None,
                    "merged_at": None,
                }
            ],
        }
        self.queue_file.write_text(json.dumps(initial))

        make_plan(self.plans_dir / "new.md", "New task", blocked_by=["existing"])

        result, _ = run_sync(
            self.root, self.queue_file, self.history_file, self.plans_dir
        )
        self.assertEqual(result.returncode, 0, result.stderr)

        data = read_queue_dict(self.queue_file)
        self.assertIsInstance(data, dict)
        tasks = {t["id"]: t for t in data["tasks"]}

        # Existing task preserved.
        self.assertEqual(tasks["existing"]["state"], "in_progress")
        self.assertEqual(tasks["existing"]["branch"], "feat-existing")
        # New plan was not auto-added.
        self.assertNotIn("new", tasks)
        # blocks inverse recomputed for the whole queue.
        self.assertEqual(tasks["existing"]["blocks"], [])
        self.assertIn("0 new tasks added", result.stdout)

    def test_drops_legacy_merge_verified_terminal_records(self):
        """sync drops legacy terminal statuses from the live queue."""
        existing_plan = self.plans_dir / "legacy.md"
        make_plan(existing_plan, "Legacy task")
        initial = {
            "tasks": [
                {
                    "id": "legacy",
                    "title": "Legacy task",
                    "plan_file": str(existing_plan),
                    "blocked_by": [],
                    "blocks": [],
                    "status": "merge_verified",
                    "merge_commit": "def5678",
                    "branch": None,
                    "worktree": None,
                    "completed_at": None,
                    "merged_at": None,
                }
            ]
        }
        self.queue_file.write_text(json.dumps(initial))

        result, _ = run_sync(
            self.root, self.queue_file, self.history_file, self.plans_dir
        )
        self.assertEqual(result.returncode, 0, result.stderr)

        tasks = {t["id"]: t for t in read_tasks(self.queue_file)}
        self.assertNotIn("legacy", tasks)
        self.assertIn("1 skipped (already settled)", result.stdout)

    def test_does_not_call_derive(self):
        """sync must not invoke aet-state derive."""
        self.queue_file.write_text(json.dumps({"tasks": []}))
        result, log_file = run_sync(
            self.root, self.queue_file, self.history_file, self.plans_dir
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        derive_calls = []
        if log_file.exists():
            for line in log_file.read_text().splitlines():
                if "derive" in line:
                    derive_calls.append(line)
        self.assertEqual(derive_calls, [])

    def test_creates_missing_queue_file(self):
        """sync recreates a missing queue file on demand."""
        self.assertFalse(self.queue_file.exists())

        result, _ = run_sync(
            self.root, self.queue_file, self.history_file, self.plans_dir
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(
            self.queue_file.exists(),
            "sync must create the queue file when it is missing",
        )

    def test_sync_preserves_explicit_members_regardless_of_status(self):
        """sync does not remove tasks based on frontmatter status changes."""
        existing = self.plans_dir / "existing.md"
        existing.write_text(
            "---\nid: existing\nsize: S\nstatus: queued\n---\n\n# Existing\n\n"
            "## Context\nPRD: docs/prds/default-prd.md\n\n"
            "## Task List\n1. Do something (traces: R-1).\n\n"
            "## Files to Modify\n- `src/widget.py` (new)\n\n"
            "## Validation Steps\n- [ ] test_widget_creation verifies widget.py\n\n"
            "---\n\n*Stage: plan-approved*\n",
            encoding="utf-8",
        )
        _ensure_default_prd(existing)
        initial = {
            "tasks": [
                {
                    "id": "existing",
                    "title": "Existing task",
                    "plan_file": str(existing),
                    "blocked_by": [],
                    "blocks": [],
                    "state": "ready",
                    "merge_commit": None,
                    "branch": None,
                    "worktree": None,
                    "completed_at": None,
                    "merged_at": None,
                }
            ]
        }
        self.queue_file.write_text(json.dumps(initial))

        result, _ = run_sync(
            self.root, self.queue_file, self.history_file, self.plans_dir
        )
        self.assertEqual(result.returncode, 0, result.stderr)

        data = json.loads(self.queue_file.read_text(encoding="utf-8"))
        ids = {t["id"] for t in data.get("tasks", [])}
        self.assertEqual(ids, {"existing"})

    def test_sync_never_adds_new_plans(self):
        """sync reconciles existing entries and never auto-adds plans from disk."""
        existing_plan = self.plans_dir / "existing.md"
        make_plan(existing_plan, "Existing task")
        initial = {
            "tasks": [
                {
                    "id": "existing",
                    "title": "Existing task",
                    "plan_file": str(existing_plan),
                    "blocked_by": [],
                    "blocks": [],
                    "state": "in_progress",
                    "merge_commit": None,
                    "branch": None,
                    "worktree": None,
                    "completed_at": None,
                    "merged_at": None,
                }
            ]
        }
        self.queue_file.write_text(json.dumps(initial))
        # A second plan exists on disk but was never explicitly added via `add`.
        make_plan(self.plans_dir / "new.md", "New task", size="S")

        result, _ = run_sync(
            self.root, self.queue_file, self.history_file, self.plans_dir
        )
        self.assertEqual(result.returncode, 0, result.stderr)

        tasks = {t["id"]: t for t in read_tasks(self.queue_file)}
        self.assertIn("existing", tasks)
        self.assertNotIn("new", tasks)
        self.assertIn("0 new tasks added", result.stdout)

    def test_sync_rebuilds_blocks(self):
        """sync recomputes reverse blocks edges for the existing queue."""
        plan_a = self.plans_dir / "a.md"
        plan_b = self.plans_dir / "b.md"
        make_plan(plan_a, "Task A", size="S")
        make_plan(plan_b, "Task B", blocked_by=["a"], size="S")
        initial = {
            "tasks": [
                {
                    "id": "a",
                    "title": "Task A",
                    "plan_file": str(plan_a),
                    "blocked_by": [],
                    "blocks": [],  # stale; build_blocks must rebuild to ["b"]
                    "state": "ready",
                    "merge_commit": None,
                    "branch": None,
                    "worktree": None,
                    "completed_at": None,
                    "merged_at": None,
                },
                {
                    "id": "b",
                    "title": "Task B",
                    "plan_file": str(plan_b),
                    "blocked_by": ["a"],
                    "blocks": [],
                    "state": "blocked",
                    "merge_commit": None,
                    "branch": None,
                    "worktree": None,
                    "completed_at": None,
                    "merged_at": None,
                },
            ]
        }
        self.queue_file.write_text(json.dumps(initial))

        result, _ = run_sync(
            self.root, self.queue_file, self.history_file, self.plans_dir
        )
        self.assertEqual(result.returncode, 0, result.stderr)

        tasks = {t["id"]: t for t in read_tasks(self.queue_file)}
        # Reverse edges rebuilt for the whole queue.
        self.assertEqual(tasks["a"]["blocks"], ["b"])
        self.assertEqual(tasks["b"]["blocks"], [])

    def test_sync_does_not_scan_plans_directory(self):
        """An invalid plan file on disk is ignored because sync never scans."""
        existing_plan = self.plans_dir / "existing.md"
        make_plan(existing_plan, "Existing task")
        # A bad plan exists on disk but is not in the queue.
        bad = self.plans_dir / "bad.md"
        bad.write_text("---\nsize: M\n---\n\n# Bad\n", encoding="utf-8")
        initial = {
            "tasks": [
                {
                    "id": "existing",
                    "title": "Existing task",
                    "plan_file": str(existing_plan),
                    "blocked_by": [],
                    "blocks": [],
                    "state": "ready",
                    "merge_commit": None,
                    "branch": None,
                    "worktree": None,
                    "completed_at": None,
                    "merged_at": None,
                }
            ]
        }
        self.queue_file.write_text(json.dumps(initial))

        result, _ = run_sync(
            self.root, self.queue_file, self.history_file, self.plans_dir
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        tasks = {t["id"]: t for t in read_tasks(self.queue_file)}
        self.assertIn("existing", tasks)
        self.assertNotIn("bad", tasks)


if __name__ == "__main__":
    unittest.main()
