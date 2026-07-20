"""Tests for the ``aet plan validate`` check suite."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
from aet import plan_validate  # noqa: E402


def make_plan(
    path: Path,
    plan_id: str | None = None,
    size: str = "M",
    blocked_by: list[str] | None = None,
    prd_ref: str | None = None,
    body: str = "",
) -> None:
    """Write a minimal plan file using the frontmatter contract."""
    stem = plan_id or path.stem
    lines = ["---", f"id: {stem}", f"size: {size}"]
    if blocked_by:
        lines.append("blocked_by:")
        for blocker in blocked_by:
            lines.append(f"  - {blocker}")
    lines.extend(["---", "", f"# Plan {stem}"])
    if prd_ref:
        lines.extend(["", "## Context", f"PRD: {prd_ref}"])
    if body:
        lines.extend(["", body])
    lines.extend(["", "---", "", "*Stage: plan-approved*"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def make_prd(path: Path, rids: list[str] | None = None) -> None:
    """Write a PRD with a Requirements section containing the given R-ids."""
    lines = [f"# PRD {path.stem}"]
    if rids:
        lines.append("## Requirements")
        for rid in rids:
            lines.append(f"- **{rid}**: description of {rid}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class TestStructuralValidation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.plans_dir = self.root / "plans"
        self.plans_dir.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_structural_delegates_to_intake_validation(self):
        """A plan missing its id is reported as a structural finding."""
        bad = self.plans_dir / "bad.md"
        bad.write_text("---\nsize: M\n---\n\n# Bad\n", encoding="utf-8")

        findings = plan_validate.validate([bad], repo_root=self.root)

        structural = [f for f in findings if f.check_id == "structural"]
        self.assertEqual(len(structural), 1)
        self.assertIn("missing id", structural[0].message)


class TestRtraceValidation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.plans_dir = self.root / "docs" / "plans"
        self.prds_dir = self.root / "docs" / "prds"
        self.plans_dir.mkdir(parents=True)
        self.prds_dir.mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_rtrace_missing_covering_task_fails(self):
        """An in-scope R-id with no covering task is a failure."""
        prd = self.prds_dir / "prd.md"
        make_prd(prd, rids=["R-4", "R-5"])
        plan = self.plans_dir / "plan.md"
        make_plan(
            plan,
            prd_ref="docs/prds/prd.md",
            body="## Task List\n1. Task one (traces: R-4)\n",
        )

        findings = plan_validate.validate([plan], repo_root=self.root)

        rtrace = [f for f in findings if f.check_id == "rtrace"]
        self.assertEqual(len(rtrace), 1)
        self.assertIn("R-5 has no covering task", rtrace[0].message)

    def test_rtrace_task_cites_unknown_rid_fails(self):
        """A task citing an R-id outside the PRD scope is a failure."""
        prd = self.prds_dir / "prd.md"
        make_prd(prd, rids=["R-4"])
        plan = self.plans_dir / "plan.md"
        make_plan(
            plan,
            prd_ref="docs/prds/prd.md",
            body="## Task List\n1. Task one (traces: R-4, R-99)\n",
        )

        findings = plan_validate.validate([plan], repo_root=self.root)

        rtrace = [f for f in findings if f.check_id == "rtrace"]
        self.assertEqual(len(rtrace), 1)
        self.assertIn("R-99", rtrace[0].message)

    def test_rtrace_coverage_credited_across_plan_set(self):
        """A requirement covered by a sibling plan is not flagged as uncovered.

        One PRD decomposes into many atomic plans, so coverage is a whole-set
        property: each plan need only trace its own slice.
        """
        prd = self.prds_dir / "prd.md"
        make_prd(prd, rids=["R-4", "R-5"])
        plan_a = self.plans_dir / "plan-a.md"
        plan_b = self.plans_dir / "plan-b.md"
        make_plan(
            plan_a,
            prd_ref="docs/prds/prd.md",
            body="## Task List\n1. Task one (traces: R-4)\n",
        )
        make_plan(
            plan_b,
            prd_ref="docs/prds/prd.md",
            body="## Task List\n1. Task two (traces: R-5)\n",
        )

        findings = plan_validate.validate([plan_a, plan_b], repo_root=self.root)

        rtrace = [f for f in findings if f.check_id == "rtrace"]
        self.assertEqual(rtrace, [], [f.message for f in rtrace])


class TestAcceptanceValidation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.plans_dir = self.root / "plans"
        self.plans_dir.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_acceptance_restating_task_fails(self):
        """An acceptance criterion that restates a task is a failure."""
        plan = self.plans_dir / "plan.md"
        body = (
            "## Task List\n"
            "1. Build the widget (traces: R-4)\n"
            "\n"
            "## Validation Steps\n"
            "- [ ] Build the widget\n"
        )
        make_plan(plan, body=body)

        findings = plan_validate.validate([plan], repo_root=self.root)

        acceptance = [f for f in findings if f.check_id == "acceptance"]
        self.assertEqual(len(acceptance), 1)
        self.assertIn("restates task", acceptance[0].message)

    def test_new_source_file_without_named_test_fails(self):
        """A new source file with no named test in validation strategy fails."""
        plan = self.plans_dir / "plan.md"
        body = (
            "## Files to Modify\n"
            "- `src/widget.py` (new)\n"
            "\n"
            "## Validation Steps\n"
            "- [ ] Run the full suite\n"
        )
        make_plan(plan, body=body)

        findings = plan_validate.validate([plan], repo_root=self.root)

        acceptance = [f for f in findings if f.check_id == "acceptance"]
        self.assertEqual(len(acceptance), 1)
        self.assertIn("widget.py", acceptance[0].message)

    def test_doc_deliverable_needs_no_named_test(self):
        """A new documentation deliverable (docs/*.md) is not testable source."""
        plan = self.plans_dir / "plan.md"
        body = (
            "## Files to Modify\n"
            "- `docs/audits/rehearsal-writeup.md` (new)\n"
            "\n"
            "## Validation Steps\n"
            "- [ ] Run the full suite\n"
        )
        make_plan(plan, body=body)

        findings = plan_validate.validate([plan], repo_root=self.root)

        acceptance = [f for f in findings if f.check_id == "acceptance"]
        self.assertEqual(acceptance, [], [f.message for f in acceptance])

    def test_feature_named_test_credits_new_source(self):
        """A new source file is covered when the strategy names a test file,
        even if the test is named for the behavior, not the source file."""
        plan = self.plans_dir / "plan.md"
        body = (
            "## Files to Modify\n"
            "- `src/track_record.py` (new)\n"
            "\n"
            "## Validation Steps\n"
            "- [ ] New source coverage — `tests/test_zero_review.py`:\n"
            "  - `test_clean_merge_counts_all_pass`\n"
        )
        make_plan(plan, body=body)

        findings = plan_validate.validate([plan], repo_root=self.root)

        acceptance = [f for f in findings if f.check_id == "acceptance"]
        self.assertEqual(acceptance, [], [f.message for f in acceptance])

    def test_new_directory_needs_no_named_test(self):
        """A new directory deliverable (trailing slash) is not a source file."""
        plan = self.plans_dir / "plan.md"
        body = (
            "## Files to Modify\n"
            "- `tests/fixtures/scenario/` (new)\n"
            "\n"
            "## Validation Steps\n"
            "- [ ] Run the full suite\n"
        )
        make_plan(plan, body=body)

        findings = plan_validate.validate([plan], repo_root=self.root)

        acceptance = [f for f in findings if f.check_id == "acceptance"]
        self.assertEqual(acceptance, [], [f.message for f in acceptance])


class TestScopeValidation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.plans_dir = self.root / "plans"
        self.adr_dir = self.root / "docs" / "adr"
        self.plans_dir.mkdir()
        self.adr_dir.mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_unresolved_adr_reference_fails(self):
        """A reference to a missing ADR file is a scope failure."""
        (self.adr_dir / "001-existing.md").write_text("# ADR-001\n", encoding="utf-8")
        plan = self.plans_dir / "plan.md"
        make_plan(
            plan,
            body="See [missing](docs/adr/999-missing.md) for context.\n",
        )

        findings = plan_validate.validate([plan], repo_root=self.root)

        scope = [f for f in findings if f.check_id == "scope"]
        self.assertEqual(len(scope), 1)
        self.assertIn("ADR reference does not resolve", scope[0].message)


class TestAckEscapeHatch(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.plans_dir = self.root / "docs" / "plans"
        self.prds_dir = self.root / "docs" / "prds"
        self.adr_dir = self.root / "docs" / "adr"
        self.plans_dir.mkdir(parents=True)
        self.prds_dir.mkdir(parents=True)
        self.adr_dir.mkdir(parents=True)
        make_prd(self.prds_dir / "prd.md", rids=["R-4"])

    def tearDown(self):
        self.tmp.cleanup()

    def _validate_with_acks(self, plan: Path) -> list[plan_validate.Finding]:
        findings = plan_validate.validate([plan], repo_root=self.root)
        text = plan.read_text(encoding="utf-8")
        return plan_validate.apply_acks(findings, {plan: text})

    def test_ack_with_reason_overrides_that_check(self):
        """A correctly formed ack marker suppresses its named check."""
        plan = self.plans_dir / "plan.md"
        make_plan(
            plan,
            prd_ref="docs/prds/prd.md",
            body=(
                "## Task List\n"
                "1. Task one (traces: R-4)\n\n"
                "See [missing](docs/adr/999-missing.md).\n\n"
                "⚠️ VALIDATE ACK: scope — intentional deferral\n"
            ),
        )

        findings = self._validate_with_acks(plan)
        unacked = [f for f in findings if not f.acked]
        self.assertEqual(len(unacked), 0)

    def test_ack_without_reason_does_not_override(self):
        """An ack marker without a reason is ignored and the failure stands."""
        plan = self.plans_dir / "plan.md"
        make_plan(
            plan,
            prd_ref="docs/prds/prd.md",
            body=(
                "## Task List\n"
                "1. Task one (traces: R-4)\n\n"
                "See [missing](docs/adr/999-missing.md).\n\n"
                "⚠️ VALIDATE ACK: scope —\n"
            ),
        )

        findings = self._validate_with_acks(plan)
        unacked = [f for f in findings if not f.acked]
        scope = [f for f in unacked if f.check_id == "scope"]
        self.assertEqual(len(scope), 1)


class TestCleanPlan(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.plans_dir = self.root / "docs" / "plans"
        self.prds_dir = self.root / "docs" / "prds"
        self.adr_dir = self.root / "docs" / "adr"
        self.plans_dir.mkdir(parents=True)
        self.prds_dir.mkdir(parents=True)
        self.adr_dir.mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_clean_plan_passes(self):
        """A well-formed plan with full coverage produces no findings."""
        prd = self.prds_dir / "prd.md"
        make_prd(prd, rids=["R-4"])
        (self.adr_dir / "001-context.md").write_text("# ADR\n", encoding="utf-8")
        plan = self.plans_dir / "plan.md"
        body = (
            "## Task List\n"
            "1. Implement feature (traces: R-4)\n"
            "\n"
            "## Files to Modify\n"
            "- `src/widget.py` (new)\n"
            "\n"
            "## Validation Steps\n"
            "- [ ] test_widget_creation verifies widget.py\n"
            "\n"
            "See [context](docs/adr/001-context.md).\n"
        )
        make_plan(plan, prd_ref="docs/prds/prd.md", body=body)

        findings = plan_validate.validate([plan], repo_root=self.root)
        unacked = [f for f in findings if not f.acked]
        self.assertEqual(len(unacked), 0, [f.message for f in unacked])


class TestPlanValidateRouting(unittest.TestCase):
    """``aet plan validate`` reaches the new binary through the dispatcher."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.bin_dir = self.root / "bin"
        self.bin_dir.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def _run_aet(self, cwd: Path, *args: str) -> subprocess.CompletedProcess:
        env = {**os.environ, "AET_BIN_DIR": str(self.bin_dir)}
        cmd = [sys.executable, str(REPO_ROOT / "aet-work" / "bin" / "aet"), *args]
        return subprocess.run(
            cmd,
            cwd=str(cwd),
            env=env,
            capture_output=True,
            text=True,
        )

    def test_plan_validate_routed_through_aet_dispatcher(self):
        """``aet plan validate <plan>`` runs the check suite and exits 0."""
        repo = self.root / "repo"
        plans_dir = repo / "docs" / "plans"
        prds_dir = repo / "docs" / "prds"
        plans_dir.mkdir(parents=True)
        prds_dir.mkdir(parents=True)
        subprocess.run(
            ["git", "init", "-q"],
            cwd=str(repo),
            check=True,
        )

        make_prd(prds_dir / "prd.md", rids=["R-4"])
        body = (
            "## Task List\n"
            "1. Implement feature (traces: R-4)\n"
        )
        make_plan(
            plans_dir / "clean.md",
            plan_id="clean",
            prd_ref="docs/prds/prd.md",
            body=body,
        )

        result = self._run_aet(repo, "plan", "validate", "docs/plans/clean.md")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("all plans passed validation", result.stdout)


if __name__ == "__main__":
    unittest.main()
