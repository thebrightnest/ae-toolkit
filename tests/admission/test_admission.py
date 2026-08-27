"""Unit tests for the single admission operation in aet.admission (R-1, R-2, R-4, R-5, R-10, R-11)."""

from __future__ import annotations

import hashlib
import subprocess
import tempfile
import unittest
from pathlib import Path

from aet.admission import (
    Admitted,
    RefusalReason,
    Refused,
    Skipped,
    SkipReason,
    admit_plan,
)
from aet.backends.git_refs_backend import GitRefsBackend
from aet.ledger import Ledger


def _git_init(root: Path) -> None:
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(
        ["git", "-C", str(root), "config", "user.email", "test@example.com"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(root), "config", "user.name", "Test User"],
        check=True,
    )


def _make_prd(prds_dir: Path, name: str, rids: list[str]) -> Path:
    path = prds_dir / name
    lines = [f"# PRD: {path.stem}"]
    if rids:
        lines.append("## Requirements")
        for rid in rids:
            lines.append(f"- **{rid}**: description of {rid}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _make_plan(
    plans_dir: Path,
    name: str,
    *,
    body: str = "",
    footer: str | None = None,
    blocked_by: list[str] | None = None,
) -> Path:
    path = plans_dir / name
    stem = Path(name).stem
    lines = ["---", f"id: {stem}", "size: S"]
    if blocked_by:
        lines.append("blocked_by:")
        for b in blocked_by:
            lines.append(f"  - {b}")
    lines.extend(["---", "", f"# Plan: {name}"])
    if body:
        lines.extend(["", body])
    if footer:
        lines.extend(["", "---", "", footer])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _make_clean_plan(
    plans_dir: Path,
    prds_dir: Path,
    name: str,
    *,
    footer: str | None = None,
    blocked_by: list[str] | None = None,
) -> Path:
    prd_name = "prd.md"
    _make_prd(prds_dir, prd_name, ["R-1"])
    body = (
        "## Context\n"
        f"PRD: docs/prds/{prd_name}\n"
        "\n"
        "## Task List\n"
        "1. Do something (traces: R-1)\n"
        "\n"
        "## Files to Modify\n"
        "- `src/widget.py` (new)\n"
        "\n"
        "## Validation Steps\n"
        "- [ ] test_widget_creation verifies widget.py\n"
    )
    return _make_plan(
        plans_dir,
        name,
        body=body,
        footer=footer,
        blocked_by=blocked_by,
    )


class TestAdmissionOutcomeTypes(unittest.TestCase):
    """Test enumerable outcome types and reasons (R-2)."""

    def test_outcome_types_and_reasons_exist(self):
        self.assertTrue(issubclass(SkipReason, str))
        self.assertIn("already in queue", [r.value for r in SkipReason])
        self.assertIn("already settled", [r.value for r in SkipReason])

        self.assertTrue(issubclass(RefusalReason, str))
        self.assertIn("plan file not found", [r.value for r in RefusalReason])
        self.assertIn("intake validation failed", [r.value for r in RefusalReason])
        self.assertIn("blocked", [r.value for r in RefusalReason])


class TestAdmitPlanOperation(unittest.TestCase):
    """Test the single admission operation admit_plan (R-1, R-4, R-5, R-10)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.plans_dir = self.root / "docs" / "plans"
        self.prds_dir = self.root / "docs" / "prds"
        self.plans_dir.mkdir(parents=True)
        self.prds_dir.mkdir(parents=True)
        _git_init(self.root)
        self.queue_file = self.root / ".agents" / "aet-queue"
        self.history_file = self.root / ".agents" / "work-history.jsonl"
        self.backend = GitRefsBackend(
            queue_file=str(self.queue_file),
            history_file=str(self.history_file),
        )

    def tearDown(self):
        self.backend.close()
        self.tmp.cleanup()

    def test_admit_clean_plan_without_footer(self):
        """A footerless clean plan is admitted (R-4, R-10)."""
        plan = _make_clean_plan(self.plans_dir, self.prds_dir, "clean-no-footer.md", footer=None)
        outcome = admit_plan(
            plan,
            plans_dir=self.plans_dir,
            backend=self.backend,
            history_file=str(self.history_file),
            queue=[],
            history=[],
        )
        self.assertIsInstance(outcome, Admitted)
        self.assertEqual(outcome.plan_file, plan)
        self.assertEqual(outcome.task["id"], "clean-no-footer")
        self.assertEqual(outcome.task["state"], "ready")

    def test_admit_clean_plan_with_footer(self):
        """A clean plan with a footer is also admitted (footer ignored, R-4)."""
        plan = _make_clean_plan(
            self.plans_dir, self.prds_dir, "clean-with-footer.md", footer="*Stage: plan-approved*"
        )
        outcome = admit_plan(
            plan,
            plans_dir=self.plans_dir,
            backend=self.backend,
            history_file=str(self.history_file),
            queue=[],
            history=[],
        )
        self.assertIsInstance(outcome, Admitted)
        self.assertEqual(outcome.task["id"], "clean-with-footer")

    def test_skip_already_in_queue(self):
        """A plan already in the queue is skipped (R-2)."""
        plan = _make_clean_plan(self.plans_dir, self.prds_dir, "live.md")
        queue = [{"id": "live", "state": "ready", "plan_file": str(plan)}]
        outcome = admit_plan(
            "live",
            plans_dir=self.plans_dir,
            backend=self.backend,
            history_file=str(self.history_file),
            queue=queue,
            history=[],
        )
        self.assertIsInstance(outcome, Skipped)
        self.assertEqual(outcome.reason, SkipReason.ALREADY_IN_QUEUE)

    def test_skip_already_settled(self):
        """A plan already settled in history is skipped (R-2)."""
        _make_clean_plan(self.plans_dir, self.prds_dir, "settled.md")
        history = [{"id": "settled", "state": "merged"}]
        outcome = admit_plan(
            "settled",
            plans_dir=self.plans_dir,
            backend=self.backend,
            history_file=str(self.history_file),
            queue=[],
            history=history,
        )
        self.assertIsInstance(outcome, Skipped)
        self.assertEqual(outcome.reason, SkipReason.ALREADY_SETTLED)

    def test_refuse_missing_plan_file(self):
        """A target with no corresponding plan file is refused (R-2)."""
        outcome = admit_plan(
            "nonexistent",
            plans_dir=self.plans_dir,
            backend=self.backend,
            history_file=str(self.history_file),
            queue=[],
            history=[],
        )
        self.assertIsInstance(outcome, Refused)
        self.assertEqual(outcome.reason, RefusalReason.PLAN_NOT_FOUND)

    def test_refuse_validation_failed(self):
        """A plan failing plan_validate is refused with findings (R-5)."""
        bad = self.plans_dir / "bad.md"
        bad.write_text("---\nsize: S\n---\n\n# Bad\n", encoding="utf-8")
        outcome = admit_plan(
            bad,
            plans_dir=self.plans_dir,
            backend=self.backend,
            history_file=str(self.history_file),
            queue=[],
            history=[],
        )
        self.assertIsInstance(outcome, Refused)
        self.assertEqual(outcome.reason, RefusalReason.VALIDATION_FAILED)
        self.assertTrue(outcome.findings)
        self.assertIsNotNone(outcome.coverage)

    def test_refuse_blocked_when_disallowed(self):
        """A blocked plan is refused when allow_blocked=False (for sprint intake)."""
        plan = _make_clean_plan(
            self.plans_dir, self.prds_dir, "feat-002.md", blocked_by=["blocker-001"]
        )
        queue = [{"id": "blocker-001", "state": "ready"}]
        outcome = admit_plan(
            plan,
            plans_dir=self.plans_dir,
            backend=self.backend,
            history_file=str(self.history_file),
            queue=queue,
            history=[],
            allow_blocked=False,
        )
        self.assertIsInstance(outcome, Refused)
        self.assertEqual(outcome.reason, RefusalReason.BLOCKED)
        self.assertEqual(outcome.blockers, ["blocker-001"])

    def test_admit_blocked_when_allowed(self):
        """A blocked plan is admitted when allow_blocked=True (for sprint add)."""
        plan = _make_clean_plan(
            self.plans_dir, self.prds_dir, "feat-002.md", blocked_by=["blocker-001"]
        )
        queue = [{"id": "blocker-001", "state": "ready"}]
        outcome = admit_plan(
            plan,
            plans_dir=self.plans_dir,
            backend=self.backend,
            history_file=str(self.history_file),
            queue=queue,
            history=[],
            allow_blocked=True,
        )
        self.assertIsInstance(outcome, Admitted)
        self.assertEqual(outcome.task["id"], "feat-002")
        self.assertEqual(outcome.task["state"], "blocked")


class TestLedgerSourceDistinctness(unittest.TestCase):
    """Assert sprint-add and sprint-intake write distinct event IDs (Task 5, R-11)."""

    def test_distinct_sources_produce_distinct_event_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger_path = Path(tmp) / ".agents" / "aet-ledger.jsonl"
            ledger = Ledger(ledger_path)
            plan_hash = hashlib.sha256(b"dummy plan content").hexdigest()
            task_id = "test-task"

            event_add = ledger.write_event(
                source="sprint-add",
                task=task_id,
                kind="cut",
                ref=plan_hash,
                ref_kind="plan-hash",
            )
            event_intake = ledger.write_event(
                source="sprint-intake",
                task=task_id,
                kind="cut",
                ref=plan_hash,
                ref_kind="plan-hash",
            )

            self.assertNotEqual(event_add["id"], event_intake["id"])
            self.assertEqual(event_add["source"], "sprint-add")
            self.assertEqual(event_intake["source"], "sprint-intake")


if __name__ == "__main__":
    unittest.main()
