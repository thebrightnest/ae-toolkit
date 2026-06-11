"""Tests for pipeline module."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "aet-work" / "lib"))

import unittest

from pipeline import STAGE_MAP, get_next_stage, get_stage, group_stages_by_session


class TestPipeline(unittest.TestCase):
    def test_stage_map(self):
        self.assertIn("plan-approved", STAGE_MAP)
        self.assertIn("implemented", STAGE_MAP)
        self.assertIn("synced", STAGE_MAP)

    def test_get_stage(self):
        stage = get_stage("plan-approved")
        self.assertIsNotNone(stage)
        self.assertEqual(stage.name, "plan-approved")
        self.assertEqual(stage.skills, ["aet-tdd", "aet-implement"])

    def test_get_stage_missing(self):
        self.assertIsNone(get_stage("nonexistent"))

    def test_get_next_stage(self):
        next_stage = get_next_stage("plan-approved")
        self.assertIsNotNone(next_stage)
        self.assertEqual(next_stage.name, "implemented")

    def test_get_next_stage_terminal(self):
        self.assertIsNone(get_next_stage("synced"))

    def test_group_minimal(self):
        groups = group_stages_by_session("minimal")
        self.assertEqual(len(groups), 1)

    def test_group_standard(self):
        groups = group_stages_by_session("standard")
        self.assertEqual(len(groups), 3)
        self.assertEqual(groups[0][0].name, "plan-approved")
        self.assertEqual(groups[0][-1].name, "implemented")
        self.assertEqual(groups[1][0].name, "qa-complete")
        self.assertEqual(groups[2][0].name, "reviewed")

    def test_group_full(self):
        groups = group_stages_by_session("full")
        self.assertEqual(len(groups), 5)
        for g in groups:
            self.assertEqual(len(g), 1)


if __name__ == "__main__":
    unittest.main()
