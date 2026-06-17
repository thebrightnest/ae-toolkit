"""Behavior-driven tests for aet-work/bin/init-queue and aet-work/bin/sync."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent


def run_script(script_name, cwd, queue_file, archive_file, plans_dir, prds_dir=None):
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

    cmd = [
        sys.executable,
        str(REPO_ROOT / "aet-work" / "bin" / script_name),
        "--queue-file",
        str(queue_file),
        "--archive-file",
        str(archive_file),
        "--plans-dir",
        str(plans_dir),
    ]
    if prds_dir is not None:
        cmd += ["--prds-dir", str(prds_dir)]

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


def make_plan(path, title, blocked_by=None, references=None):
    """Write a minimal plan markdown file."""
    content = f"---\ntitle: {title}\n---\n\n# {title}\n"
    if blocked_by:
        content += "\n## Blocked by\n" + "\n".join(f"- {b}" for b in blocked_by) + "\n"
    if references:
        content += "\n## References\n" + "\n".join(f"- [{r}]({r})" for r in references) + "\n"
    content += "\n---\n\n*Stage: plan-approved*\n"
    path.write_text(content)


class TestInitQueue(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.plans_dir = self.root / "plans"
        self.prds_dir = self.root / "prds"
        self.queue_file = self.root / "work-queue.json"
        self.archive_file = self.root / "work-archive.json"
        self.plans_dir.mkdir()
        self.prds_dir.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_rebuilds_facts_with_planned_status_and_wrapper(self):
        """init-queue creates a wrapped queue of planned facts with blocks inverse."""
        make_plan(self.plans_dir / "feat-001.md", "First task")
        make_plan(self.plans_dir / "feat-002.md", "Second task", blocked_by=["feat-001"])
        (self.prds_dir / "latest.md").write_text("# Latest PRD\n")

        result, _ = run_script(
            "init-queue", self.root, self.queue_file, self.archive_file, self.plans_dir, self.prds_dir
        )
        self.assertEqual(result.returncode, 0, result.stderr)

        data = read_queue_dict(self.queue_file)
        self.assertIsInstance(data, dict)
        self.assertIn("queue_updated_at", data)
        self.assertEqual(data.get("source_prd"), str(self.prds_dir / "latest.md"))

        tasks = {t["id"]: t for t in data["tasks"]}
        self.assertEqual(tasks["feat-001"]["status"], "planned")
        self.assertEqual(tasks["feat-002"]["status"], "planned")
        self.assertEqual(tasks["feat-002"]["blocked_by"], ["feat-001"])
        self.assertEqual(tasks["feat-001"]["blocks"], ["feat-002"])

    def test_preserves_terminal_status_and_metadata_and_resets_non_terminal(self):
        """Existing terminal tasks keep status/metadata; non-terminal become planned."""
        make_plan(self.plans_dir / "old.md", "Old task")
        make_plan(self.plans_dir / "new.md", "New task")
        make_plan(self.plans_dir / "stale.md", "Stale task")
        initial = {
            "source_prd": "docs/prds/old.md",
            "queue_updated_at": "2026-01-01T00:00:00Z",
            "tasks": [
                {
                    "id": "old",
                    "title": "Old task",
                    "plan_file": str(self.plans_dir / "old.md"),
                    "blocked_by": [],
                    "blocks": [],
                    "status": "merged",
                    "merge_commit": "abc1234",
                    "merge_strategy": "squash",
                    "branch": "feat-old",
                    "worktree": "/worktrees/old",
                    "completed_at": "2026-01-01T00:00:00Z",
                    "merged_at": "2026-01-01T00:00:00Z",
                },
                {
                    "id": "stale",
                    "title": "Stale task",
                    "plan_file": str(self.plans_dir / "stale.md"),
                    "blocked_by": [],
                    "blocks": [],
                    "status": "blocked",
                    "merge_commit": None,
                    "branch": None,
                    "worktree": None,
                    "completed_at": None,
                    "merged_at": None,
                },
            ],
        }
        self.queue_file.write_text(json.dumps(initial))

        result, _ = run_script(
            "init-queue", self.root, self.queue_file, self.archive_file, self.plans_dir, self.prds_dir
        )
        self.assertEqual(result.returncode, 0, result.stderr)

        tasks = {t["id"]: t for t in read_tasks(self.queue_file)}
        # Terminal task preserved.
        self.assertEqual(tasks["old"]["status"], "merged")
        self.assertEqual(tasks["old"]["merge_commit"], "abc1234")
        self.assertEqual(tasks["old"]["merge_strategy"], "squash")
        self.assertEqual(tasks["old"]["branch"], "feat-old")
        self.assertEqual(tasks["old"]["worktree"], "/worktrees/old")
        # Non-terminal task normalized to planned.
        self.assertEqual(tasks["stale"]["status"], "planned")

    def test_does_not_call_derive(self):
        """init-queue must not invoke aet-state derive."""
        make_plan(self.plans_dir / "feat-001.md", "First task")
        result, log_file = run_script(
            "init-queue", self.root, self.queue_file, self.archive_file, self.plans_dir, self.prds_dir
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        derive_calls = []
        if log_file.exists():
            for line in log_file.read_text().splitlines():
                if "derive" in line:
                    derive_calls.append(line)
        self.assertEqual(derive_calls, [])


class TestSync(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.plans_dir = self.root / "plans"
        self.prds_dir = self.root / "prds"
        self.queue_file = self.root / "work-queue.json"
        self.archive_file = self.root / "work-archive.json"
        self.plans_dir.mkdir()
        self.prds_dir.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_appends_only_new_plan_and_preserves_existing(self):
        """sync is append-only and leaves existing task statuses untouched."""
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
                    "status": "in-progress",
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

        result, _ = run_script(
            "sync", self.root, self.queue_file, self.archive_file, self.plans_dir, None
        )
        self.assertEqual(result.returncode, 0, result.stderr)

        data = read_queue_dict(self.queue_file)
        self.assertIsInstance(data, dict)
        tasks = {t["id"]: t for t in data["tasks"]}

        # Existing task preserved.
        self.assertEqual(tasks["existing"]["status"], "in-progress")
        self.assertEqual(tasks["existing"]["branch"], "feat-existing")
        # New task appended as planned.
        self.assertEqual(tasks["new"]["status"], "planned")
        self.assertEqual(tasks["new"]["blocked_by"], ["existing"])
        # blocks inverse recomputed for the whole queue.
        self.assertEqual(tasks["existing"]["blocks"], ["new"])

    def test_reports_drift_without_mutating_status(self):
        """Missing plan files are reported as drift; stored status is not changed."""
        initial = {
            "tasks": [
                {
                    "id": "missing",
                    "title": "Missing task",
                    "plan_file": "docs/plans/missing.md",
                    "blocked_by": [],
                    "blocks": [],
                    "status": "in-progress",
                    "merge_commit": None,
                    "branch": "feat-missing",
                    "worktree": None,
                    "completed_at": None,
                    "merged_at": None,
                }
            ]
        }
        self.queue_file.write_text(json.dumps(initial))

        result, _ = run_script(
            "sync", self.root, self.queue_file, self.archive_file, self.plans_dir, None
        )
        self.assertEqual(result.returncode, 0, result.stderr)

        tasks = {t["id"]: t for t in read_tasks(self.queue_file)}
        self.assertEqual(tasks["missing"]["status"], "in-progress")
        self.assertIn("drift", result.stdout.lower())

    def test_normalizes_merge_verified_to_merged(self):
        """sync normalizes legacy merge_verified statuses to merged."""
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

        result, _ = run_script(
            "sync", self.root, self.queue_file, self.archive_file, self.plans_dir, None
        )
        self.assertEqual(result.returncode, 0, result.stderr)

        tasks = {t["id"]: t for t in read_tasks(self.queue_file)}
        self.assertEqual(tasks["legacy"]["status"], "merged")

    def test_does_not_call_derive(self):
        """sync must not invoke aet-state derive."""
        make_plan(self.plans_dir / "feat-001.md", "First task")
        result, log_file = run_script(
            "sync", self.root, self.queue_file, self.archive_file, self.plans_dir, None
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        derive_calls = []
        if log_file.exists():
            for line in log_file.read_text().splitlines():
                if "derive" in line:
                    derive_calls.append(line)
        self.assertEqual(derive_calls, [])


if __name__ == "__main__":
    unittest.main()
