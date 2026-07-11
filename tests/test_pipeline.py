"""Tests for pipeline module."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "aet-work" / "lib"))

import unittest

import pipeline
from pipeline import STAGE_MAP, STAGES, get_next_stage, get_stage, group_stages_by_session


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


class TestStageGateKeys(unittest.TestCase):
    """Stage routing is pure data: gate_key names the plan-frontmatter key."""

    def test_gated_stages_carry_their_frontmatter_key(self):
        self.assertEqual(get_stage("reviewed").gate_key, "security_review")
        self.assertEqual(get_stage("secure").gate_key, "docs_sync")

    def test_ungated_stages_have_no_gate_key(self):
        for name in ("plan-approved", "implemented", "qa-complete", "synced"):
            self.assertIsNone(get_stage(name).gate_key)

    def test_gate_key_is_serializable_data(self):
        for stage in STAGES:
            self.assertIsInstance(stage.gate_key, (str, type(None)))

    def test_no_runtime_judgment_left_in_the_engine(self):
        # The conditional callables and their heuristic helpers are gone;
        # routing happens once at plan time, never inside the engine.
        for stage in STAGES:
            self.assertFalse(hasattr(stage, "conditional"))
        self.assertFalse(hasattr(pipeline, "_security_sensitive"))
        self.assertFalse(hasattr(pipeline, "_divergences_found"))


if __name__ == "__main__":
    unittest.main()
