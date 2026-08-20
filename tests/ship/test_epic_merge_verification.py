"""Tests for epic-level merge verification in aet ship close (R-21).

In single-pr mode the epic integration branch is the unit that reaches trunk.
`aet ship close` must verify the integration branch's merge into trunk once,
retaining ADR-029's fail-closed property:
- no closure without verified merge evidence;
- no self-merge (closing a branch against itself).
"""

from __future__ import annotations

import argparse
import importlib.machinery
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_SHIP_PY = Path(__file__).parents[2] / "src" / "aet" / "cli" / "ship.py"
_spec = importlib.util.spec_from_loader(
    "aet_ship_epic", importlib.machinery.SourceFileLoader("aet_ship_epic", str(_SHIP_PY))
)
ship = importlib.util.module_from_spec(_spec)
sys.modules["aet_ship_epic"] = ship
_spec.loader.exec_module(ship)


class TestEpicMergeVerification(unittest.TestCase):
    """Behavior-driven tests for epic-level closure."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        base = Path(self.tmpdir.name)

        self.queue_path = base / ".agents" / "aet-queue"
        self.queue_path.parent.mkdir(parents=True)
        self.history_file = self.queue_path.with_name("work-history.jsonl")

        self.plan_path = base / "docs" / "plans" / "epic-01.md"
        self.plan_path.parent.mkdir(parents=True)
        self.plan_path.write_text(
            "---\n"
            "id: epic-01\n"
            "status: awaiting_merge\n"
            "---\n\n"
            "# Epic 01\n\n"
            "---\n\n"
            "*Stage: synced*\n",
            encoding="utf-8",
        )

        queue = {
            "tasks": [
                {
                    "id": "epic-01",
                    "status": "awaiting_merge",
                    "branch": "epic-01",
                    "plan_file": str(self.plan_path),
                }
            ]
        }
        self.queue_path.write_text(json.dumps(queue), encoding="utf-8")

        self.cwd = os.getcwd()
        self.addCleanup(os.chdir, self.cwd)

    def test_close_accepts_target_branch_override(self):
        """aet ship close --target-branch passes the override to record-merge."""
        with patch.object(
            ship.aet_state,
            "cmd_record_merge",
            return_value=0,
        ) as record_mock:
            rc = ship.cmd_ship(
                argparse.Namespace(
                    task_id="epic-01",
                    plan=str(self.plan_path),
                    queue=str(self.queue_path),
                    branch=None,
                    merge_commit=None,
                    target_branch="main",
                    dry_run=False,
                )
            )
        self.assertEqual(rc, 0)
        record_mock.assert_called_once()
        ns = record_mock.call_args[0][0]
        self.assertEqual(ns.target_branch, "main")

    def test_close_refuses_self_merge(self):
        """R-21: closing a branch against itself is a self-merge and is refused."""
        with patch.object(
            ship.aet_state,
            "cmd_record_merge",
            return_value=0,
        ) as record_mock:
            rc = ship.cmd_ship(
                argparse.Namespace(
                    task_id="epic-01",
                    plan=str(self.plan_path),
                    queue=str(self.queue_path),
                    branch="epic-01",
                    merge_commit=None,
                    target_branch="epic-01",
                    dry_run=False,
                )
            )
        self.assertNotEqual(rc, 0)
        record_mock.assert_not_called()

    def test_close_refuses_missing_merge_evidence(self):
        """R-21: record-merge failure (no merge evidence) propagates as failure."""
        with patch.object(
            ship.aet_state,
            "cmd_record_merge",
            return_value=1,
        ) as record_mock:
            rc = ship.cmd_ship(
                argparse.Namespace(
                    task_id="epic-01",
                    plan=str(self.plan_path),
                    queue=str(self.queue_path),
                    branch="epic-01",
                    merge_commit=None,
                    target_branch="main",
                    dry_run=False,
                )
            )
        self.assertNotEqual(rc, 0)
        record_mock.assert_called_once()
        ns = record_mock.call_args[0][0]
        self.assertEqual(ns.target_branch, "main")

    def test_close_happy_path_records_epic_merge(self):
        """R-21: verified epic merge into trunk records closure."""
        with patch.object(
            ship.aet_state,
            "cmd_record_merge",
            return_value=0,
        ) as record_mock:
            rc = ship.cmd_ship(
                argparse.Namespace(
                    task_id="epic-01",
                    plan=str(self.plan_path),
                    queue=str(self.queue_path),
                    branch="epic-01",
                    merge_commit="merge-sha-1",
                    target_branch="main",
                    dry_run=False,
                )
            )
        self.assertEqual(rc, 0)
        record_mock.assert_called_once()
        ns = record_mock.call_args[0][0]
        self.assertEqual(ns.target_branch, "main")
        self.assertEqual(ns.merge_commit, "merge-sha-1")


if __name__ == "__main__":
    unittest.main()
