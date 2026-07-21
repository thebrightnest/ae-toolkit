"""Tests for the aet-ship pre-merge gate (`aet ship gate`)."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_SHIP_PY = Path(__file__).parents[1] / "src" / "aet" / "cli" / "ship.py"
_spec = importlib.util.spec_from_loader(
    "aet_ship_gate", importlib.machinery.SourceFileLoader("aet_ship_gate", str(_SHIP_PY))
)
ship = importlib.util.module_from_spec(_spec)
sys.modules["aet_ship_gate"] = ship
_spec.loader.exec_module(ship)


class MockResult:
    def __init__(self, returncode, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _subprocess_mock(responses, record=None):
    """Return a mock subprocess.run that answers git and test commands.

    responses maps tuple(program, *args) or command_string -> (returncode, stdout, stderr).
    For shell=True commands the invocation is a string; the response key can be that
    string or a (shell, "-c", command_string) tuple.
    If record is provided, it is a list that receives every invoked command.
    """

    def _lookup(cmd):
        if isinstance(cmd, str):
            if cmd in responses:
                return responses[cmd]
            return None
        args = tuple(cmd)
        if args in responses:
            return responses[args]
        # Shell command lookup: match the -c payload.
        if len(args) >= 3 and args[1] == "-c":
            for key, value in responses.items():
                if isinstance(key, tuple) and len(key) >= 3 and key[1] == "-c" and key[2] == args[2]:
                    return value
        return None

    def mock_run(cmd, **kwargs):
        if record is not None:
            record.append(cmd if isinstance(cmd, str) else tuple(cmd))
        hit = _lookup(cmd)
        if hit is not None:
            rc, out, err = hit
            return MockResult(rc, out, err)
        return MockResult(1, "", f"unexpected: {cmd!r}")

    return mock_run


class TestShipGateParser(unittest.TestCase):
    def test_gate_subcommand_parses_plan_argument(self):
        """aet ship gate accepts a plan file path."""
        parser = ship.build_parser()
        args = parser.parse_args(["gate", "docs/plans/t1.md"])
        self.assertEqual(args.command, "gate")
        self.assertEqual(args.plan, "docs/plans/t1.md")


class TestShipGateChecks(unittest.TestCase):
    """Behavior-driven tests for each aet ship gate check."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        base = Path(self.tmpdir.name)

        self.plan_path = base / "docs" / "plans" / "t1.md"
        self.plan_path.parent.mkdir(parents=True)
        self.plan_path.write_text(
            "---\n"
            "id: t1\n"
            "status: awaiting_merge\n"
            "---\n\n"
            "# Plan T1\n\n"
            "## Task List\n\n"
            "- [x] task one\n"
            "- [x] task two\n\n"
            "---\n\n"
            "*Stage: implemented*\n",
            encoding="utf-8",
        )

        self.cwd = os.getcwd()
        self.addCleanup(os.chdir, self.cwd)

    def _base_responses(self, branch="feat-001"):
        """Default happy-path git responses (independent branch, no rebase needed)."""
        origin_main = "origin-main-sha"
        return {
            ("git", "fetch", "origin"): (0, "", ""),
            ("git", "merge-base", "HEAD", "origin/main"): (0, f"{origin_main}\n", ""),
            ("git", "rev-parse", "origin/main"): (0, f"{origin_main}\n", ""),
            ("git", "branch", "--show-current"): (0, f"{branch}\n", ""),
            ("git", "status", "--short"): (0, "", ""),
            ("git", "diff", "origin/main", "--name-only"): (0, "src/aet/cli/ship.py\n", ""),
            "true": (0, "", ""),
        }

    def _shell(self, cmd):
        return cmd

    def test_gate_rebase_conflict_stops(self):
        """A rebase conflict onto origin/main stops the gate with the documented message."""
        responses = self._base_responses()
        # Make the branch independent but behind origin/main.
        responses[("git", "merge-base", "HEAD", "origin/main")] = (0, "old-merge-base\n", "")
        responses[("git", "rev-parse", "origin/main")] = (0, "origin-main-sha\n", "")
        responses[
            ("git", "rebase", "--onto", "origin/main", "old-merge-base", "feat-001")
        ] = (1, "", "conflict")

        with patch.object(ship.subprocess, "run", side_effect=_subprocess_mock(responses)):
            rc = ship.cmd_gate(ship.parse_args(["gate", str(self.plan_path)]))

        self.assertNotEqual(rc, 0)

    def test_gate_dirty_tree_stops(self):
        """An uncommitted working tree stops the gate and prompts stash/commit/abort."""
        responses = self._base_responses()
        responses[("git", "status", "--short")] = (0, " M src/aet/cli/ship.py\n", "")

        with patch.object(ship.subprocess, "run", side_effect=_subprocess_mock(responses)):
            rc = ship.cmd_gate(ship.parse_args(["gate", str(self.plan_path)]))

        self.assertNotEqual(rc, 0)

    def test_gate_test_failure_stops(self):
        """A failing test suite stops the gate."""
        responses = self._base_responses()
        responses[self._shell("false")] = (1, "", "test failure")
        env = {"AET_SHIP_TEST_CMD": "false"}

        with patch.dict(os.environ, env):
            with patch.object(
                ship.subprocess, "run", side_effect=_subprocess_mock(responses)
            ):
                rc = ship.cmd_gate(ship.parse_args(["gate", str(self.plan_path)]))

        self.assertNotEqual(rc, 0)

    def test_gate_coverage_drop_flagged(self):
        """A coverage drop is flagged but does not stop the gate."""
        responses = self._base_responses()
        responses[self._shell("false")] = (1, "", "coverage dropped")
        env = {
            "AET_SHIP_TEST_CMD": "true",
            "AET_SHIP_COVERAGE_CMD": "false",
        }

        with patch.dict(os.environ, env):
            with patch.object(
                ship.subprocess, "run", side_effect=_subprocess_mock(responses)
            ):
                rc = ship.cmd_gate(ship.parse_args(["gate", str(self.plan_path)]))

        self.assertEqual(rc, 0)

    def _write_plan_stage(self, stage: str, tasks: list[str] | None = None) -> None:
        """Rewrite the plan file with the given stage and optional task list."""
        task_block = ""
        if tasks is not None:
            task_block = "## Task List\n\n" + "\n".join(tasks) + "\n\n"
        self.plan_path.write_text(
            "---\n"
            "id: t1\n"
            "status: awaiting_merge\n"
            "---\n\n"
            "# Plan T1\n\n"
            f"{task_block}"
            "---\n\n"
            f"*Stage: {stage}*\n",
            encoding="utf-8",
        )

    def test_gate_incomplete_plan_flagged(self):
        """An unchecked task in the plan is flagged but does not stop the gate."""
        self._write_plan_stage("implemented", ["- [ ] incomplete task"])
        responses = self._base_responses()
        env = {"AET_SHIP_TEST_CMD": "true"}

        with patch.dict(os.environ, env):
            with patch.object(
                ship.subprocess, "run", side_effect=_subprocess_mock(responses)
            ):
                rc = ship.cmd_gate(ship.parse_args(["gate", str(self.plan_path)]))

        self.assertEqual(rc, 0)

    def test_gate_stage_skip_synced(self):
        """When the plan is synced, aet-review and aet-cso are skipped."""
        self._write_plan_stage("synced")
        responses = self._base_responses()
        env = {"AET_SHIP_TEST_CMD": "true"}

        with patch.object(
            ship.subprocess, "run", side_effect=_subprocess_mock(responses)
        ):
            with patch.dict(os.environ, env):
                rc = ship.cmd_gate(ship.parse_args(["gate", str(self.plan_path)]))

        self.assertEqual(rc, 0)

    def test_gate_stage_skip_reviewed(self):
        """When the plan is reviewed, only aet-review is skipped."""
        self._write_plan_stage("reviewed")
        responses = self._base_responses()
        env = {"AET_SHIP_TEST_CMD": "true"}

        with patch.object(
            ship.subprocess, "run", side_effect=_subprocess_mock(responses)
        ):
            with patch.dict(os.environ, env):
                rc = ship.cmd_gate(ship.parse_args(["gate", str(self.plan_path)]))

        self.assertEqual(rc, 0)

    def test_gate_stage_qa_complete_runs_review(self):
        """When the plan is qa-complete, aet-review is not skipped."""
        self._write_plan_stage("qa-complete")
        responses = self._base_responses()
        env = {"AET_SHIP_TEST_CMD": "true"}

        with patch.object(
            ship.subprocess, "run", side_effect=_subprocess_mock(responses)
        ):
            with patch.dict(os.environ, env):
                rc = ship.cmd_gate(ship.parse_args(["gate", str(self.plan_path)]))

        self.assertEqual(rc, 0)

    def _write_work_class(self, work_class: str) -> None:
        """Append a Work class footer to the plan file."""
        content = self.plan_path.read_text(encoding="utf-8")
        content = content.replace("*Stage: implemented*\n", "")
        content += f"\n_Work class: {work_class}_\n*Stage: implemented*\n"
        self.plan_path.write_text(content, encoding="utf-8")

    def test_gate_missing_evidence_stops_for_critical(self):
        """A critical-class plan without verify evidence stops the gate."""
        self._write_plan_stage("implemented", ["- [x] task one"])
        self._write_work_class("critical")
        responses = self._base_responses()
        env = {"AET_SHIP_TEST_CMD": "true"}

        with patch.object(
            ship.subprocess, "run", side_effect=_subprocess_mock(responses)
        ):
            with patch.dict(os.environ, env):
                rc = ship.cmd_gate(ship.parse_args(["gate", str(self.plan_path)]))

        self.assertNotEqual(rc, 0)

    def test_gate_scope_audit_flags_other_plans(self):
        """A diff touching other plan files is flagged but does not stop the gate."""
        self._write_plan_stage("implemented", ["- [x] task one"])
        responses = self._base_responses()
        responses[("git", "diff", "origin/main", "--name-only")] = (
            0,
            "src/aet/cli/ship.py\ndocs/plans/OTHER-01.md\n",
            "",
        )
        env = {"AET_SHIP_TEST_CMD": "true"}

        with patch.object(
            ship.subprocess, "run", side_effect=_subprocess_mock(responses)
        ):
            with patch.dict(os.environ, env):
                rc = ship.cmd_gate(ship.parse_args(["gate", str(self.plan_path)]))

        self.assertEqual(rc, 0)

    def test_gate_happy_path_all_checks_pass(self):
        """When every gate check passes, the gate returns 0."""
        self._write_plan_stage("implemented", ["- [x] task one"])
        responses = self._base_responses()
        env = {"AET_SHIP_TEST_CMD": "true"}

        with patch.object(
            ship.subprocess, "run", side_effect=_subprocess_mock(responses)
        ):
            with patch.dict(os.environ, env):
                rc = ship.cmd_gate(ship.parse_args(["gate", str(self.plan_path)]))

        self.assertEqual(rc, 0)


class TestShipGateIntegration(unittest.TestCase):
    """Integration test using a real scratch git repository."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        base = Path(self.tmpdir.name)

        self.origin = base / "origin.git"
        self.origin.mkdir()
        self.clone = base / "repo"
        self.clone.mkdir()

        # Create a bare origin repository.
        subprocess.run(["git", "init", "--bare", str(self.origin)], check=True, capture_output=True)

        # Clone it and set up an initial main commit.
        subprocess.run(
            ["git", "clone", str(self.origin), str(self.clone)],
            check=True,
            capture_output=True,
        )
        self._git("config", "user.email", "test@example.com")
        self._git("config", "user.name", "Test User")
        readme = self.clone / "README.md"
        readme.write_text("hello\n", encoding="utf-8")
        self._git("add", "README.md")
        self._git("commit", "-m", "initial")
        self._git("push", "-u", "origin", "main")

        # Create a feature branch with a change.
        self._git("checkout", "-b", "feat-001")
        plan_dir = self.clone / "docs" / "plans"
        plan_dir.mkdir(parents=True)
        self.plan_path = plan_dir / "t1.md"
        self.plan_path.write_text(
            "---\n"
            "id: t1\n"
            "status: awaiting_merge\n"
            "---\n\n"
            "# Plan T1\n\n"
            "## Task List\n\n"
            "- [x] task one\n\n"
            "---\n\n"
            "*Stage: implemented*\n",
            encoding="utf-8",
        )
        src_dir = self.clone / "src" / "aet" / "cli"
        src_dir.mkdir(parents=True)
        (src_dir / "ship.py").write_text("# ship\n", encoding="utf-8")
        self._git("add", ".")
        self._git("commit", "-m", "feat: ship gate")

        self.cwd = os.getcwd()
        self.addCleanup(os.chdir, self.cwd)

    def _git(self, *args):
        return subprocess.run(
            ["git", *args], cwd=str(self.clone), check=True, capture_output=True, text=True
        )

    def test_gate_integration_happy_path(self):
        """The full gate runs successfully against a real git repo."""
        os.chdir(str(self.clone))
        env = {"AET_SHIP_TEST_CMD": "true"}
        with patch.dict(os.environ, env):
            rc = ship.cmd_gate(ship.parse_args(["gate", str(self.plan_path)]))
        self.assertEqual(rc, 0)
