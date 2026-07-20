#!/usr/bin/env python3
"""Tests for src/aet/cli/aet-state.py — standard-library only."""

import tempfile
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path

AET_STATE_PY = Path(__file__).resolve().parents[1] / "src" / "aet" / "cli" / "aet-state.py"

aet_state = SourceFileLoader("aet_state", str(AET_STATE_PY)).load_module()


class TestDeriveStatus(unittest.TestCase):
    def setUp(self):
        self._orig_branch_exists = aet_state.branch_exists
        self._orig_is_ancestor = aet_state.is_ancestor_of_main
        self.branch_exists_map = {}
        self.ancestor_map = {}

        def fake_branch_exists(branch, cwd=None):
            return self.branch_exists_map.get(branch, False)

        def fake_is_ancestor(commit, cwd=None):
            return self.ancestor_map.get(commit, False)

        aet_state.branch_exists = fake_branch_exists
        aet_state.is_ancestor_of_main = fake_is_ancestor

    def tearDown(self):
        aet_state.branch_exists = self._orig_branch_exists
        aet_state.is_ancestor_of_main = self._orig_is_ancestor

    def test_missing_plan(self):
        task = {"id": "t1", "plan_file": "docs/plans/missing.md"}
        derived = aet_state.derive_status(task)
        self.assertFalse(derived["plan_exists"])
        self.assertEqual(derived["derived_status"], "unknown")

    def test_planned_no_branch(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            plan = Path(tmpdir) / "plan.md"
            plan.write_text("# Plan\n")
            task = {"id": "t1", "plan_file": str(plan)}
            derived = aet_state.derive_status(task)
            self.assertTrue(derived["plan_exists"])
            self.assertEqual(derived["derived_status"], "planned")

    def test_in_progress_with_branch(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            plan = Path(tmpdir) / "plan.md"
            plan.write_text("# Plan\n")
            self.branch_exists_map["feat-1"] = True
            task = {"id": "t1", "plan_file": str(plan), "branch": "feat-1"}
            derived = aet_state.derive_status(task)
            self.assertEqual(derived["derived_status"], "in-progress")

    def test_merged_when_ancestor(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            plan = Path(tmpdir) / "plan.md"
            plan.write_text("# Plan\n")
            self.branch_exists_map["feat-1"] = True
            self.ancestor_map["feat-1"] = True
            task = {"id": "t1", "plan_file": str(plan), "branch": "feat-1"}
            derived = aet_state.derive_status(task)
            self.assertEqual(derived["derived_status"], "merged")
            self.assertTrue(derived["on_main"])

    def test_merged_by_merge_commit(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            plan = Path(tmpdir) / "plan.md"
            plan.write_text("# Plan\n")
            self.ancestor_map["abc123"] = True
            task = {"id": "t1", "plan_file": str(plan), "merge_commit": "abc123"}
            derived = aet_state.derive_status(task)
            self.assertEqual(derived["derived_status"], "merged")

    def test_warning_when_done_not_on_main(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            plan = Path(tmpdir) / "plan.md"
            plan.write_text("# Plan\n")
            self.branch_exists_map["feat-1"] = True
            task = {
                "id": "t1",
                "plan_file": str(plan),
                "branch": "feat-1",
                "status": "done",
            }
            derived = aet_state.derive_status(task)
            self.assertIn("warning", derived["derived_status"])
            self.assertIn("done without merge verification", derived["warnings"])


class TestUpdatePlanFooter(unittest.TestCase):
    def test_replaces_existing_stage(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            plan = Path(tmpdir) / "plan.md"
            plan.write_text("# Plan\n\n*Stage: plan-approved*\n")
            aet_state.update_plan_footer(str(plan), "implemented")
            self.assertIn("_Stage: implemented_", plan.read_text())
            self.assertNotIn("_Stage: plan-approved_", plan.read_text())

    def test_appends_stage_when_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            plan = Path(tmpdir) / "plan.md"
            plan.write_text("# Plan\n")
            aet_state.update_plan_footer(str(plan), "reviewed")
            self.assertIn("_Stage: reviewed_", plan.read_text())


if __name__ == "__main__":
    unittest.main(verbosity=2)
