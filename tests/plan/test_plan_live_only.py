"""Tests that plan-consuming tooling considers live work only."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from aet import plan_parser, plan_validate, plans_lint


def _make_plan(
    path: Path,
    plan_id: str | None = None,
    footer_stage: str | None = None,
    status: str | None = None,
    blocked_by: list[str] | None = None,
    prd_ref: str | None = None,
    body: str = "",
) -> None:
    stem = plan_id or path.stem
    lines = ["---", f"id: {stem}", "size: S"]
    if status is not None:
        lines.append(f"status: {status}")
    if blocked_by is not None:
        lines.append("blocked_by:")
        for blocker in blocked_by:
            lines.append(f"  - {blocker}")
    lines.extend(
        [
            "---",
            "",
            f"# Plan {stem}",
            "",
            "## Context",
            "",
        ]
    )
    if prd_ref:
        lines.append(f"PRD: {prd_ref}")
    else:
        lines.append("PRD: docs/prds/default-prd.md")
    lines.append("")
    if body:
        lines.extend([body, ""])
    else:
        lines.extend(
            [
                "## Task List",
                "",
                "1. Do something (traces: R-1).",
                "",
            ]
        )
    if footer_stage:
        lines.extend(["---", "", f"*Stage: {footer_stage}*", ""])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _make_prd(path: Path, rids: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# PRD {path.stem}"]
    if rids:
        lines.append("## Requirements")
        for rid in rids:
            lines.append(f"- **{rid}**: description")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class TestSettledPlanDetection(unittest.TestCase):
    """`is_settled_plan` recognises terminal footer stages and statuses."""

    def test_live_plan_is_not_settled(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = Path(tmp) / "live.md"
            _make_plan(plan, footer_stage="plan-approved")
            self.assertFalse(plan_parser.is_settled_plan(plan))

    def test_merged_footer_is_settled(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = Path(tmp) / "merged.md"
            _make_plan(plan, footer_stage="merged")
            self.assertTrue(plan_parser.is_settled_plan(plan))

    def test_abandoned_footer_is_settled(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = Path(tmp) / "abandoned.md"
            _make_plan(plan, footer_stage="abandoned")
            self.assertTrue(plan_parser.is_settled_plan(plan))

    def test_terminal_status_is_settled(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = Path(tmp) / "status-merged.md"
            _make_plan(plan, status="merged")
            self.assertTrue(plan_parser.is_settled_plan(plan))


class TestPlansLintLiveOnly(unittest.TestCase):
    """`aet plans lint` ignores settled plans in the scanned directory."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.plans_dir = Path(self.tmp.name) / "docs" / "plans"
        self.plans_dir.mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_merged_footer_plan_is_excluded(self):
        _make_plan(self.plans_dir / "live.md", footer_stage="plan-approved")
        _make_plan(self.plans_dir / "merged.md", footer_stage="merged")

        violations = plans_lint.lint_corpus(self.plans_dir)
        warnings = plans_lint.lint_floor(self.plans_dir)

        self.assertEqual(violations, [])
        self.assertEqual(warnings, [])

    def test_settled_plan_does_not_trigger_floor_signals(self):
        """A settled child must not flag a live parent as a floor candidate."""
        _make_plan(
            self.plans_dir / "parent.md",
            plan_id="parent",
            footer_stage="plan-approved",
        )
        _make_plan(
            self.plans_dir / "child.md",
            plan_id="child",
            blocked_by=["parent"],
            footer_stage="merged",
            body="## Files to Modify\n- `src/foo.py`\n- `src/bar.py`",
        )

        warnings = plans_lint.lint_floor(self.plans_dir)

        self.assertEqual(warnings, [])


class TestPlanValidateLiveOnly(unittest.TestCase):
    """`aet plan validate` runs checks over live plans only."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.plans_dir = self.root / "docs" / "plans"
        self.prds_dir = self.root / "docs" / "prds"
        self.plans_dir.mkdir(parents=True)
        self.prds_dir.mkdir(parents=True)
        _make_prd(self.prds_dir / "default-prd.md", ["R-1"])

    def tearDown(self):
        self.tmp.cleanup()

    def test_settled_plan_is_skipped(self):
        _make_plan(
            self.plans_dir / "live.md",
            plan_id="live",
            footer_stage="plan-approved",
        )
        _make_plan(
            self.plans_dir / "merged.md",
            plan_id="merged",
            footer_stage="merged",
            # Intentionally broken: missing required R-1 coverage.
            body="## Task List\n1. Do nothing (traces: R-99).",
        )

        findings = plan_validate.validate(
            [self.plans_dir / "live.md", self.plans_dir / "merged.md"],
            repo_root=self.root,
        )
        unacked = [f for f in findings if not f.acked]

        self.assertEqual(unacked, [])

    def test_rtrace_coverage_uses_live_plans_only(self):
        """A requirement traced only by a settled plan is uncovered for live work."""
        _make_prd(self.prds_dir / "coverage-prd.md", ["R-4", "R-5"])
        _make_plan(
            self.plans_dir / "live.md",
            plan_id="live",
            prd_ref="docs/prds/coverage-prd.md",
            footer_stage="plan-approved",
            body="## Task List\n1. Live task (traces: R-4)",
        )
        _make_plan(
            self.plans_dir / "settled.md",
            plan_id="settled",
            prd_ref="docs/prds/coverage-prd.md",
            footer_stage="merged",
            body="## Task List\n1. Settled task (traces: R-5)",
        )

        findings = plan_validate.validate(
            [self.plans_dir / "live.md"], repo_root=self.root
        )
        rtrace = [f for f in findings if f.check_id == "rtrace"]

        self.assertEqual(len(rtrace), 1)
        self.assertIn("R-5 has no covering task", rtrace[0].message)


class TestToolingStability(unittest.TestCase):
    """Plan tooling output is unchanged by settled plans accumulating."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.plans_dir = self.root / "docs" / "plans"
        self.prds_dir = self.root / "docs" / "prds"
        self.plans_dir.mkdir(parents=True)
        self.prds_dir.mkdir(parents=True)
        _make_prd(self.prds_dir / "default-prd.md", ["R-1"])

    def tearDown(self):
        self.tmp.cleanup()

    def _live_plan(self, name: str) -> Path:
        path = self.plans_dir / f"{name}.md"
        _make_plan(path, plan_id=name, footer_stage="plan-approved")
        return path

    def _settled_plan(self, name: str) -> Path:
        path = self.plans_dir / f"{name}.md"
        _make_plan(path, plan_id=name, footer_stage="merged")
        return path

    def test_lint_and_validate_output_unchanged_after_closures(self):
        """Fifty settled plans do not change lint/validate output or counts."""
        live_paths = [self._live_plan(f"live-{i:02d}") for i in range(5)]
        for i in range(50):
            self._settled_plan(f"settled-{i:02d}")

        violations = plans_lint.lint_corpus(self.plans_dir)
        warnings = plans_lint.lint_floor(self.plans_dir)
        findings = plan_validate.validate(live_paths, repo_root=self.root)
        unacked = [f for f in findings if not f.acked]

        self.assertEqual(violations, [])
        self.assertEqual(warnings, [])
        self.assertEqual(unacked, [])


if __name__ == "__main__":
    unittest.main()
