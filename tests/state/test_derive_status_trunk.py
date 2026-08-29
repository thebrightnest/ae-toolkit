"""Tests for derive_status against a non-main trunk."""

import importlib.machinery
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_AET_STATE_PY = Path(__file__).parents[2] / "src" / "aet" / "cli" / "aet_state.py"
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


class TestDeriveStatusNonMainTrunk(unittest.TestCase):
    def test_merged_when_branch_on_non_main_trunk(self):
        """A branch merged to a non-main trunk derives as merged."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Plan\n")
            plan_path = f.name

        task = {
            "id": "t1",
            "plan_file": plan_path,
            "branch": "feat-001",
            "base_commit": "base0000",
        }

        responses = {
            ("show-ref", "--verify", "--quiet", "refs/heads/feat-001"): (0, "", ""),
            ("rev-parse", "feat-001"): (0, "abc1234\n", ""),
            ("rev-parse", "base0000"): (0, "base0000\n", ""),
            ("merge-base", "--is-ancestor", "feat-001", "origin/dev"): (0, "", ""),
        }

        with patch.object(aet_state.subprocess, "run", side_effect=_git_mock(responses)):
            derived = aet_state.derive_status(task, trunk_branch="dev")

        self.assertEqual(derived["derived_status"], "merged")
        self.assertTrue(derived["on_trunk"])

    def test_dependent_unblocks_when_blocker_merged_to_non_main_trunk(self):
        """A dependent becomes ready when its blocker is merged to a non-main trunk."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Plan\n")
            plan_path = f.name

        def blocker_status(task_id):
            return "merged" if task_id == "blocker" else "unknown"

        task = {
            "id": "dependent",
            "plan_file": plan_path,
            "branch": None,
            "blocked_by": ["blocker"],
        }

        responses = {
            ("show-ref", "--verify", "--quiet", "refs/heads/None"): (1, "", ""),
        }

        with patch.object(aet_state.subprocess, "run", side_effect=_git_mock(responses)):
            derived = aet_state.derive_status(task, blocker_status, trunk_branch="dev")

        self.assertEqual(derived["derived_status"], "ready")

    def test_not_merged_when_branch_only_on_main_but_trunk_is_dev(self):
        """A branch on origin/main does not count as merged when trunk is dev."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Plan\n")
            plan_path = f.name

        task = {
            "id": "t1",
            "plan_file": plan_path,
            "branch": "feat-001",
            "base_commit": "base0000",
        }

        responses = {
            ("show-ref", "--verify", "--quiet", "refs/heads/feat-001"): (0, "", ""),
            ("rev-parse", "feat-001"): (0, "abc1234\n", ""),
            ("rev-parse", "base0000"): (0, "base0000\n", ""),
            # Ancestor of origin/main but not origin/dev.
            ("merge-base", "--is-ancestor", "feat-001", "origin/dev"): (1, "", ""),
        }

        with patch.object(aet_state.subprocess, "run", side_effect=_git_mock(responses)):
            derived = aet_state.derive_status(task, trunk_branch="dev")

        self.assertEqual(derived["derived_status"], "in_progress")
        self.assertFalse(derived["on_trunk"])


class TestValidateTransitionNonMainTrunk(unittest.TestCase):
    def test_transition_to_merged_allowed_on_non_main_trunk(self):
        """A merged transition is legal when the branch is on the configured trunk."""
        task = {
            "id": "t1",
            "state": "awaiting_merge",
            "branch": "feat-001",
            "base_commit": "base0000",
        }

        responses = {
            ("rev-parse", "feat-001"): (0, "abc1234\n", ""),
            ("rev-parse", "base0000"): (0, "base0000\n", ""),
            ("merge-base", "--is-ancestor", "feat-001", "origin/dev"): (0, "", ""),
        }

        with patch.object(aet_state.subprocess, "run", side_effect=_git_mock(responses)):
            ok, msg = aet_state.validate_transition(
                task, "awaiting_merge", "merged", trunk_branch="dev"
            )

        self.assertTrue(ok, msg)

    def test_transition_to_merged_rejected_when_not_on_non_main_trunk(self):
        """A merged transition is illegal when the branch is not on the configured trunk."""
        task = {
            "id": "t1",
            "state": "awaiting_merge",
            "branch": "feat-001",
            "base_commit": "base0000",
        }

        responses = {
            ("merge-base", "--is-ancestor", "feat-001", "origin/dev"): (1, "", ""),
        }

        with patch.object(aet_state.subprocess, "run", side_effect=_git_mock(responses)):
            ok, msg = aet_state.validate_transition(
                task, "awaiting_merge", "merged", trunk_branch="dev"
            )

        self.assertFalse(ok)
        self.assertIn("origin/dev", msg)


if __name__ == "__main__":
    unittest.main()
