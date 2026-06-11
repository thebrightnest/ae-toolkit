#!/usr/bin/env python3
"""Tests for aet-state.py — standard-library only."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

AET_STATE = Path(__file__).resolve().parents[1] / "aet-work" / "bin" / "aet-state"


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


if __name__ == "__main__":
    unittest.main(verbosity=2)
