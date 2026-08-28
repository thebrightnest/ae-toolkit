"""A failed group session keeps the stages it proved, and tells the retry the rest.

A session group records its stage once, at the group boundary, and only on a zero
exit. A session that died late therefore lost every stage in the group, and the
retry re-ran completed work — 21 times on 2026-08-27
(`docs/bugs/20260828-group-stage-advance-is-all-or-nothing.md`).

ADR-069 decides what may credit a stage whose session failed: its own passing
verdict, and nothing else. A stage with no evidence binding is never credited,
because its artifact is commits and a commit does not distinguish finished from
interrupted; what is on the branch goes to the run's handoff note instead, which
the retry's prompt already carries.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pytest

from aet import evidence, handoff, telemetry
from aet.cli import orchestrator
from aet.workflow import load_workflow

pytestmark = pytest.mark.xdist_group("git-repo")


def _write_verdict(repo: Path, reports: Path, task_id: str, kind: str, verdict: str) -> None:
    """Write a schema-valid verdict for *kind*, as its stage's skill would."""
    filler = {str: "x", int: 0, float: 0.0, bool: True, list: []}
    record = {name: filler.get(typ, "x") for name, typ in evidence.SCHEMAS[kind].items()}
    record.update(
        {
            "task_id": task_id,
            "stage": "stage",
            "skill": f"aet-{kind}",
            "verdict": verdict,
            "summary": f"{kind} {verdict}",
            "generated_at": "2026-08-28T00:00:00Z",
        }
    )
    record.pop("tree_hash", None)
    evidence.write_verdict(
        task_id=task_id,
        kind=kind,
        record=record,
        project_slug=telemetry.derive_project_slug(str(repo)),
        reports_root=str(reports),
        worktree_dir=str(repo),
    )


class TestStageCreditOnFailure(unittest.TestCase):
    """Only a passing verdict advances the record on the failure path."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.repo = self.root / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        for key, value in (("user.email", "t@example.com"), ("user.name", "T")):
            subprocess.run(["git", "-C", str(self.repo), "config", key, value], check=True)
        (self.repo / "f.txt").write_text("x\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.repo), "add", "."], check=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "-q", "-m", "init"], check=True)
        self.base = subprocess.run(
            ["git", "-C", str(self.repo), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()

        (self.repo / ".agents").mkdir()
        self.reports = self.root / "reports"
        self.workflow = load_workflow(str(self.repo), "software")
        # The group whose loss was measured: plan-approved carries no evidence,
        # implemented is gated on qa.
        self.group = [
            self.workflow.stage_map["plan-approved"],
            self.workflow.stage_map["implemented"],
        ]
        self.task = {
            "id": "t1",
            "state": "in_progress",
            "stage": "plan-approved",
            "base_commit": self.base,
        }

    def tearDown(self):
        self.tmp.cleanup()

    def _commit(self, message: str) -> None:
        (self.repo / f"{message}.txt").write_text("work\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.repo), "add", "."], check=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "-q", "-m", message], check=True)

    def _credit(self, run_id: str | None = "run-1") -> str | None:
        with patch.dict(os.environ, {"AET_REPORTS_DIR": str(self.reports)}):
            return orchestrator._credit_proven_stages(
                self.task,
                self.group,
                self.workflow,
                task_id="t1",
                repo_root=str(self.repo),
                worktree_dir=str(self.repo),
                run_id=run_id,
            )

    def test_a_stage_without_evidence_is_never_credited(self):
        """A commit proves work happened, not that the stage finished."""
        self._commit("implement")

        credited = self._credit()

        self.assertIsNone(credited)
        self.assertEqual(self.task["stage"], "plan-approved")

    def test_the_branch_state_reaches_the_retry(self):
        """What the record must not claim, the handoff note says out loud."""
        self._commit("implement")

        self._credit()

        note = handoff.read_note(str(self.repo), "run-1")
        self.assertIsNotNone(note)
        block = handoff.render_prompt_block(note)
        self.assertIn("already carries 1 commit(s)", block)
        self.assertIn("do not redo that work", block)
        self.assertIn("implement", block)

    def test_a_passing_verdict_credits_its_stage(self):
        """`implemented` is gated on qa; a passing qa verdict advances past it."""
        self._commit("implement")
        _write_verdict(self.repo, self.reports, "t1", "qa", "pass")
        self.task["stage"] = "implemented"
        self.group = [self.workflow.stage_map["implemented"]]

        credited = self._credit()

        self.assertEqual(credited, "qa-complete")
        self.assertEqual(self.task["stage"], "qa-complete")

    def test_a_failing_verdict_credits_nothing(self):
        """A judgment the gate must not paper over does not advance the record."""
        self._commit("implement")
        _write_verdict(self.repo, self.reports, "t1", "qa", "fail")
        self.task["stage"] = "implemented"
        self.group = [self.workflow.stage_map["implemented"]]

        credited = self._credit()

        self.assertIsNone(credited)
        self.assertEqual(self.task["stage"], "implemented")

    def test_crediting_survives_a_missing_run_id(self):
        """The failure path stays a failure even with nowhere to write a note."""
        self._commit("implement")

        self.assertIsNone(self._credit(run_id=None))


if __name__ == "__main__":
    unittest.main()
