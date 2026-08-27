"""Tests for the work_class plan-frontmatter attribute (twe-01)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]
from aet import plan_parser  # noqa: E402


def make_plan(path: Path, work_class: str | None = None) -> None:
    """Write a minimal plan with an optional work_class frontmatter key."""
    lines = ["---", "id: " + path.stem, "size: M"]
    if work_class is not None:
        lines.append(f"work_class: {work_class}")
    lines.extend(["---", "", "# Title", ""])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class TestWorkClassAttribute(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_valid_work_class_parsed_onto_task(self):
        """A valid work_class is carried onto the queue task record."""
        plan = self.root / "twe-01.md"
        make_plan(plan, work_class="critical")
        task = plan_parser.new_task_from_plan(plan)
        self.assertEqual(task["work_class"], "critical")

    def test_absent_work_class_defaults_unclassified(self):
        """A missing work_class defaults to unclassified on the task record."""
        plan = self.root / "twe-01.md"
        make_plan(plan)
        task = plan_parser.new_task_from_plan(plan)
        self.assertEqual(task["work_class"], "unclassified")

    def test_invalid_work_class_rejected_at_intake(self):
        """A present but non-tier work_class produces a named intake error."""
        plan = self.root / "twe-01.md"
        make_plan(plan, work_class="urgent")
        errors = plan_parser.intake_validation_errors([plan])
        self.assertEqual(len(errors), 1)
        self.assertIn("work_class must be one of trivial|normal|critical", errors[0][1])
        self.assertIn("urgent", errors[0][1])

    def test_absent_work_class_is_not_an_intake_error(self):
        """A missing work_class is legal and produces no intake error."""
        plan = self.root / "twe-01.md"
        make_plan(plan)
        errors = plan_parser.intake_validation_errors([plan])
        self.assertEqual(errors, [])


class TestVerifyRoutingKey(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_verify_skip_requires_reason(self):
        """verify: skipped without verify_reason fails intake validation."""
        plan = self.root / "poh-02.md"
        lines = [
            "---",
            "id: poh-02",
            "size: S",
            "verify: skipped",
            "---",
            "",
            "# Title",
            "",
        ]
        plan.write_text("\n".join(lines) + "\n", encoding="utf-8")
        errors = plan_parser.intake_validation_errors([plan])
        self.assertEqual(len(errors), 1)
        self.assertIn("verify_reason is required when verify is skipped", errors[0][1])

    def test_verify_skip_with_reason_passes(self):
        """verify: skipped with verify_reason passes intake validation."""
        plan = self.root / "poh-02.md"
        lines = [
            "---",
            "id: poh-02",
            "size: S",
            "verify: skipped",
            "verify_reason: unit tests cover all invariant changes",
            "---",
            "",
            "# Title",
            "",
        ]
        plan.write_text("\n".join(lines) + "\n", encoding="utf-8")
        errors = plan_parser.intake_validation_errors([plan])
        self.assertEqual(errors, [])

    def test_verify_required_passes(self):
        """verify: required passes intake validation."""
        plan = self.root / "poh-02.md"
        lines = [
            "---",
            "id: poh-02",
            "size: S",
            "verify: required",
            "---",
            "",
            "# Title",
            "",
        ]
        plan.write_text("\n".join(lines) + "\n", encoding="utf-8")
        errors = plan_parser.intake_validation_errors([plan])
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
