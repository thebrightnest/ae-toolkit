#!/usr/bin/env python3
"""Tests for aet-state.py — standard-library only."""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

AET_STATE = Path(__file__).resolve().parents[1] / "aet-work" / "bin" / "aet-state"
QUEUE_PY = Path(__file__).resolve().parents[1] / "aet-work" / "lib" / "queue.py"

spec = importlib.util.spec_from_file_location("queue", QUEUE_PY)
queue = importlib.util.module_from_spec(spec)
spec.loader.exec_module(queue)
read_archive = queue.read_archive
write_archive = queue.write_archive
archive_tasks = queue.archive_tasks


class TestAetState(unittest.TestCase):
    def run_cmd(self, *args, cwd=None, check=True):
        cmd = [sys.executable, str(AET_STATE), *args]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=cwd,
            check=False,
        )
        if check and result.returncode != 0:
            self.fail(f"Command failed: {' '.join(args)}\nstdout: {result.stdout}\nstderr: {result.stderr}")
        return result

    def sample_queue(self, tmpdir):
        q = [
            {
                "id": "test-01",
                "title": "Test task one",
                "plan_file": "docs/plans/test-01.md",
                "status": "planned",
                "blocks": [],
                "blocked_by": [],
                "branch": "test-01",
                "worktree": None,
                "merge_commit": None,
                "completed_at": None,
                "merged_at": None,
            }
        ]
        p = Path(tmpdir) / "queue.json"
        p.write_text(json.dumps(q, indent=2))
        return p

    def test_help(self):
        result = self.run_cmd("--help")
        self.assertIn("derive", result.stdout)
        self.assertIn("transition", result.stdout)
        self.assertIn("validate", result.stdout)
        self.assertIn("sync-footers", result.stdout)
        self.assertIn("--dry-run", result.stdout)

    def test_derive_with_sample_queue(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            qpath = self.sample_queue(tmpdir)
            # Create a fake plan file so derivation sees it
            plan_dir = Path(tmpdir) / "docs" / "plans"
            plan_dir.mkdir(parents=True)
            (plan_dir / "test-01.md").write_text("# Plan\n")

            result = self.run_cmd("derive", str(qpath), cwd=tmpdir)
            data = json.loads(result.stdout)
            self.assertIn("test-01", data)
            # Since we can't guarantee git branch exists, at minimum plan exists
            self.assertIn("derived_status", data["test-01"])

    def test_validate_allows_legal_transition(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            qpath = self.sample_queue(tmpdir)
            result = self.run_cmd("validate", "test-01", "planned", "in-progress", str(qpath), cwd=tmpdir)
            self.assertEqual(result.returncode, 0)

    def test_validate_rejects_merged_without_ancestry(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            qpath = self.sample_queue(tmpdir)
            # Set status to in-progress first
            q = json.loads(qpath.read_text())
            q[0]["status"] = "in-progress"
            qpath.write_text(json.dumps(q, indent=2))
            result = self.run_cmd(
                "validate", "test-01", "in-progress", "merged", str(qpath),
                cwd=tmpdir, check=False,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("ancestor", result.stderr.lower())

    def test_validate_rejects_abandoned_without_reason_clear(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            qpath = self.sample_queue(tmpdir)
            # Set status to abandoned with a reason
            q = json.loads(qpath.read_text())
            q[0]["status"] = "abandoned"
            q[0]["failure_reason"] = "Some reason"
            qpath.write_text(json.dumps(q, indent=2))
            result = self.run_cmd(
                "validate", "test-01", "abandoned", "planned", str(qpath),
                cwd=tmpdir, check=False,
            )
            self.assertEqual(result.returncode, 1)

    def test_validate_allows_abandoned_to_planned_when_reason_cleared(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            qpath = self.sample_queue(tmpdir)
            q = json.loads(qpath.read_text())
            q[0]["status"] = "abandoned"
            q[0]["failure_reason"] = None
            qpath.write_text(json.dumps(q, indent=2))
            result = self.run_cmd(
                "validate", "test-01", "abandoned", "planned", str(qpath),
                cwd=tmpdir, check=False,
            )
            self.assertEqual(result.returncode, 0)

    def test_transition_applies_legal_change(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            qpath = self.sample_queue(tmpdir)
            result = self.run_cmd("transition", "test-01", "planned", "in-progress", str(qpath), cwd=tmpdir)
            self.assertEqual(result.returncode, 0)
            q = json.loads(qpath.read_text())
            self.assertEqual(q[0]["status"], "in-progress")

    def test_transition_rejects_illegal_change(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            qpath = self.sample_queue(tmpdir)
            result = self.run_cmd(
                "transition", "test-01", "in-progress", "merged", str(qpath),
                cwd=tmpdir, check=False,
            )
            self.assertEqual(result.returncode, 1)
            q = json.loads(qpath.read_text())
            self.assertEqual(q[0]["status"], "planned")  # unchanged

    def test_sync_footers_updates_plan_and_queue(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            qpath = self.sample_queue(tmpdir)
            plan_dir = Path(tmpdir) / "docs" / "plans"
            plan_dir.mkdir(parents=True)
            plan_path = plan_dir / "test-01.md"
            plan_path.write_text("# Plan\n\n*Stage: planned*\n")

            result = self.run_cmd("sync-footers", str(plan_path), "implemented", str(qpath), cwd=tmpdir)
            self.assertEqual(result.returncode, 0)

            content = plan_path.read_text()
            self.assertIn("*Stage: implemented*", content)

            q = json.loads(qpath.read_text())
            self.assertEqual(q[0]["status"], "implemented")

    def test_dry_run_does_not_mutate(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            qpath = self.sample_queue(tmpdir)
            before = qpath.read_text()
            result = self.run_cmd(
                "--dry-run", "transition", "test-01", "planned", "in-progress", str(qpath),
                cwd=tmpdir, check=False,
            )
            after = qpath.read_text()
            self.assertEqual(before, after)

    def test_derive_done_without_merge_is_flagged(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            qpath = self.sample_queue(tmpdir)
            q = json.loads(qpath.read_text())
            q[0]["status"] = "done"
            q[0]["merge_commit"] = None
            qpath.write_text(json.dumps(q, indent=2))

            result = self.run_cmd("derive", str(qpath), cwd=tmpdir)
            data = json.loads(result.stdout)
            self.assertIn("warning", data["test-01"].get("derived_status", "").lower())


class TestArchiveHelpers(unittest.TestCase):
    def test_read_archive_missing_returns_empty_list(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "archive.json"
            self.assertFalse(path.exists())
            tasks = read_archive(str(path))
            self.assertEqual(tasks, [])

    def test_write_archive_creates_file_with_timestamp(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "archive.json"
            write_archive(str(path), [{"id": "t1"}])
            self.assertTrue(path.exists())
            data = json.loads(path.read_text())
            self.assertIn("archived_at", data)
            self.assertEqual(data["tasks"], [{"id": "t1"}])

    def test_archive_tasks_moves_terminal_tasks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            queue_file = Path(tmpdir) / "queue.json"
            archive_file = Path(tmpdir) / "archive.json"
            queue = [
                {"id": "active", "status": "unblocked", "blocked_by": []},
                {"id": "done", "status": "done", "blocked_by": []},
                {"id": "merged", "status": "merged", "blocked_by": []},
                {"id": "abandoned", "status": "abandoned", "blocked_by": []},
            ]
            queue_file.write_text(json.dumps(queue, indent=2))
            new_queue, archived = archive_tasks(str(queue_file), str(archive_file))
            self.assertEqual(len(new_queue), 1)
            self.assertEqual(new_queue[0]["id"], "active")
            self.assertEqual({t["id"] for t in archived}, {"done", "merged", "abandoned"})
            archive_data = json.loads(archive_file.read_text())
            self.assertEqual(len(archive_data["tasks"]), 3)

    def test_archive_tasks_appends_to_existing_archive(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            queue_file = Path(tmpdir) / "queue.json"
            archive_file = Path(tmpdir) / "archive.json"
            write_archive(str(archive_file), [{"id": "old"}])
            queue = [{"id": "done", "status": "done", "blocked_by": []}]
            queue_file.write_text(json.dumps(queue, indent=2))
            new_queue, archived = archive_tasks(str(queue_file), str(archive_file))
            self.assertEqual(len(new_queue), 0)
            self.assertEqual(archived[0]["id"], "done")
            archive_data = json.loads(archive_file.read_text())
            self.assertEqual([t["id"] for t in archive_data["tasks"]], ["old", "done"])

    def test_archive_tasks_skips_terminal_with_active_dependents(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            queue_file = Path(tmpdir) / "queue.json"
            archive_file = Path(tmpdir) / "archive.json"
            queue = [
                {"id": "dep", "status": "merged", "blocked_by": []},
                {"id": "active", "status": "blocked", "blocked_by": ["dep"]},
            ]
            queue_file.write_text(json.dumps(queue, indent=2))
            new_queue, archived = archive_tasks(str(queue_file), str(archive_file))
            self.assertEqual(len(new_queue), 2)
            self.assertEqual(archived, [])

    def test_archive_tasks_normalizes_merge_verified(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            queue_file = Path(tmpdir) / "queue.json"
            archive_file = Path(tmpdir) / "archive.json"
            queue = [
                {"id": "legacy", "status": "merge_verified", "blocked_by": []},
            ]
            queue_file.write_text(json.dumps(queue, indent=2))
            new_queue, archived = archive_tasks(str(queue_file), str(archive_file))
            self.assertEqual(len(new_queue), 0)
            self.assertEqual(archived[0]["status"], "merged")


class TestAetStateArchive(unittest.TestCase):
    def run_cmd(self, *args, cwd=None, check=True):
        cmd = [sys.executable, str(AET_STATE), *args]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=cwd,
            check=False,
        )
        if check and result.returncode != 0:
            self.fail(f"Command failed: {' '.join(args)}\nstdout: {result.stdout}\nstderr: {result.stderr}")
        return result

    def test_archive_command(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            qpath = Path(tmpdir) / "queue.json"
            apath = Path(tmpdir) / "archive.json"
            queue = [
                {"id": "active", "status": "unblocked", "blocked_by": []},
                {"id": "done", "status": "done", "blocked_by": []},
                {"id": "merged", "status": "merged", "blocked_by": []},
                {"id": "abandoned", "status": "abandoned", "blocked_by": []},
            ]
            qpath.write_text(json.dumps(queue, indent=2))

            result = self.run_cmd("archive", str(qpath), str(apath), cwd=tmpdir)
            self.assertIn("Archived 3 tasks", result.stdout)
            self.assertIn("Active queue: 1 tasks remaining", result.stdout)

            queue_after = json.loads(qpath.read_text())
            self.assertEqual(len(queue_after), 1)
            self.assertEqual(queue_after[0]["id"], "active")

            archive_data = json.loads(apath.read_text())
            self.assertEqual(len(archive_data["tasks"]), 3)

    def test_archive_command_skips_dependents(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            qpath = Path(tmpdir) / "queue.json"
            apath = Path(tmpdir) / "archive.json"
            queue = [
                {"id": "dep", "status": "merged", "blocked_by": []},
                {"id": "active", "status": "blocked", "blocked_by": ["dep"]},
            ]
            qpath.write_text(json.dumps(queue, indent=2))

            result = self.run_cmd("archive", str(qpath), str(apath), cwd=tmpdir)
            self.assertIn("Archived 0 tasks", result.stdout)
            self.assertIn("Skipped 1 terminal tasks with active dependents", result.stdout)

            queue_after = json.loads(qpath.read_text())
            self.assertEqual(len(queue_after), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
