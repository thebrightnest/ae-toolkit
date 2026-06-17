"""Tests for aet-state derive_status."""

import importlib.machinery
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_AET_STATE_PY = Path(__file__).parent.parent / "aet-work" / "bin" / "aet-state"
_spec = importlib.util.spec_from_loader(
    "aet_state", importlib.machinery.SourceFileLoader("aet_state", str(_AET_STATE_PY))
)
aet_state = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(aet_state)


class MockResult:
    def __init__(self, returncode, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _git_mock(responses):
    """Return a mock subprocess.run that answers git commands.

    responses maps tuple(git_args) -> (returncode, stdout, stderr).
    """

    def mock_run(cmd, **kwargs):
        args = tuple(cmd[1:])
        rc, out, err = responses.get(args, (1, "", ""))
        return MockResult(rc, out, err)

    return mock_run


class TestDeriveStatus(unittest.TestCase):
    def test_unblocked_when_blockers_terminal(self):
        """A task with no branch and all blockers merged/abandoned is unblocked."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Plan\n")
            plan_path = f.name

        def blocker_status(task_id):
            return "merged" if task_id == "t1" else "unknown"

        task = {
            "id": "t2",
            "plan_file": plan_path,
            "branch": None,
            "blocked_by": ["t1"],
        }

        responses = {
            ("show-ref", "--verify", "--quiet", "refs/heads/None"): (1, "", ""),
        }

        with patch.object(aet_state.subprocess, "run", side_effect=_git_mock(responses)):
            derived = aet_state.derive_status(task, blocker_status)

        self.assertEqual(derived["derived_status"], "unblocked")

    def test_blocked_when_blockers_not_terminal(self):
        """A task with no branch and a non-terminal blocker is blocked."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Plan\n")
            plan_path = f.name

        def blocker_status(task_id):
            return "in-progress" if task_id == "t1" else "unknown"

        task = {
            "id": "t2",
            "plan_file": plan_path,
            "branch": None,
            "blocked_by": ["t1"],
        }

        responses = {
            ("show-ref", "--verify", "--quiet", "refs/heads/None"): (1, "", ""),
        }

        with patch.object(aet_state.subprocess, "run", side_effect=_git_mock(responses)):
            derived = aet_state.derive_status(task, blocker_status)

        self.assertEqual(derived["derived_status"], "blocked")

    def test_unblocked_when_blocker_abandoned(self):
        """An abandoned blocker is terminal, so the dependent is unblocked."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Plan\n")
            plan_path = f.name

        def blocker_status(task_id):
            return "abandoned" if task_id == "t1" else "unknown"

        task = {
            "id": "t2",
            "plan_file": plan_path,
            "branch": None,
            "blocked_by": ["t1"],
        }

        responses = {
            ("show-ref", "--verify", "--quiet", "refs/heads/None"): (1, "", ""),
        }

        with patch.object(aet_state.subprocess, "run", side_effect=_git_mock(responses)):
            derived = aet_state.derive_status(task, blocker_status)

        self.assertEqual(derived["derived_status"], "unblocked")

    def test_in_progress_when_branch_exists(self):
        """A local branch takes precedence over blocker-aware statuses."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Plan\n")
            plan_path = f.name

        task = {
            "id": "t1",
            "plan_file": plan_path,
            "branch": "feat-001",
            "blocked_by": ["t0"],
        }

        responses = {
            ("show-ref", "--verify", "--quiet", "refs/heads/feat-001"): (0, "", ""),
            ("merge-base", "--is-ancestor", "feat-001", "origin/main"): (1, "", ""),
        }

        with patch.object(aet_state.subprocess, "run", side_effect=_git_mock(responses)):
            derived = aet_state.derive_status(task)

        self.assertEqual(derived["derived_status"], "in-progress")

    def test_merged_when_branch_on_main(self):
        """A branch that is an ancestor of origin/main is merged."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Plan\n")
            plan_path = f.name

        task = {
            "id": "t1",
            "plan_file": plan_path,
            "branch": "feat-001",
        }

        responses = {
            ("show-ref", "--verify", "--quiet", "refs/heads/feat-001"): (0, "", ""),
            ("merge-base", "--is-ancestor", "feat-001", "origin/main"): (0, "", ""),
        }

        with patch.object(aet_state.subprocess, "run", side_effect=_git_mock(responses)):
            derived = aet_state.derive_status(task)

        self.assertEqual(derived["derived_status"], "merged")

    def test_merged_when_merge_commit_on_main(self):
        """A merge_commit that is an ancestor of origin/main is merged."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Plan\n")
            plan_path = f.name

        task = {
            "id": "t1",
            "plan_file": plan_path,
            "branch": None,
            "merge_commit": "abc1234",
        }

        responses = {
            ("show-ref", "--verify", "--quiet", "refs/heads/None"): (1, "", ""),
            ("merge-base", "--is-ancestor", "abc1234", "origin/main"): (0, "", ""),
        }

        with patch.object(aet_state.subprocess, "run", side_effect=_git_mock(responses)):
            derived = aet_state.derive_status(task)

        self.assertEqual(derived["derived_status"], "merged")

    def test_drift_when_plan_file_missing(self):
        """A missing plan file is reported as drift, not as a status."""
        task = {
            "id": "t1",
            "plan_file": "/nonexistent/plan.md",
            "branch": None,
        }

        responses = {
            ("show-ref", "--verify", "--quiet", "refs/heads/None"): (1, "", ""),
        }

        with patch.object(aet_state.subprocess, "run", side_effect=_git_mock(responses)):
            derived = aet_state.derive_status(task)

        self.assertEqual(derived["derived_status"], "drift")
        self.assertEqual(derived["drift"], "plan_file missing")

    def test_done_without_merge_verification_warning(self):
        """The legacy done-without-merge warning is preserved during transition."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Plan\n")
            plan_path = f.name

        task = {
            "id": "t1",
            "plan_file": plan_path,
            "branch": None,
            "status": "done",
        }

        responses = {
            ("show-ref", "--verify", "--quiet", "refs/heads/None"): (1, "", ""),
        }

        with patch.object(aet_state.subprocess, "run", side_effect=_git_mock(responses)):
            derived = aet_state.derive_status(task)

        self.assertIn("done without merge verification", derived["warnings"][0])
        self.assertTrue(derived["derived_status"].startswith("unblocked"))


if __name__ == "__main__":
    unittest.main()
