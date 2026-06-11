"""Tests for verifier module."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "aet-work" / "lib"))

import tempfile
import unittest

from verifier import read_plan_stage


class TestVerifier(unittest.TestCase):
    def test_read_plan_stage(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Plan\n\n*Stage: implemented*\n")
            path = f.name

        stage = read_plan_stage(path)
        self.assertEqual(stage, "implemented")

    def test_read_plan_stage_missing(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Plan\n")
            path = f.name

        stage = read_plan_stage(path)
        self.assertIsNone(stage)

    def test_read_plan_stage_no_file(self):
        self.assertIsNone(read_plan_stage("/nonexistent/path.md"))


if __name__ == "__main__":
    unittest.main()
