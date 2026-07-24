"""Tests for the aet-ship direct merge command (`aet ship merge`)."""

from __future__ import annotations

import argparse
import importlib.machinery
import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_SHIP_PY = Path(__file__).parents[1] / "src" / "aet" / "cli" / "ship.py"
_spec = importlib.util.spec_from_loader(
    "aet_ship_merge", importlib.machinery.SourceFileLoader("aet_ship_merge", str(_SHIP_PY))
)
ship = importlib.util.module_from_spec(_spec)
sys.modules["aet_ship_merge"] = ship
_spec.loader.exec_module(ship)


class MockResult:
    def __init__(self, returncode, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class TestShipMergeParser(unittest.TestCase):
    """Argument parsing for the merge subcommand."""

    def test_merge_subcommand_requires_branch(self):
        """aet ship merge requires --branch to be explicit."""
        parser = ship.build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(["merge", "docs/plans/t1.md"])

    def test_merge_subcommand_parses_branch(self):
        """aet ship merge accepts a plan and a required --branch."""
        parser = ship.build_parser()
        args = parser.parse_args(["merge", "docs/plans/t1.md", "--branch", "dev"])
        self.assertEqual(args.command, "merge")
        self.assertEqual(args.plan, "docs/plans/t1.md")
        self.assertEqual(args.branch, "dev")


class TestShipMergeConflictDetection(unittest.TestCase):
    """Conflict detection before direct merge."""

    def test_has_merge_conflicts_detects_conflict_markers(self):
        """_has_merge_conflicts returns True when merge-tree emits conflict markers."""
        responses = {
            ("git", "merge-base", "HEAD", "origin/dev"): (0, "base-sha\n", ""),
            ("git", "merge-tree", "base-sha", "HEAD", "origin/dev"): (
                0,
                "<<<<<<< HEAD\nours\n=======\ntheirs\n>>>>>>> origin/dev\n",
                "",
            ),
        }
        with patch.object(ship.subprocess, "run", side_effect=self._mock_run(responses)):
            has_conflicts, msg = ship._has_merge_conflicts("dev")
        self.assertTrue(has_conflicts)
        self.assertIn("conflicts", msg.lower())

    def test_has_merge_conflicts_returns_false_when_clean(self):
        """_has_merge_conflicts returns False when merge-tree has no conflict markers."""
        responses = {
            ("git", "merge-base", "HEAD", "origin/dev"): (0, "base-sha\n", ""),
            ("git", "merge-tree", "base-sha", "HEAD", "origin/dev"): (
                0,
                "merged content\n",
                "",
            ),
        }
        with patch.object(ship.subprocess, "run", side_effect=self._mock_run(responses)):
            has_conflicts, msg = ship._has_merge_conflicts("dev")
        self.assertFalse(has_conflicts)
        self.assertEqual(msg, "")

    @staticmethod
    def _mock_run(responses):
        def mock_run(cmd, **kwargs):
            args = tuple(cmd)
            if args in responses:
                rc, out, err = responses[args]
                return MockResult(rc, out, err)
            return MockResult(1, "", f"unexpected: {cmd!r}")

        return mock_run


class TestShipMergeCommand(unittest.TestCase):
    """Behavior-driven tests for `cmd_merge`."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        base = Path(self.tmpdir.name)

        self.plan_path = base / "docs" / "plans" / "t1.md"
        self.plan_path.parent.mkdir(parents=True)
        self._write_plan(
            "---\n"
            "id: t1\n"
            "status: awaiting_merge\n"
            "---\n\n"
            "# Plan T1\n\n"
            "## Task List\n\n"
            "- [x] task one\n\n"
            "---\n\n"
            "*Stage: implemented*\n",
        )

        self.cwd = os.getcwd()
        self.addCleanup(os.chdir, self.cwd)

    def _write_plan(self, content: str) -> None:
        self.plan_path.write_text(content, encoding="utf-8")

    def test_merge_requires_branch_option(self):
        """Typer/argparse rejects merge when --branch is missing."""
        with self.assertRaises(SystemExit):
            ship.parse_args(["merge", str(self.plan_path)])

    def test_merge_refuses_to_proceed_when_gate_fails(self):
        """If the gate reports failure, merge exits before conflict/merge checks."""
        gate_result = ship.GateResult(
            ok=False,
            pr_base="origin/dev",
            rebased=False,
            scope_audit=[],
            dry_run=False,
            message="Working tree is dirty.",
        )
        with patch.object(ship, "_run_gate", return_value=gate_result):
            rc = ship.cmd_merge(
                argparse.Namespace(plan=str(self.plan_path), branch="dev", dry_run=False)
            )
        self.assertNotEqual(rc, 0)

    def test_merge_stops_on_conflict_detection(self):
        """Detected conflicts stop the merge before touching the target branch."""
        gate_result = ship.GateResult(
            ok=True,
            pr_base="origin/dev",
            rebased=False,
            scope_audit=[],
            dry_run=False,
            message="Gate passed.",
        )
        with patch.object(ship, "_run_gate", return_value=gate_result):
            with patch.object(ship, "_check_release_guard", return_value=None):
                with patch.object(ship, "_is_monolithic_commit", return_value=False):
                    with patch.object(
                        ship, "_has_merge_conflicts", return_value=(True, "conflict!")
                    ):
                        with patch.object(
                            ship, "_merge_into_target", return_value=(True, "", "sha")
                        ) as merge_mock:
                            rc = ship.cmd_merge(
                                argparse.Namespace(
                                    plan=str(self.plan_path), branch="dev", dry_run=False
                                )
                            )
        self.assertNotEqual(rc, 0)
        merge_mock.assert_not_called()

    def test_merge_happy_path_records_closure(self):
        """A clean gate + no conflicts triggers merge and records closure."""
        gate_result = ship.GateResult(
            ok=True,
            pr_base="origin/dev",
            rebased=False,
            scope_audit=[],
            dry_run=False,
            message="Gate passed.",
        )
        with patch.object(ship, "_run_gate", return_value=gate_result):
            with patch.object(ship, "_check_release_guard", return_value=None):
                with patch.object(ship, "_is_monolithic_commit", return_value=False):
                    with patch.object(
                        ship, "_has_merge_conflicts", return_value=(False, "")
                    ):
                        with patch.object(
                            ship,
                            "_merge_into_target",
                            return_value=(True, "merged", "abc123"),
                        ):
                            with patch.object(ship.aet_state, "cmd_record_merge", return_value=0) as close_mock:
                                rc = ship.cmd_merge(
                                    argparse.Namespace(
                                        plan=str(self.plan_path), branch="dev", dry_run=False
                                    )
                                )
        self.assertEqual(rc, 0)
        close_mock.assert_called_once()
        ns = close_mock.call_args[0][0]
        self.assertEqual(ns.task_id, "t1")
        self.assertEqual(ns.merge_commit, "abc123")
        self.assertEqual(ns.target_branch, "dev")

    def test_merge_dry_run_skips_closure(self):
        """Dry-run reports success but does not call record-merge."""
        gate_result = ship.GateResult(
            ok=True,
            pr_base="origin/dev",
            rebased=False,
            scope_audit=[],
            dry_run=True,
            message="Gate passed.",
        )
        with patch.object(ship, "_run_gate", return_value=gate_result):
            with patch.object(ship, "_check_release_guard", return_value=None):
                with patch.object(ship, "_is_monolithic_commit", return_value=False):
                    with patch.object(
                        ship, "_has_merge_conflicts", return_value=(False, "")
                    ):
                        with patch.object(
                            ship,
                            "_merge_into_target",
                            return_value=(True, "would merge", None),
                        ):
                            with patch.object(ship.aet_state, "cmd_record_merge") as close_mock:
                                rc = ship.cmd_merge(
                                    argparse.Namespace(
                                        plan=str(self.plan_path), branch="dev", dry_run=True
                                    )
                                )
        self.assertEqual(rc, 0)
        close_mock.assert_not_called()


class TestShipMergeIntoTarget(unittest.TestCase):
    """Tests for `_merge_into_target` worktree and merge logic."""

    def test_merge_creates_temp_worktree_and_cleans_up(self):
        """When no target worktree exists, create one, merge, push, and remove it."""
        repo_root = "/repo"
        worktree_path = Path(repo_root) / ".worktrees" / ".merge-dev-1234"
        responses = {
            ("git", "worktree", "list", "--porcelain"): (0, "", ""),
            ("git", "rev-parse", "--show-toplevel"): (0, f"{repo_root}\n", ""),
            (
                "git",
                "worktree",
                "add",
                "--checkout",
                str(worktree_path),
                "origin/dev",
            ): (0, "", ""),
            ("git", "-C", str(worktree_path), "checkout", "dev"): (0, "", ""),
            ("git", "-C", str(worktree_path), "pull", "origin", "dev"): (0, "", ""),
            (
                "git",
                "-C",
                str(worktree_path),
                "merge",
                "--no-ff",
                "-m",
                "Merge feat-001 into dev",
                "feat-001",
            ): (0, "", ""),
            ("git", "-C", str(worktree_path), "rev-parse", "HEAD"): (
                0,
                "merge-commit-sha\n",
                "",
            ),
            ("git", "-C", str(worktree_path), "push", "origin", "dev"): (0, "", ""),
            ("git", "worktree", "remove", "--force", str(worktree_path)): (0, "", ""),
        }
        commands: list[tuple[str, ...]] = []

        def mock_run(cmd, **kwargs):
            commands.append(tuple(cmd))
            args = tuple(cmd)
            if args in responses:
                rc, out, err = responses[args]
                return MockResult(rc, out, err)
            return MockResult(1, "", f"unexpected: {cmd!r}")

        with patch.object(ship.subprocess, "run", side_effect=mock_run):
            with patch.object(ship.os, "getpid", return_value=1234):
                ok, msg, merge_commit = ship._merge_into_target("dev", "feat-001", False)

        self.assertTrue(ok)
        self.assertEqual(merge_commit, "merge-commit-sha")
        self.assertIn(
            ("git", "worktree", "remove", "--force", str(worktree_path)), commands
        )

    def test_merge_reuses_existing_worktree(self):
        """When a target worktree already exists, use it instead of creating one."""
        existing = "/repo/.worktrees/dev"
        responses = {
            (
                "git",
                "worktree",
                "list",
                "--porcelain",
            ): (
                0,
                f"worktree {existing}\nbranch refs/heads/dev\n",
                "",
            ),
            ("git", "-C", existing, "checkout", "dev"): (0, "", ""),
            ("git", "-C", existing, "pull", "origin", "dev"): (0, "", ""),
            (
                "git",
                "-C",
                existing,
                "merge",
                "--no-ff",
                "-m",
                "Merge feat-001 into dev",
                "feat-001",
            ): (0, "", ""),
            ("git", "-C", existing, "rev-parse", "HEAD"): (
                0,
                "merge-commit-sha\n",
                "",
            ),
            ("git", "-C", existing, "push", "origin", "dev"): (0, "", ""),
        }
        commands: list[tuple[str, ...]] = []

        def mock_run(cmd, **kwargs):
            commands.append(tuple(cmd))
            args = tuple(cmd)
            if args in responses:
                rc, out, err = responses[args]
                return MockResult(rc, out, err)
            return MockResult(1, "", f"unexpected: {cmd!r}")

        with patch.object(ship.subprocess, "run", side_effect=mock_run):
            ok, msg, merge_commit = ship._merge_into_target("dev", "feat-001", False)

        self.assertTrue(ok)
        self.assertEqual(merge_commit, "merge-commit-sha")
        self.assertFalse(
            any(c[1] == "worktree" and c[2] == "add" for c in commands)
        )


if __name__ == "__main__":
    unittest.main()
