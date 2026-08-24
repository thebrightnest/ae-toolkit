"""`run-one` applies the intake validation `sprint add` enforces.

`sprint add` refuses a plan that fails intake. `run-one` did not, and it is the
other door onto the board: a plan the gate refused ran through it unchanged, so
intake quality was advisory while presenting as mandatory, and nothing recorded
which of the two doors a task came through.
"""

from __future__ import annotations

import argparse
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from aet.backends.git_refs_backend import GitRefsBackend
from aet.cli import orchestrator


def _git_init(root: Path) -> None:
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    for key, value in (("user.email", "t@example.com"), ("user.name", "T")):
        subprocess.run(["git", "-C", str(root), "config", key, value], check=True)


def _clean_plan(plans_dir: Path, prds_dir: Path, name: str) -> Path:
    (prds_dir / "alpha-prd.md").write_text(
        "# Alpha\n## Requirements\n- **R-1**: one\n", encoding="utf-8"
    )
    plan = plans_dir / name
    plan.write_text(
        "---\nid: "
        + Path(name).stem
        + "\nsize: S\nsecurity_review: skipped\n"
        "security_review_reason: no attack surface\n---\n\n"
        f"# Plan {Path(name).stem}\n\n## Context\n\nPRD: docs/prds/alpha-prd.md\n\n"
        "## Task List\n\n1. Deliver it (traces: R-1).\n\n"
        "## Validation Strategy\n\nRun the suite.\n\n"
        "## Acceptance Criteria\n\n- [ ] It works\n\n---\n\n*Stage: plan-approved*\n",
        encoding="utf-8",
    )
    return plan


def _broken_plan(plans_dir: Path, name: str) -> Path:
    """A plan with no frontmatter id — a structural intake failure."""
    plan = plans_dir / name
    plan.write_text(
        "---\nsize: S\n---\n\n# Broken\n\n---\n\n*Stage: plan-approved*\n",
        encoding="utf-8",
    )
    return plan


def _stub_state_calls():
    """Answer the `aet_state.py transition` call, delegate everything else.

    The backend runs git through the same module attribute, so a blanket mock
    breaks the store this test reads back.
    """
    real = subprocess.run

    def _run(cmd, *args, **kwargs):
        if any("aet_state.py" in str(part) for part in cmd):
            return subprocess.CompletedProcess(cmd, 0, "", "")
        return real(cmd, *args, **kwargs)

    return _run


class _Fixture:
    def __init__(self, tmp: str) -> None:
        self.root = Path(tmp).resolve()
        self.plans = self.root / "docs" / "plans"
        self.prds = self.root / "docs" / "prds"
        self.plans.mkdir(parents=True)
        self.prds.mkdir(parents=True)
        _git_init(self.root)
        queue = self.root / ".agents" / "aet-queue"
        queue.parent.mkdir(parents=True, exist_ok=True)
        GitRefsBackend(
            queue_file=str(queue),
            history_file=str(self.root / ".agents" / "work-history.jsonl"),
        ).save([])

    def backend(self) -> GitRefsBackend:
        return GitRefsBackend(
            queue_file=str(self.root / ".agents" / "aet-queue"),
            history_file=str(self.root / ".agents" / "work-history.jsonl"),
        )


class TestIntakeFindings(unittest.TestCase):
    """The same suite, the same corpus, the same acks."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.fix = _Fixture(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_a_clean_plan_yields_no_findings(self):
        plan = _clean_plan(self.fix.plans, self.fix.prds, "good.md")
        backend = self.fix.backend()
        try:
            found = orchestrator._intake_findings(
                str(plan), str(self.fix.root), backend
            )
        finally:
            backend.close()

        self.assertEqual(found, [])

    def test_a_structurally_broken_plan_yields_findings(self):
        plan = _broken_plan(self.fix.plans, "bad.md")
        backend = self.fix.backend()
        try:
            found = orchestrator._intake_findings(
                str(plan), str(self.fix.root), backend
            )
        finally:
            backend.close()

        self.assertTrue(found)
        self.assertTrue(all(f.plan == plan for f in found))

    def test_an_acked_finding_is_not_a_refusal(self):
        """The escape hatch `sprint add` honours is honoured here too."""
        plan = _broken_plan(self.fix.plans, "bad.md")
        plan.write_text(
            plan.read_text(encoding="utf-8")
            + "\n⚠️ VALIDATE ACK: structural — deliberate for this test\n"
            + "⚠️ VALIDATE ACK: rtrace — no PRD in this fixture\n",
            encoding="utf-8",
        )
        backend = self.fix.backend()
        try:
            found = orchestrator._intake_findings(
                str(plan), str(self.fix.root), backend
            )
        finally:
            backend.close()

        self.assertEqual(found, [])

    def test_findings_for_sibling_plans_are_not_this_plan_s_problem(self):
        _broken_plan(self.fix.plans, "someone-else.md")
        plan = _clean_plan(self.fix.plans, self.fix.prds, "good.md")
        backend = self.fix.backend()
        try:
            found = orchestrator._intake_findings(
                str(plan), str(self.fix.root), backend
            )
        finally:
            backend.close()

        self.assertEqual(found, [])

    def test_a_missing_plans_directory_does_not_become_a_refusal(self):
        plan = self.fix.root / "loose.md"
        plan.write_text("---\nid: loose\nsize: S\n---\n\n# Loose\n", encoding="utf-8")
        backend = self.fix.backend()
        try:
            found = orchestrator._intake_findings(
                str(plan), str(self.fix.root), backend
            )
        finally:
            backend.close()

        self.assertTrue(all(f.plan == plan for f in found))


class TestRunSingleRefuses(unittest.TestCase):
    """The gate is on the run path, not only in the helper."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.fix = _Fixture(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _args(self, plan: Path, **overrides) -> argparse.Namespace:
        args = argparse.Namespace(
            repo_root=str(self.fix.root),
            plan_file=str(plan),
            run_id="test-run",
            base=None,
            skip_intake=False,
            isolation="standard",
            force=False,
        )
        for key, value in overrides.items():
            setattr(args, key, value)
        return args

    def _run(self, plan: Path, **overrides):
        with patch.dict("os.environ", {"AET_REPO_ROOT": str(self.fix.root)}, clear=False):
            with patch.object(orchestrator.os.environ, "get", wraps=orchestrator.os.environ.get):
                return orchestrator.run_single(self._args(plan, **overrides), adapter=None)

    def test_a_failing_plan_is_refused_before_any_work(self):
        plan = _broken_plan(self.fix.plans, "bad.md")

        with patch.object(orchestrator, "load_workflow") as workflow:
            rc = self._run(plan)

        self.assertEqual(rc, 1)
        workflow.assert_not_called()

    def test_the_refusal_names_the_ack_syntax_and_the_bypass(self):
        plan = _broken_plan(self.fix.plans, "bad.md")

        with patch.object(orchestrator, "load_workflow"):
            with patch("builtins.print") as printed:
                self._run(plan)

        output = "\n".join(str(call.args[0]) for call in printed.call_args_list if call.args)
        self.assertIn("VALIDATE ACK: <check-id>", output)
        self.assertIn("--skip-intake", output)

    def test_skip_intake_lets_the_run_proceed(self):
        plan = _broken_plan(self.fix.plans, "bad.md")

        with patch.object(orchestrator, "load_workflow") as workflow:
            workflow.side_effect = orchestrator.WorkflowError("stop here")
            rc = self._run(plan, skip_intake=True)

        # Reaching the workflow load is the point: the gate did not refuse.
        self.assertEqual(rc, 1)
        workflow.assert_called_once()

    def test_skip_intake_says_what_it_bypassed(self):
        plan = _broken_plan(self.fix.plans, "bad.md")

        with patch.object(orchestrator, "load_workflow") as workflow:
            workflow.side_effect = orchestrator.WorkflowError("stop here")
            with patch("builtins.print") as printed:
                self._run(plan, skip_intake=True)

        output = "\n".join(str(call.args[0]) for call in printed.call_args_list if call.args)
        self.assertIn("intake validation skipped", output)

    def test_a_batch_child_is_not_re_judged(self):
        """Its task passed intake on the way in; re-judging would fail mid-flight."""
        plan = _broken_plan(self.fix.plans, "bad.md")

        with patch.dict("os.environ", {"AET_TASK_ID": "bad"}, clear=False):
            with patch.object(orchestrator, "load_workflow") as workflow:
                workflow.side_effect = orchestrator.WorkflowError("stop here")
                rc = orchestrator.run_single(self._args(plan), adapter=None)

        self.assertEqual(rc, 1)
        workflow.assert_called_once()


class TestRecordedBypass(unittest.TestCase):
    """A bypass that leaves no trace is the audit-trail half of the defect."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.fix = _Fixture(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_the_bypassed_check_ids_land_on_the_task_record(self):
        queue_file = self.fix.root / ".agents" / "aet-queue"
        backend = self.fix.backend()
        backend.save([{"id": "t1", "state": "planned", "plan_file": "docs/plans/t1.md"}])

        with patch.object(orchestrator, "resolve_base_commit", return_value="abc"):
            with patch.object(orchestrator, "record_task_meta"):
                with patch.object(orchestrator.subprocess, "run", _stub_state_calls()):
                    orchestrator._record_run_one_in_queue(
                        backend,
                        str(queue_file),
                        "t1",
                        ".worktrees/t1",
                        "t1",
                        str(self.fix.root),
                        intake_skipped=["structural", "structural"],
                    )

        recorded = self.fix.backend().load()["queue"][0]
        self.assertEqual(recorded["intake_skipped"], ["structural"])

    def test_a_validated_task_carries_no_bypass_field(self):
        """Its presence must mean exactly one thing."""
        queue_file = self.fix.root / ".agents" / "aet-queue"
        backend = self.fix.backend()
        backend.save([{"id": "t1", "state": "planned", "plan_file": "docs/plans/t1.md"}])

        with patch.object(orchestrator, "resolve_base_commit", return_value="abc"):
            with patch.object(orchestrator, "record_task_meta"):
                with patch.object(orchestrator.subprocess, "run", _stub_state_calls()):
                    orchestrator._record_run_one_in_queue(
                        backend,
                        str(queue_file),
                        "t1",
                        ".worktrees/t1",
                        "t1",
                        str(self.fix.root),
                        intake_skipped=[],
                    )

        self.assertNotIn("intake_skipped", self.fix.backend().load()["queue"][0])


if __name__ == "__main__":
    unittest.main()
