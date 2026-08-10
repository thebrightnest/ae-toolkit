"""Scoped validation for init-queue: warn-and-skip unrelated plans, fail-closed on included plans."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]


def _seed_queue_from_plans(queue_file, plans_dir):
    """Simulate the explicit sprint-add record for init-queue tests."""
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


def _queue_is_empty_or_missing(queue_file):
    """Return True when the queue file is absent or holds an empty task list."""
    path = Path(queue_file)
    if not path.exists():
        return True
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return True
    if data == []:
        return True
    if isinstance(data, dict) and not data.get("tasks"):
        return True
    return False


def run_script(script_name, cwd, queue_file, history_file, plans_dir, prds_dir=None):
    """Run a queue script in an isolated environment and return its result."""
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

    if script_name == "init-queue" and _queue_is_empty_or_missing(queue_file):
        _seed_queue_from_plans(queue_file, plans_dir)

    module_name = script_name.replace("-", "_")
    cmd = [
        sys.executable,
        str(REPO_ROOT / "src" / "aet" / "cli" / f"{module_name}.py"),
        "--queue-file",
        str(queue_file),
        "--history-file",
        str(history_file),
        "--plans-dir",
        str(plans_dir),
    ]
    if prds_dir is not None:
        cmd += ["--prds-dir", str(prds_dir)]

    result = subprocess.run(cmd, cwd=str(cwd), env=env, capture_output=True, text=True)
    return result, log_file


def read_tasks(queue_file):
    """Read the task list from a queue file, regardless of wrapper format."""
    with open(queue_file, "r", encoding="utf-8") as f:
        data = json.load(f)
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
    lines.extend(["## Validation Steps", "- [ ] test_widget_creation verifies widget.py", ""])
    lines.extend(["---", "", "*Stage: plan-approved*"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class TestInitQueueScopedValidation(unittest.TestCase):
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

    def _seed_queue(self, *plan_names: str) -> None:
        """Write a minimal queue file containing the named plans."""
        tasks = []
        for name in plan_names:
            pf = self.plans_dir / name
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
        self.queue_file.write_text(json.dumps({"tasks": tasks}), encoding="utf-8")

    def test_settled_invalid_plan_is_skipped_silently(self):
        """A settled plan is skipped before validation; it does not block the rebuild."""
        make_plan(self.plans_dir / "active.md", "Active task")
        bad = self.plans_dir / "bad-settled.md"
        bad.write_text(
            "---\nsize: M\n---\n\n# Bad settled\n\n"
            "---\n\n*Stage: merged*\n",
            encoding="utf-8",
        )
        self._seed_queue("active.md", "bad-settled.md")

        result, _ = run_script(
            "init-queue",
            self.root,
            self.queue_file,
            self.history_file,
            self.plans_dir,
            self.prds_dir,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

        tasks = {t["id"]: t for t in read_tasks(self.queue_file)}
        self.assertIn("active", tasks)
        self.assertNotIn("bad-settled", tasks)
        self.assertIn("1 settled tasks skipped", result.stdout)

    def test_non_sprint_plans_not_in_queue_are_ignored(self):
        """Plans that were never added to the queue are not auto-added or validated."""
        make_plan(self.plans_dir / "active.md", "Active task")
        bad = self.plans_dir / "bad-draft.md"
        bad.write_text("---\nsize: M\n---\n\n# Bad draft\n", encoding="utf-8")
        self._seed_queue("active.md")

        result, _ = run_script(
            "init-queue",
            self.root,
            self.queue_file,
            self.history_file,
            self.plans_dir,
            self.prds_dir,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

        tasks = {t["id"]: t for t in read_tasks(self.queue_file)}
        self.assertIn("active", tasks)
        self.assertNotIn("bad-draft", tasks)
        self.assertNotIn("bad-draft.md", result.stderr)

    def test_included_invalid_plan_fails_closed(self):
        """An invalid plan already in the queue fails closed and prevents queue write."""
        bad = self.plans_dir / "bad-active.md"
        bad.write_text("---\nsize: M\n---\n\n# Bad active\n", encoding="utf-8")
        self._seed_queue("bad-active.md")

        result, _ = run_script(
            "init-queue",
            self.root,
            self.queue_file,
            self.history_file,
            self.plans_dir,
            self.prds_dir,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("bad-active.md", result.stderr)
        self.assertIn("missing id", result.stderr)

    def test_settled_plans_skipped_before_validation(self):
        """Settled-ness from the footer is checked before validating included plans."""
        make_plan(self.plans_dir / "active.md", "Active task")
        settled_bad = self.plans_dir / "settled-bad.md"
        settled_bad.write_text(
            "---\nsize: M\n---\n\n# Settled bad\n\n"
            "---\n\n*Stage: merged*\n",
            encoding="utf-8",
        )
        draft_bad = self.plans_dir / "draft-bad.md"
        draft_bad.write_text("---\nsize: M\n---\n\n# Draft bad\n", encoding="utf-8")
        self._seed_queue("active.md", "settled-bad.md")

        result, _ = run_script(
            "init-queue",
            self.root,
            self.queue_file,
            self.history_file,
            self.plans_dir,
            self.prds_dir,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

        tasks = {t["id"]: t for t in read_tasks(self.queue_file)}
        self.assertIn("active", tasks)
        self.assertNotIn("settled-bad", tasks)
        self.assertNotIn("draft-bad", tasks)


if __name__ == "__main__":
    unittest.main()
