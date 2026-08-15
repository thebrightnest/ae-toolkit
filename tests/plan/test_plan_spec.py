"""Tests for portable plan spec extraction and rendering (R-19)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from aet import plan_parser


class TestExtractPlanSpec(unittest.TestCase):
    def _write_plan(self, root: Path, name: str, content: str) -> Path:
        path = root / "docs" / "plans" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def test_extracts_routing_frontmatter(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_plan(
                Path(tmp),
                "r19.md",
                "---\n"
                "id: r19\n"
                "size: M\n"
                "pipeline: full\n"
                "security_review: required\n"
                "docs_sync: skipped\n"
                "docs_sync_reason: docs live in wiki\n"
                "work_class: critical\n"
                "---\n\n"
                "# Plan: The spec travels\n\n"
                "## Context\n\n"
                "PRD: docs/prds/open-work-board-prd.md\n\n"
                "## Task List\n\n"
                "1. Carry the spec (traces: R-19)\n"
                "2. Render the plan (traces: R-19)\n\n"
                "## Validation Steps\n\n"
                "- [ ] Two-machine test passes\n\n"
                "---\n\n"
                "*Stage: plan-approved*\n",
            )
            spec = plan_parser.extract_plan_spec(path)
            assert spec is not None
            fm = spec["frontmatter"]
            self.assertEqual(fm["id"], "r19")
            self.assertEqual(fm["size"], "M")
            self.assertEqual(fm["pipeline"], "full")
            self.assertEqual(fm["security_review"], "required")
            self.assertEqual(fm["docs_sync"], "skipped")
            self.assertEqual(fm["work_class"], "critical")
            self.assertEqual(spec["title"], "Plan: The spec travels")
            self.assertEqual(
                spec["tasks"],
                [
                    "1. Carry the spec (traces: R-19)",
                    "2. Render the plan (traces: R-19)",
                ],
            )
            self.assertIn("## Context", spec["body"])
            self.assertIn("## Validation Steps", spec["body"])
            self.assertNotIn("Stage:", spec["body"])

    def test_returns_none_for_missing_file(self):
        spec = plan_parser.extract_plan_spec(Path("/nonexistent/docs/plans/x.md"))
        self.assertIsNone(spec)

    def test_new_task_carries_spec(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_plan(
                Path(tmp),
                "r19.md",
                "---\n"
                "id: r19\n"
                "size: S\n"
                "pipeline: standard\n"
                "---\n\n"
                "# Title\n\n"
                "## Task List\n\n"
                "- [ ] one\n\n"
                "---\n\n"
                "*Stage: plan-approved*\n",
            )
            task = plan_parser.new_task_from_plan(path)
            self.assertIn("spec", task)
            self.assertEqual(task["spec"]["frontmatter"]["pipeline"], "standard")
            self.assertEqual(task["spec"]["tasks"], ["- [ ] one"])


class TestExtractPlanSpecFromText(unittest.TestCase):
    """The spec can be built from plan text that never touches the filesystem.

    The backfill migration reads deleted plans out of a git blob, so extraction
    must not require a path on disk.
    """

    def test_builds_spec_from_text(self):
        spec = plan_parser.extract_plan_spec_from_text(
            "---\n"
            "id: owb-09\n"
            "size: L\n"
            "pipeline: full\n"
            "security_review: skipped\n"
            "docs_sync: required\n"
            "---\n\n"
            "# Plan: Recovered From a Blob\n\n"
            "## Context\n\n"
            "Deleted by b95538dd.\n\n"
            "## Task List\n\n"
            "1. Recover the spec (traces: R-19)\n\n"
            "---\n\n"
            "*Stage: plan-approved*\n",
            "owb-09",
        )
        assert spec is not None
        self.assertEqual(spec["frontmatter"]["id"], "owb-09")
        self.assertEqual(spec["frontmatter"]["size"], "L")
        self.assertEqual(spec["frontmatter"]["security_review"], "skipped")
        self.assertEqual(spec["frontmatter"]["docs_sync"], "required")
        self.assertEqual(spec["title"], "Plan: Recovered From a Blob")
        self.assertEqual(spec["tasks"], ["1. Recover the spec (traces: R-19)"])
        self.assertIn("## Context", spec["body"])
        self.assertNotIn("Stage:", spec["body"])

    def test_falls_back_to_stem_when_no_title(self):
        spec = plan_parser.extract_plan_spec_from_text(
            "---\nid: owb-09\n---\n\nno heading here\n", "owb-09"
        )
        assert spec is not None
        self.assertEqual(spec["title"], "owb-09")


class TestRenderPlan(unittest.TestCase):
    def test_renders_plan_from_spec(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "docs" / "plans" / "r19.md"
            task = {
                "id": "r19",
                "spec": {
                    "frontmatter": {
                        "id": "r19",
                        "size": "M",
                        "pipeline": "full",
                        "security_review": "required",
                        "docs_sync": "skipped",
                    },
                    "title": "Plan: The spec travels",
                    "body": "## Task List\n\n1. Do work (traces: R-19)\n",
                    "tasks": ["1. Do work (traces: R-19)"],
                },
            }
            rendered = plan_parser.render_plan(out, task)
            self.assertTrue(rendered)
            text = out.read_text(encoding="utf-8")
            self.assertIn("id: r19", text)
            self.assertIn("size: M", text)
            self.assertIn("pipeline: full", text)
            self.assertIn("security_review: required", text)
            self.assertIn("docs_sync: skipped", text)
            self.assertIn("# Plan: The spec travels", text)
            self.assertIn("## Task List", text)
            self.assertIn("1. Do work (traces: R-19)", text)
            self.assertNotIn("Stage:", text)

    def test_noop_when_spec_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "docs" / "plans" / "r19.md"
            rendered = plan_parser.render_plan(out, {"id": "r19"})
            self.assertFalse(rendered)
            self.assertFalse(out.exists())


class TestTaskRoutingData(unittest.TestCase):
    def test_prefers_spec_frontmatter(self):
        task = {
            "id": "r19",
            "plan_file": "docs/plans/old.md",
            "spec": {"frontmatter": {"pipeline": "full", "security_review": "skipped"}},
        }
        data = plan_parser.task_routing_data(task)
        self.assertEqual(data["pipeline"], "full")
        self.assertEqual(data["security_review"], "skipped")

    def test_falls_back_to_plan_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "old.md"
            path.write_text(
                "---\n"
                "id: old\n"
                "size: S\n"
                "pipeline: minimal\n"
                "---\n\n"
                "# Old\n",
                encoding="utf-8",
            )
            task = {"id": "old", "plan_file": str(path)}
            data = plan_parser.task_routing_data(task)
            self.assertEqual(data["pipeline"], "minimal")

    def test_returns_empty_when_nothing_available(self):
        data = plan_parser.task_routing_data({"id": "x"})
        self.assertEqual(data, {})


class TestTaskPlanPath(unittest.TestCase):
    def test_returns_canonical_path(self):
        task = {"id": "r19"}
        with tempfile.TemporaryDirectory() as tmp:
            path = plan_parser.task_plan_path(task, tmp)
            assert path is not None
            self.assertEqual(path, Path(tmp) / "docs" / "plans" / "r19.md")


if __name__ == "__main__":
    unittest.main()
