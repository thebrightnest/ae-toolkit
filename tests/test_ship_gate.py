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

from aet import plan_parser
from aet.backends.git_refs_backend import GitRefsBackend

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
    Unknown commands are delegated to the real subprocess so the git-refs backend
    can operate on the temporary repository.
    If record is provided, it is a list that receives every invoked command.
    """
    real_run = subprocess.run

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
        return real_run(cmd, **kwargs)

    return mock_run


class TestShipGateParser(unittest.TestCase):
    def test_gate_subcommand_parses_plan_argument(self):
        """aet ship gate accepts a task id."""
        parser = ship.build_parser()
        args = parser.parse_args(["gate", "t1"])
        self.assertEqual(args.command, "gate")
        self.assertEqual(args.plan, "t1")


class TestShipGateChecks(unittest.TestCase):
    """Behavior-driven tests for each aet ship gate check."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        base = Path(self.tmpdir.name)

        self.repo = base / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "-C", str(self.repo), "init", "-q"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "config", "user.email", "test@example.com"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "config", "user.name", "Test User"], check=True)
        (self.repo / "README.md").write_text("hello\n", encoding="utf-8")
        (self.repo / ".agents").mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "-C", str(self.repo), "add", "."], check=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "-q", "-m", "initial"], check=True)

        self.plan_path = self.repo / "docs" / "plans" / "t1.md"
        self.plan_path.parent.mkdir(parents=True)
        self._default_content = (
            "---\n"
            "id: t1\n"
            "status: awaiting_merge\n"
            "---\n\n"
            "# Plan T1\n\n"
            "## Task List\n\n"
            "- [x] task one\n"
            "- [x] task two\n\n"
            "---\n\n"
            "*Stage: implemented*\n"
        )
        self.plan_path.write_text(self._default_content, encoding="utf-8")

        self.cwd = os.getcwd()
        self.addCleanup(os.chdir, self.cwd)
        os.chdir(self.repo)

    def _spec(self, content: str | None = None) -> dict:
        """Build a spec dict from the given plan content."""
        text = content if content is not None else self.plan_path.read_text(encoding="utf-8")
        return plan_parser.extract_plan_spec_from_text(text, "t1")

    def _save_task(self, spec: dict, task_id: str = "t1") -> None:
        """Write a live task record with the given spec to the queue."""
        backend = GitRefsBackend(
            queue_file=str(self.repo / ".agents" / "aet-queue"),
            history_file=str(self.repo / ".agents" / "work-history.jsonl"),
        )
        backend.save(
            [
                {
                    "id": task_id,
                    "state": "awaiting_merge",
                    "stage": "qa-complete",
                    "branch": "feat-001",
                    "plan_file": str(Path("docs/plans") / f"{task_id}.md"),
                    "spec": spec,
                }
            ]
        )

    def _base_responses(self, branch="feat-001"):
        """Default happy-path git responses (independent branch, no rebase needed)."""
        origin_main = "origin-main-sha"
        return {
            ("git", "rev-parse", "--show-toplevel"): (0, f"{self.repo}\n", ""),
            ("git", "fetch", "origin"): (0, "", ""),
            ("git", "merge-base", "HEAD", "origin/main"): (0, f"{origin_main}\n", ""),
            ("git", "rev-parse", "origin/main"): (0, f"{origin_main}\n", ""),
            ("git", "branch", "--show-current"): (0, f"{branch}\n", ""),
            ("git", "status", "--short"): (0, "", ""),
            ("git", "diff", "origin/main", "--name-only"): (0, "src/aet/cli/ship.py\n", ""),
            ("true",): (0, "", ""),
        }

    def _shell(self, cmd):
        return (cmd,)

    def test_gate_rebase_conflict_stops(self):
        """A rebase conflict onto origin/main stops the gate with the documented message."""
        self._save_task(self._spec())
        responses = self._base_responses()
        # Make the branch independent but behind origin/main.
        responses[("git", "merge-base", "HEAD", "origin/main")] = (0, "old-merge-base\n", "")
        responses[("git", "rev-parse", "origin/main")] = (0, "origin-main-sha\n", "")
        responses[("git", "rebase", "--onto", "origin/main", "old-merge-base", "feat-001")] = (1, "", "conflict")
        responses[("git", "log", "--oneline", "--decorate", "--ancestry-path", "old-merge-base..HEAD")] = (0, "", "")

        with patch.object(ship.subprocess, "run", side_effect=_subprocess_mock(responses)):
            rc = ship.cmd_gate(ship.parse_args(["gate", "t1"]))

        self.assertNotEqual(rc, 0)

    def test_gate_dirty_tree_stops(self):
        """An uncommitted working tree stops the gate and prompts stash/commit/abort."""
        self._save_task(self._spec())
        responses = self._base_responses()
        responses[("git", "status", "--short")] = (0, " M src/aet/cli/ship.py\n", "")

        with patch.object(ship.subprocess, "run", side_effect=_subprocess_mock(responses)):
            rc = ship.cmd_gate(ship.parse_args(["gate", "t1"]))

        self.assertNotEqual(rc, 0)

    def test_gate_test_failure_stops(self):
        """A failing test suite stops the gate."""
        self._save_task(self._spec())
        responses = self._base_responses()
        responses[("false",)] = (1, "", "test failure")
        env = {"AET_SHIP_TEST_CMD": "false"}

        with patch.dict(os.environ, env):
            with patch.object(ship.subprocess, "run", side_effect=_subprocess_mock(responses)):
                rc = ship.cmd_gate(ship.parse_args(["gate", "t1"]))

        self.assertNotEqual(rc, 0)

    def test_gate_coverage_drop_flagged(self):
        """A coverage drop is flagged but does not stop the gate."""
        self._save_task(self._spec())
        responses = self._base_responses()
        responses[("false",)] = (1, "", "coverage dropped")
        env = {
            "AET_SHIP_TEST_CMD": "true",
            "AET_SHIP_COVERAGE_CMD": "false",
        }

        with patch.dict(os.environ, env):
            with patch.object(ship.subprocess, "run", side_effect=_subprocess_mock(responses)):
                rc = ship.cmd_gate(ship.parse_args(["gate", "t1"]))

        self.assertEqual(rc, 0)

    def test_gate_incomplete_plan_flagged(self):
        """An unchecked task in the plan is flagged but does not stop the gate."""
        content = (
            "---\n"
            "id: t1\n"
            "status: awaiting_merge\n"
            "---\n\n"
            "# Plan T1\n\n"
            "## Task List\n\n"
            "- [ ] incomplete task\n\n"
            "---\n\n"
            "*Stage: implemented*\n"
        )
        self._save_task(self._spec(content))
        responses = self._base_responses()
        env = {"AET_SHIP_TEST_CMD": "true"}

        with patch.dict(os.environ, env):
            with patch.object(ship.subprocess, "run", side_effect=_subprocess_mock(responses)):
                rc = ship.cmd_gate(ship.parse_args(["gate", "t1"]))

        self.assertEqual(rc, 0)

    def test_gate_stage_skip_synced(self):
        """When the plan is synced, aet-review and aet-cso are skipped."""
        self._save_task(self._spec())
        responses = self._base_responses()
        env = {"AET_SHIP_TEST_CMD": "true"}

        with patch.object(ship.subprocess, "run", side_effect=_subprocess_mock(responses)):
            with patch.dict(os.environ, env):
                rc = ship.cmd_gate(ship.parse_args(["gate", "t1"]))

        self.assertEqual(rc, 0)

    def test_gate_stage_skip_reviewed(self):
        """When the plan is reviewed, only aet-review is skipped."""
        self._save_task(self._spec())
        responses = self._base_responses()
        env = {"AET_SHIP_TEST_CMD": "true"}

        with patch.object(ship.subprocess, "run", side_effect=_subprocess_mock(responses)):
            with patch.dict(os.environ, env):
                rc = ship.cmd_gate(ship.parse_args(["gate", "t1"]))

        self.assertEqual(rc, 0)

    def test_gate_stage_qa_complete_runs_review(self):
        """When the plan is qa-complete, aet-review is not skipped."""
        self._save_task(self._spec())
        responses = self._base_responses()
        env = {"AET_SHIP_TEST_CMD": "true"}

        with patch.object(ship.subprocess, "run", side_effect=_subprocess_mock(responses)):
            with patch.dict(os.environ, env):
                rc = ship.cmd_gate(ship.parse_args(["gate", "t1"]))

        self.assertEqual(rc, 0)

    def test_gate_missing_evidence_stops_for_critical(self):
        """A critical-class plan without verify evidence stops the gate."""
        self.test_verify_evidence_required_for_critical()

    def test_verify_evidence_required_for_critical(self):
        """A critical task whose workflow declares a verify stage is refused without evidence and passes with it."""
        content = (
            "---\n"
            "id: t1\n"
            "status: awaiting_merge\n"
            "work_class: critical\n"
            "---\n\n"
            "# Plan T1\n\n"
            "## Task List\n\n"
            "- [x] task one\n\n"
            "---\n\n"
            "*Stage: implemented*\n"
        )
        self._save_task(self._spec(content))
        responses = self._base_responses()
        env = {"AET_SHIP_TEST_CMD": "true"}

        # Without evidence -> refused
        with patch.object(ship.subprocess, "run", side_effect=_subprocess_mock(responses)):
            with patch.dict(os.environ, env):
                rc = ship.cmd_gate(ship.parse_args(["gate", "t1"]))
        self.assertNotEqual(rc, 0)

        # With evidence -> passes
        evidence_dir = self.repo / ".agents" / "verify"
        evidence_dir.mkdir(parents=True, exist_ok=True)
        (evidence_dir / "t1-evidence.md").write_text("# Evidence\n", encoding="utf-8")

        with patch.object(ship.subprocess, "run", side_effect=_subprocess_mock(responses)):
            with patch.dict(os.environ, env):
                rc = ship.cmd_gate(ship.parse_args(["gate", "t1"]))
        self.assertEqual(rc, 0)

    def test_workflow_without_verify_stage_imposes_no_requirement(self):
        """A workflow with no verify stage produces no verify requirement, including for a critical task."""
        import json

        workflows_dir = self.repo / ".agents" / "workflows"
        workflows_dir.mkdir(parents=True, exist_ok=True)
        noverify_workflow = {
            "version": 1,
            "name": "noverify",
            "done_state": "done",
            "stages": [
                {"name": "plan-approved", "skills": ["aet-tdd"], "evidence": None, "gate_key": None},
                {"name": "implemented", "skills": ["aet-qa"], "evidence": "qa", "gate_key": None},
            ],
            "execution_policy": {"session_groups": [["plan-approved", "implemented"]]},
            "routing": {"default": {"harness": "claude", "model": None}, "by_stage": {}},
        }
        (workflows_dir / "noverify.json").write_text(json.dumps(noverify_workflow), encoding="utf-8")

        content = (
            "---\n"
            "id: t1\n"
            "status: awaiting_merge\n"
            "workflow: noverify\n"
            "work_class: critical\n"
            "---\n\n"
            "# Plan T1\n\n"
            "## Task List\n\n"
            "- [x] task one\n\n"
            "---\n\n"
            "*Stage: implemented*\n"
        )
        self._save_task(self._spec(content))
        responses = self._base_responses()
        env = {"AET_SHIP_TEST_CMD": "true"}

        with patch.object(ship.subprocess, "run", side_effect=_subprocess_mock(responses)):
            with patch.dict(os.environ, env):
                rc = ship.cmd_gate(ship.parse_args(["gate", "t1"]))

        self.assertEqual(rc, 0)

    def test_refusal_names_the_producing_stage(self):
        """The refusal message names the workflow stage that produces verify evidence."""
        content = (
            "---\n"
            "id: t1\n"
            "status: awaiting_merge\n"
            "work_class: critical\n"
            "---\n\n"
            "# Plan T1\n\n"
            "## Task List\n\n"
            "- [x] task one\n\n"
            "---\n\n"
            "*Stage: implemented*\n"
        )
        self._save_task(self._spec(content))
        responses = self._base_responses()
        env = {"AET_SHIP_TEST_CMD": "true"}

        args = ship.parse_args(["gate", "t1"])
        args.task_id = "t1"
        args.spec = self._spec(content)

        with patch.object(ship.subprocess, "run", side_effect=_subprocess_mock(responses)):
            with patch.dict(os.environ, env):
                result = ship._run_gate(args)

        self.assertFalse(result.ok)
        self.assertIn("synced", result.message)

    def test_gate_scope_audit_flags_other_prds(self):
        """A diff touching other PRD files is flagged but does not stop the gate."""
        content = (
            "---\n"
            "id: t1\n"
            "status: awaiting_merge\n"
            "---\n\n"
            "# Plan T1\n\n"
            "Source: `docs/prds/demo-prd.md`\n\n"
            "## Task List\n\n"
            "- [x] task one\n\n"
            "---\n\n"
            "*Stage: implemented*\n"
        )
        self._save_task(self._spec(content))
        responses = self._base_responses()
        responses[("git", "diff", "origin/main", "--name-only")] = (
            0,
            "src/aet/cli/ship.py\ndocs/prds/OTHER-01.md\n",
            "",
        )
        env = {"AET_SHIP_TEST_CMD": "true"}

        with patch.object(ship.subprocess, "run", side_effect=_subprocess_mock(responses)):
            with patch.dict(os.environ, env):
                rc = ship.cmd_gate(ship.parse_args(["gate", "t1"]))

        self.assertEqual(rc, 0)

    def test_gate_happy_path_all_checks_pass(self):
        """When every gate check passes, the gate returns 0."""
        self._save_task(self._spec())
        responses = self._base_responses()
        env = {"AET_SHIP_TEST_CMD": "true"}

        with patch.object(ship.subprocess, "run", side_effect=_subprocess_mock(responses)):
            with patch.dict(os.environ, env):
                rc = ship.cmd_gate(ship.parse_args(["gate", "t1"]))

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
        plan_content = (
            "---\n"
            "id: t1\n"
            "status: awaiting_merge\n"
            "---\n\n"
            "# Plan T1\n\n"
            "## Task List\n\n"
            "- [x] task one\n\n"
            "---\n\n"
            "*Stage: implemented*\n"
        )
        self.plan_path.write_text(plan_content, encoding="utf-8")
        spec = plan_parser.extract_plan_spec_from_text(plan_content, "t1")
        backend = GitRefsBackend(
            queue_file=str(self.clone / ".agents" / "aet-queue"),
            history_file=str(self.clone / ".agents" / "work-history.jsonl"),
        )
        backend.save(
            [
                {
                    "id": "t1",
                    "state": "awaiting_merge",
                    "stage": "qa-complete",
                    "branch": "feat-001",
                    "plan_file": "docs/plans/t1.md",
                    "spec": spec,
                }
            ]
        )
        src_dir = self.clone / "src" / "aet" / "cli"
        src_dir.mkdir(parents=True)
        (src_dir / "ship.py").write_text("# ship\n", encoding="utf-8")
        self._git("add", ".")
        self._git("commit", "-m", "feat: ship gate")

        self.cwd = os.getcwd()
        self.addCleanup(os.chdir, self.cwd)

    def _git(self, *args):
        return subprocess.run(["git", *args], cwd=str(self.clone), check=True, capture_output=True, text=True)

    def test_gate_integration_happy_path(self):
        """The full gate runs successfully against a real git repo."""
        os.chdir(str(self.clone))
        env = {"AET_SHIP_TEST_CMD": "true"}
        with patch.dict(os.environ, env):
            rc = ship.cmd_gate(ship.parse_args(["gate", "t1"]))
        self.assertEqual(rc, 0)

    def test_gate_uses_non_main_trunk_when_origin_head_points_elsewhere(self):
        """When refs/remotes/origin/HEAD points at a non-main branch, gate uses it."""
        # Create and push a develop branch, then make it the remote HEAD symbol.
        self._git("checkout", "-b", "develop")
        self._git("push", "-u", "origin", "develop")
        self._git("remote", "set-head", "origin", "develop")
        self._git("checkout", "feat-001")
        os.chdir(str(self.clone))
        env = {"AET_SHIP_TEST_CMD": "true"}
        commands: list[tuple[str, ...]] = []
        original_run = ship.subprocess.run

        def _recording_run(cmd, **kwargs):
            commands.append(tuple(cmd))
            return original_run(cmd, **kwargs)

        with patch.dict(os.environ, env):
            with patch.object(ship.subprocess, "run", side_effect=_recording_run):
                rc = ship.cmd_gate(ship.parse_args(["gate", "t1"]))

        self.assertEqual(rc, 0)
        self.assertTrue(any(c[0] == "git" and c[1] == "merge-base" and "origin/develop" in c for c in commands))


if __name__ == "__main__":
    unittest.main()
