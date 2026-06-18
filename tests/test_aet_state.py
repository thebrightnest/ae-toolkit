"""Tests for aet-state derive_status."""

import importlib.machinery
import importlib.util
import json
import os
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


def _subprocess_mock(responses):
    """Return a mock subprocess.run that answers git and gh commands.

    responses maps tuple(program, *args) -> (returncode, stdout, stderr).
    """

    def mock_run(cmd, **kwargs):
        args = tuple(cmd)
        rc, out, err = responses.get(args, (1, "", ""))
        return MockResult(rc, out, err)

    return mock_run


class TestRecordMerge(unittest.TestCase):
    def setUp(self):
        self.queue_file = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        self.queue = {
            "tasks": [
                {
                    "id": "t1",
                    "status": "awaiting_merge",
                    "branch": "feat-001",
                    "plan_file": "docs/plans/t1.md",
                }
            ]
        }
        json.dump(self.queue, self.queue_file)
        self.queue_file.close()

    def tearDown(self):
        os.unlink(self.queue_file.name)

    def _load_task(self):
        with open(self.queue_file.name, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data["tasks"][0]

    def test_regular_merge(self):
        """A branch tip that is an ancestor of origin/main is recorded as regular."""
        responses = {
            ("git", "fetch", "origin"): (0, "", ""),
            ("git", "rev-parse", "feat-001"): (0, "abc1234\n", ""),
            ("git", "merge-base", "--is-ancestor", "abc1234", "origin/main"): (0, "", ""),
        }

        args = aet_state.argparse.Namespace(
            command="record-merge",
            task_id="t1",
            queue=self.queue_file.name,
            dry_run=False,
        )

        with patch.object(aet_state.subprocess, "run", side_effect=_subprocess_mock(responses)):
            rc = aet_state.cmd_record_merge(args)

        self.assertEqual(rc, 0)
        task = self._load_task()
        self.assertEqual(task["status"], "merged")
        self.assertEqual(task["merge_commit"], "abc1234")
        self.assertEqual(task["merge_strategy"], "regular")
        self.assertIn("merged_at", task)

    def test_squash_merge_via_gh(self):
        """A squash merge resolved via gh pr view is recorded."""
        responses = {
            ("git", "fetch", "origin"): (0, "", ""),
            ("git", "rev-parse", "feat-001"): (0, "branch_tip\n", ""),
            ("git", "merge-base", "--is-ancestor", "branch_tip", "origin/main"): (1, "", ""),
            ("gh", "pr", "view", "feat-001", "--json", "mergeCommit"): (
                0,
                '{"mergeCommit":{"oid":"squash_sha"}}',
                "",
            ),
            ("git", "merge-base", "--is-ancestor", "squash_sha", "origin/main"): (0, "", ""),
        }

        args = aet_state.argparse.Namespace(
            command="record-merge",
            task_id="t1",
            queue=self.queue_file.name,
            dry_run=False,
        )

        with patch.object(aet_state.subprocess, "run", side_effect=_subprocess_mock(responses)):
            rc = aet_state.cmd_record_merge(args)

        self.assertEqual(rc, 0)
        task = self._load_task()
        self.assertEqual(task["status"], "merged")
        self.assertEqual(task["merge_commit"], "squash_sha")
        self.assertEqual(task["merge_strategy"], "squash")

    def test_diff_fallback(self):
        """When gh fails, a matching diff on origin/main is used."""
        responses = {
            ("git", "fetch", "origin"): (0, "", ""),
            ("git", "rev-parse", "feat-001"): (0, "branch_tip\n", ""),
            ("git", "merge-base", "--is-ancestor", "branch_tip", "origin/main"): (1, "", ""),
            ("gh", "pr", "view", "feat-001", "--json", "mergeCommit"): (1, "", "gh failed"),
            ("git", "merge-base", "feat-001", "origin/main"): (0, "merge_base\n", ""),
            ("git", "diff", "merge_base..feat-001"): (0, "branch diff\n", ""),
            ("git", "rev-list", "--max-count", "20", "origin/main"): (
                0,
                "squash_sha\nother_sha\n",
                "",
            ),
            ("git", "diff", "squash_sha^..squash_sha"): (0, "branch diff\n", ""),
            ("git", "diff", "other_sha^..other_sha"): (0, "other diff\n", ""),
            ("git", "merge-base", "--is-ancestor", "squash_sha", "origin/main"): (0, "", ""),
        }

        args = aet_state.argparse.Namespace(
            command="record-merge",
            task_id="t1",
            queue=self.queue_file.name,
            dry_run=False,
        )

        with patch.object(aet_state.subprocess, "run", side_effect=_subprocess_mock(responses)):
            rc = aet_state.cmd_record_merge(args)

        self.assertEqual(rc, 0)
        task = self._load_task()
        self.assertEqual(task["status"], "merged")
        self.assertEqual(task["merge_commit"], "squash_sha")
        self.assertEqual(task["merge_strategy"], "squash")

    def test_unresolved_leaves_queue_unchanged(self):
        """If no merge commit can be resolved, the command fails without mutating the queue."""
        responses = {
            ("git", "fetch", "origin"): (0, "", ""),
            ("git", "rev-parse", "feat-001"): (0, "branch_tip\n", ""),
            ("git", "merge-base", "--is-ancestor", "branch_tip", "origin/main"): (1, "", ""),
            ("gh", "pr", "view", "feat-001", "--json", "mergeCommit"): (1, "", "gh failed"),
            ("git", "merge-base", "feat-001", "origin/main"): (0, "merge_base\n", ""),
            ("git", "diff", "merge_base..feat-001"): (0, "branch diff\n", ""),
            ("git", "rev-list", "--max-count", "20", "origin/main"): (0, "other_sha\n", ""),
            ("git", "diff", "other_sha^..other_sha"): (0, "other diff\n", ""),
        }

        args = aet_state.argparse.Namespace(
            command="record-merge",
            task_id="t1",
            queue=self.queue_file.name,
            dry_run=False,
        )

        with patch.object(aet_state.subprocess, "run", side_effect=_subprocess_mock(responses)):
            rc = aet_state.cmd_record_merge(args)

        self.assertEqual(rc, 1)
        task = self._load_task()
        self.assertEqual(task["status"], "awaiting_merge")
        self.assertNotIn("merge_commit", task)


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
