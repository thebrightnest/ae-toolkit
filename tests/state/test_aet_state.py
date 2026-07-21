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

_AET_STATE_PY = Path(__file__).parents[2] / "src" / "aet" / "cli" / "aet_state.py"
_spec = importlib.util.spec_from_loader(
    "aet_state", importlib.machinery.SourceFileLoader("aet_state", str(_AET_STATE_PY))
)
aet_state = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(aet_state)

from aet import queue as aet_queue_module  # noqa: E402


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


class TestAuditCommand(unittest.TestCase):
    def test_derive_subcommand_removed(self):
        """The old `derive` subcommand is no longer registered."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"tasks": []}, f)
            queue_path = f.name

        with patch.object(sys, "argv", ["aet-state", "derive", queue_path]):
            rc = aet_state.main()
        self.assertEqual(rc, 2)

    def test_audit_reports_no_discrepancies_when_states_match(self):
        """audit reports empty when stored state matches derived state."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            plan_path = "docs/plans/t1.md"
            queue = {
                "tasks": [
                    {"id": "t1", "state": "planned", "plan_file": plan_path, "branch": None}
                ]
            }
            json.dump(queue, f)
            queue_path = f.name

        responses = {
            ("show-ref", "--verify", "--quiet", "refs/heads/None"): (1, "", ""),
        }

        args = aet_state.argparse.Namespace(
            command="audit",
            queue=queue_path,
            dry_run=False,
        )

        with patch.object(aet_state.subprocess, "run", side_effect=_git_mock(responses)):
            rc = aet_state.cmd_audit(args)

        self.assertEqual(rc, 0)

    def test_audit_reports_discrepancy_without_mutating(self):
        """audit reports stored-vs-git discrepancies and never mutates the queue."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            plan_path = "docs/plans/t1.md"
            queue = {
                "tasks": [
                    {"id": "t1", "state": "ready", "plan_file": plan_path, "branch": "feat-001"}
                ]
            }
            json.dump(queue, f)
            queue_path = f.name

        responses = {
            ("show-ref", "--verify", "--quiet", "refs/heads/feat-001"): (0, "", ""),
            ("merge-base", "--is-ancestor", "feat-001", "origin/main"): (1, "", ""),
        }

        args = aet_state.argparse.Namespace(
            command="audit",
            queue=queue_path,
            dry_run=False,
        )

        with patch.object(aet_state.subprocess, "run", side_effect=_git_mock(responses)):
            rc = aet_state.cmd_audit(args)

        self.assertEqual(rc, 0)

        with open(queue_path, "r", encoding="utf-8") as f:
            after = json.load(f)
        self.assertEqual(after["tasks"][0]["state"], "ready")


class TestRecordMerge(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.queue_file_path = Path(self.tmpdir.name) / "work-queue.json"
        self.history_file = str(self.queue_file_path.with_name("work-history.jsonl"))
        self.queue = {
            "tasks": [
                {
                    "id": "t1",
                    "state": "awaiting_merge",
                    "branch": "feat-001",
                    "plan_file": "docs/plans/t1.md",
                }
            ]
        }
        with open(self.queue_file_path, "w", encoding="utf-8") as f:
            json.dump(self.queue, f)

    def tearDown(self):
        self.tmpdir.cleanup()

    def _load_task(self):
        with open(self.history_file, "r", encoding="utf-8") as f:
            line = f.readline()
        return json.loads(line)

    def test_regular_merge(self):
        """A branch tip that is an ancestor of origin/main is recorded and sealed."""
        responses = {
            ("git", "fetch", "origin"): (0, "", ""),
            ("git", "rev-parse", "feat-001"): (0, "abc1234\n", ""),
            ("git", "merge-base", "--is-ancestor", "abc1234", "origin/main"): (0, "", ""),
        }

        args = aet_state.argparse.Namespace(
            command="record-merge",
            task_id="t1",
            queue=str(self.queue_file_path),
            dry_run=False,
        )

        with patch.object(aet_state.subprocess, "run", side_effect=_subprocess_mock(responses)):
            rc = aet_state.cmd_record_merge(args)

        self.assertEqual(rc, 0)
        task = self._load_task()
        self.assertEqual(task["state"], "merged")
        self.assertEqual(task["merge_commit"], "abc1234")
        self.assertEqual(task["merge_strategy"], "regular")
        self.assertIn("merged_at", task)

        with open(self.queue_file_path, "r", encoding="utf-8") as f:
            live = json.load(f)
        self.assertEqual(live["tasks"], [])

    def test_squash_merge_via_gh(self):
        """A squash merge resolved via gh pr view is recorded and sealed."""
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
            queue=str(self.queue_file_path),
            dry_run=False,
        )

        with patch.object(aet_state.subprocess, "run", side_effect=_subprocess_mock(responses)):
            rc = aet_state.cmd_record_merge(args)

        self.assertEqual(rc, 0)
        task = self._load_task()
        self.assertEqual(task["state"], "merged")
        self.assertEqual(task["merge_commit"], "squash_sha")
        self.assertEqual(task["merge_strategy"], "squash")

        with open(str(self.queue_file_path), "r", encoding="utf-8") as f:
            live = json.load(f)
        self.assertEqual(live["tasks"], [])

    def test_diff_fallback(self):
        """When gh fails, a matching diff on origin/main is used and the task is sealed."""
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
            queue=str(self.queue_file_path),
            dry_run=False,
        )

        with patch.object(aet_state.subprocess, "run", side_effect=_subprocess_mock(responses)):
            rc = aet_state.cmd_record_merge(args)

        self.assertEqual(rc, 0)
        task = self._load_task()
        self.assertEqual(task["state"], "merged")
        self.assertEqual(task["merge_commit"], "squash_sha")
        self.assertEqual(task["merge_strategy"], "squash")

        with open(str(self.queue_file_path), "r", encoding="utf-8") as f:
            live = json.load(f)
        self.assertEqual(live["tasks"], [])

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
            queue=str(self.queue_file_path),
            dry_run=False,
        )

        with patch.object(aet_state.subprocess, "run", side_effect=_subprocess_mock(responses)):
            rc = aet_state.cmd_record_merge(args)

        self.assertEqual(rc, 1)
        with open(str(self.queue_file_path), "r", encoding="utf-8") as f:
            live = json.load(f)
        task = live["tasks"][0]
        self.assertEqual(task["state"], "awaiting_merge")
        self.assertNotIn("status", task)
        self.assertNotIn("merge_commit", task)

    def test_record_merge_with_plan_updates_frontmatter_and_footer(self):
        """record-merge --plan updates plan frontmatter status and footer stage."""
        plan_dir = Path(self.tmpdir.name) / "docs" / "plans"
        plan_dir.mkdir(parents=True)
        plan_path = plan_dir / "t1.md"
        plan_path.write_text(
            "---\n"
            "id: t1\n"
            "status: awaiting_merge\n"
            "---\n\n"
            "# Plan T1\n\n"
            "---\n\n"
            "*Stage: awaiting_merge*\n",
            encoding="utf-8",
        )
        self.queue["tasks"][0]["plan_file"] = str(plan_path)
        with open(self.queue_file_path, "w", encoding="utf-8") as f:
            json.dump(self.queue, f)

        plan_abs = os.path.realpath(str(plan_path))
        plan_rel = os.path.relpath(plan_abs, os.path.realpath(self.tmpdir.name))
        responses = {
            ("git", "fetch", "origin"): (0, "", ""),
            ("git", "rev-parse", "feat-001"): (0, "abc1234\n", ""),
            ("git", "merge-base", "--is-ancestor", "abc1234", "origin/main"): (0, "", ""),
            ("git", "add", plan_rel): (0, "", ""),
            ("git", "diff", "--cached", "--quiet"): (1, "", ""),
            ("git", "commit", "-m", "chore(t1): mark plan as merged"): (0, "", ""),
            ("git", "push"): (0, "", ""),
        }

        args = aet_state.argparse.Namespace(
            command="record-merge",
            task_id="t1",
            queue=str(self.queue_file_path),
            dry_run=False,
            plan=str(plan_path),
            branch=None,
            merge_commit=None,
        )

        mock = _subprocess_mock(responses)
        with patch.object(aet_state.subprocess, "run", side_effect=mock):
            with patch.object(aet_queue_module.subprocess, "run", side_effect=mock):
                rc = aet_state.cmd_record_merge(args)

        self.assertEqual(rc, 0)
        content = plan_path.read_text(encoding="utf-8")
        self.assertIn("status: merged", content)
        self.assertIn("*Stage: merged*", content)

        # Queue task should be sealed to history.
        with open(self.queue_file_path, "r", encoding="utf-8") as f:
            live = json.load(f)
        self.assertEqual(live["tasks"], [])
        task = self._load_task()
        self.assertEqual(task["state"], "merged")

    def test_record_merge_pushes_status_commit(self):
        """record-merge pushes the status commit so closure is versioned."""
        plan_dir = Path(self.tmpdir.name) / "docs" / "plans"
        plan_dir.mkdir(parents=True)
        plan_path = plan_dir / "t1.md"
        plan_path.write_text(
            "---\n"
            "id: t1\n"
            "status: awaiting_merge\n"
            "---\n\n"
            "# Plan T1\n\n"
            "---\n\n"
            "*Stage: awaiting_merge*\n",
            encoding="utf-8",
        )
        self.queue["tasks"][0]["plan_file"] = str(plan_path)
        with open(self.queue_file_path, "w", encoding="utf-8") as f:
            json.dump(self.queue, f)

        plan_abs = os.path.realpath(str(plan_path))
        plan_rel = os.path.relpath(plan_abs, os.path.realpath(self.tmpdir.name))
        pushed = []

        responses = {
            ("git", "fetch", "origin"): (0, "", ""),
            ("git", "rev-parse", "feat-001"): (0, "abc1234\n", ""),
            ("git", "merge-base", "--is-ancestor", "abc1234", "origin/main"): (
                0,
                "",
                "",
            ),
            ("git", "add", plan_rel): (0, "", ""),
            ("git", "diff", "--cached", "--quiet"): (1, "", ""),
            ("git", "commit", "-m", "chore(t1): mark plan as merged"): (0, "", ""),
            ("git", "push"): (0, "", ""),
        }

        def tracking_mock(cmd, **kwargs):
            args = tuple(cmd)
            if args == ("git", "push"):
                pushed.append(args)
            rc, out, err = responses.get(args, (1, "", ""))
            return MockResult(rc, out, err)

        args = aet_state.argparse.Namespace(
            command="record-merge",
            task_id="t1",
            queue=str(self.queue_file_path),
            dry_run=False,
            plan=str(plan_path),
            branch=None,
            merge_commit=None,
        )

        with patch.object(aet_state.subprocess, "run", side_effect=tracking_mock):
            with patch.object(
                aet_queue_module.subprocess, "run", side_effect=tracking_mock
            ):
                rc = aet_state.cmd_record_merge(args)

        self.assertEqual(rc, 0)
        self.assertIn(("git", "push"), pushed)

    def test_push_failure_is_recoverable_and_idempotent(self):
        """A push failure leaves the local commit intact; re-run succeeds."""
        plan_dir = Path(self.tmpdir.name) / "docs" / "plans"
        plan_dir.mkdir(parents=True)
        plan_path = plan_dir / "t1.md"
        plan_path.write_text(
            "---\n"
            "id: t1\n"
            "status: awaiting_merge\n"
            "---\n\n"
            "# Plan T1\n\n"
            "---\n\n"
            "*Stage: awaiting_merge*\n",
            encoding="utf-8",
        )
        self.queue["tasks"][0]["plan_file"] = str(plan_path)
        with open(self.queue_file_path, "w", encoding="utf-8") as f:
            json.dump(self.queue, f)

        plan_abs = os.path.realpath(str(plan_path))
        plan_rel = os.path.relpath(plan_abs, os.path.realpath(self.tmpdir.name))
        responses = {
            ("git", "fetch", "origin"): (0, "", ""),
            ("git", "rev-parse", "feat-001"): (0, "abc1234\n", ""),
            ("git", "merge-base", "--is-ancestor", "abc1234", "origin/main"): (
                0,
                "",
                "",
            ),
            ("git", "add", plan_rel): (0, "", ""),
            ("git", "diff", "--cached", "--quiet"): (1, "", ""),
            ("git", "commit", "-m", "chore(t1): mark plan as merged"): (0, "", ""),
            ("git", "push"): (1, "", "network unreachable"),
        }

        args = aet_state.argparse.Namespace(
            command="record-merge",
            task_id="t1",
            queue=str(self.queue_file_path),
            dry_run=False,
            plan=str(plan_path),
            branch=None,
            merge_commit=None,
        )

        mock = _subprocess_mock(responses)
        with patch.object(aet_state.subprocess, "run", side_effect=mock):
            with patch.object(aet_queue_module.subprocess, "run", side_effect=mock):
                rc = aet_state.cmd_record_merge(args)

        # Push failure is reported as non-zero but the local commit is intact.
        self.assertNotEqual(rc, 0)
        content = plan_path.read_text(encoding="utf-8")
        self.assertIn("status: merged", content)
        self.assertIn("*Stage: merged*", content)

        # Simulate re-run with connectivity restored. The status update is
        # idempotent (no diff), so only the push is attempted and succeeds.
        responses[("git", "push")] = (0, "", "")
        responses[("git", "diff", "--cached", "--quiet")] = (0, "", "")
        with patch.object(aet_state.subprocess, "run", side_effect=mock):
            with patch.object(aet_queue_module.subprocess, "run", side_effect=mock):
                rc = aet_state.cmd_record_merge(args)
        self.assertEqual(rc, 0)

    def test_record_merge_with_plan_dry_run_does_not_mutate_plan(self):
        """record-merge --plan --dry-run reports without updating the plan."""
        plan_dir = Path(self.tmpdir.name) / "docs" / "plans"
        plan_dir.mkdir(parents=True)
        plan_path = plan_dir / "t1.md"
        original_content = (
            "---\n"
            "id: t1\n"
            "status: awaiting_merge\n"
            "---\n\n"
            "# Plan T1\n\n"
            "---\n\n"
            "*Stage: awaiting_merge*\n"
        )
        plan_path.write_text(original_content, encoding="utf-8")
        self.queue["tasks"][0]["plan_file"] = str(plan_path)
        with open(self.queue_file_path, "w", encoding="utf-8") as f:
            json.dump(self.queue, f)

        responses = {
            ("git", "fetch", "origin"): (0, "", ""),
            ("git", "rev-parse", "feat-001"): (0, "abc1234\n", ""),
            ("git", "merge-base", "--is-ancestor", "abc1234", "origin/main"): (0, "", ""),
        }

        args = aet_state.argparse.Namespace(
            command="record-merge",
            task_id="t1",
            queue=str(self.queue_file_path),
            dry_run=True,
            plan=str(plan_path),
        )

        with patch.object(aet_state.subprocess, "run", side_effect=_subprocess_mock(responses)):
            rc = aet_state.cmd_record_merge(args)

        self.assertEqual(rc, 0)
        self.assertEqual(plan_path.read_text(encoding="utf-8"), original_content)
        with open(self.queue_file_path, "r", encoding="utf-8") as f:
            live = json.load(f)
        self.assertEqual(len(live["tasks"]), 1)

    def test_record_merge_plan_update_skipped_when_merge_unverified(self):
        """If merge verification fails, the plan file is not updated."""
        plan_dir = Path(self.tmpdir.name) / "docs" / "plans"
        plan_dir.mkdir(parents=True)
        plan_path = plan_dir / "t1.md"
        original_content = (
            "---\n"
            "id: t1\n"
            "status: awaiting_merge\n"
            "---\n\n"
            "# Plan T1\n\n"
            "---\n\n"
            "*Stage: awaiting_merge*\n"
        )
        plan_path.write_text(original_content, encoding="utf-8")
        self.queue["tasks"][0]["plan_file"] = str(plan_path)
        with open(self.queue_file_path, "w", encoding="utf-8") as f:
            json.dump(self.queue, f)

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
            queue=str(self.queue_file_path),
            dry_run=False,
            plan=str(plan_path),
        )

        with patch.object(aet_state.subprocess, "run", side_effect=_subprocess_mock(responses)):
            rc = aet_state.cmd_record_merge(args)

        self.assertEqual(rc, 1)
        self.assertEqual(plan_path.read_text(encoding="utf-8"), original_content)


class TestDeriveStatus(unittest.TestCase):
    def test_unblocked_when_blockers_terminal(self):
        """A task with no branch and all blockers merged/abandoned is ready."""
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

        self.assertEqual(derived["derived_status"], "ready")

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
        """An abandoned blocker is terminal, so the dependent is ready."""
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

        self.assertEqual(derived["derived_status"], "ready")

    def test_in_progress_when_branch_exists(self):
        """A local branch takes precedence over blocker-aware states."""
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

        self.assertEqual(derived["derived_status"], "in_progress")

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

    def test_awaiting_merge_without_merge_verification_warning(self):
        """An awaiting_merge task without merge verification is flagged."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Plan\n")
            plan_path = f.name

        task = {
            "id": "t1",
            "plan_file": plan_path,
            "branch": None,
            "state": "awaiting_merge",
        }

        responses = {
            ("show-ref", "--verify", "--quiet", "refs/heads/None"): (1, "", ""),
        }

        with patch.object(aet_state.subprocess, "run", side_effect=_git_mock(responses)):
            derived = aet_state.derive_status(task)

        self.assertIn("awaiting_merge without merge verification", derived["warnings"][0])
        self.assertTrue(derived["derived_status"].startswith("ready"))


class TestSetStage(unittest.TestCase):
    """Tests for the set-stage in_progress sub-state command (fods-04)."""

    def _write_queue(self, tasks):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump({"tasks": tasks}, f)
        f.close()
        return f.name

    def _load_task(self, queue_path):
        with open(queue_path, "r", encoding="utf-8") as f:
            return json.load(f)["tasks"][0]

    def test_set_stage_appends_history_and_requires_in_progress(self):
        """set-stage writes stage + history only when state is in_progress."""
        queue_path = self._write_queue(
            [{"id": "t1", "state": "in_progress", "stage": "plan-approved"}]
        )

        args = aet_state.argparse.Namespace(
            command="set-stage",
            task_id="t1",
            stage="implemented",
            queue=queue_path,
            dry_run=False,
        )

        rc = aet_state.cmd_set_stage(args)

        self.assertEqual(rc, 0)
        task = self._load_task(queue_path)
        self.assertEqual(task["stage"], "implemented")
        self.assertEqual(len(task["history"]), 1)
        self.assertEqual(task["history"][0]["from"], "plan-approved")
        self.assertEqual(task["history"][0]["to"], "implemented")
        self.assertEqual(task["history"][0]["by"], "orch")

    def test_set_stage_rejects_non_in_progress_state(self):
        """set-stage is only legal while the task is in_progress."""
        queue_path = self._write_queue([{"id": "t1", "state": "planned"}])

        args = aet_state.argparse.Namespace(
            command="set-stage",
            task_id="t1",
            stage="implemented",
            queue=queue_path,
            dry_run=False,
        )

        rc = aet_state.cmd_set_stage(args)

        self.assertEqual(rc, 1)
        task = self._load_task(queue_path)
        self.assertNotIn("stage", task)
        self.assertNotIn("history", task)

    def test_set_stage_dry_run_does_not_mutate(self):
        """dry-run reports the stage without writing it."""
        queue_path = self._write_queue(
            [{"id": "t1", "state": "in_progress", "stage": "plan-approved"}]
        )

        args = aet_state.argparse.Namespace(
            command="set-stage",
            task_id="t1",
            stage="implemented",
            queue=queue_path,
            dry_run=True,
        )

        rc = aet_state.cmd_set_stage(args)

        self.assertEqual(rc, 0)
        task = self._load_task(queue_path)
        self.assertEqual(task["stage"], "plan-approved")
        self.assertNotIn("history", task)


class TestStateTransition(unittest.TestCase):
    """Tests for the forward-only recorded state lifecycle (fods-02)."""

    def test_apply_transition_writes_no_status_key(self):
        """_apply_transition mutates state but never writes a legacy status key."""
        with tempfile.TemporaryDirectory() as tmpdir:
            queue_path = Path(tmpdir) / "work-queue.json"
            history_file = queue_path.with_name("work-history.jsonl")
            queue = [{"id": "t1", "state": "planned"}]
            queue_path.write_text(json.dumps({"tasks": queue}), encoding="utf-8")

            backend = aet_state.make_backend(str(queue_path))
            task = queue[0]
            aet_state._apply_transition(
                backend, queue, task, "planned", "ready",
                by="test", history_file=str(history_file),
            )

            self.assertEqual(task["state"], "ready")
            self.assertNotIn("status", task)

    def test_sync_footers_command_removed(self):
        """The deprecated sync-footers subcommand is no longer registered."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"tasks": []}, f)
            queue_path = f.name

        with patch.object(sys, "argv", ["aet-state", "sync-footers", "docs/plans/t1.md", "implemented", queue_path]):
            rc = aet_state.main()
        self.assertEqual(rc, 2)

    def test_audit_and_heal_speak_canonical_states(self):
        """audit and heal compare stored state against canonical derived states."""
        import io

        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "plans" / "t1.md"
            plan_path.parent.mkdir(parents=True)
            plan_path.write_text("# Plan\n")
            queue_path = Path(tmpdir) / "work-queue.json"
            queue = {
                "tasks": [
                    {
                        "id": "t1",
                        "state": "planned",
                        "plan_file": str(plan_path),
                        "branch": None,
                    }
                ]
            }
            queue_path.write_text(json.dumps(queue), encoding="utf-8")

            responses = {
                ("show-ref", "--verify", "--quiet", "refs/heads/None"): (1, "", ""),
            }

            args = aet_state.argparse.Namespace(
                command="audit",
                queue=str(queue_path),
                dry_run=False,
            )

            stdout_capture = io.StringIO()
            with patch.object(aet_state.subprocess, "run", side_effect=_git_mock(responses)):
                with patch.object(sys, "stdout", stdout_capture):
                    rc = aet_state.cmd_audit(args)

            self.assertEqual(rc, 0)
            results = json.loads(stdout_capture.getvalue())
            self.assertEqual(results["t1"]["derived"], "ready")
            self.assertTrue(results["t1"]["discrepancy"])

    def test_legal_transition_matrix(self):
        """Every legal lifecycle transition is accepted by validate_transition."""
        ancestry_responses = {
            ("git", "merge-base", "--is-ancestor", "feat-001", "origin/main"): (0, "", ""),
        }

        for from_state, targets in aet_state.queue_lib.LEGAL_TRANSITIONS.items():
            for to_state in targets:
                # Pre-intake has neither state nor status; otherwise use state.
                if from_state is None:
                    task = {"id": "t", "branch": "feat-001"}
                else:
                    task = {"id": "t", "state": from_state, "branch": "feat-001"}
                with patch.object(
                    aet_state.subprocess, "run", side_effect=_subprocess_mock(ancestry_responses)
                ):
                    ok, msg = aet_state.validate_transition(task, from_state, to_state)
                self.assertTrue(ok, f"{from_state} -> {to_state}: {msg}")

    def test_illegal_transition_rejected_no_mutation(self):
        """An illegal transition is rejected and the queue file is not mutated."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            queue = {"tasks": [{"id": "t1", "state": "planned"}]}
            json.dump(queue, f)
            queue_path = f.name

        args = aet_state.argparse.Namespace(
            command="transition",
            task_id="t1",
            from_stage="planned",
            to_stage="merged",
            queue=queue_path,
            dry_run=False,
            reason=None,
        )

        rc = aet_state.cmd_transition(args)
        self.assertEqual(rc, 1)

        with open(queue_path, "r", encoding="utf-8") as f:
            after = json.load(f)
        self.assertEqual(after["tasks"][0].get("state"), "planned")
        self.assertNotIn("history", after["tasks"][0])

    def test_history_entry_shape(self):
        """A transition appends a history entry with the required shape."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            queue = {"tasks": [{"id": "t1", "state": "planned"}]}
            json.dump(queue, f)
            queue_path = f.name

        args = aet_state.argparse.Namespace(
            command="transition",
            task_id="t1",
            from_stage="planned",
            to_stage="ready",
            queue=queue_path,
            dry_run=False,
            reason=None,
        )

        rc = aet_state.cmd_transition(args)
        self.assertEqual(rc, 0)

        with open(queue_path, "r", encoding="utf-8") as f:
            after = json.load(f)
        task = after["tasks"][0]
        self.assertEqual(task["state"], "ready")
        self.assertEqual(len(task["history"]), 1)
        entry = task["history"][0]
        self.assertEqual(entry["from"], "planned")
        self.assertEqual(entry["to"], "ready")
        self.assertEqual(entry["by"], "transition")
        self.assertIn("at", entry)

    def test_terminal_transition_promotes_dependent(self):
        """A terminal transition promotes dependents, then seals the terminal task."""
        with tempfile.TemporaryDirectory() as tmpdir:
            queue_path = Path(tmpdir) / "work-queue.json"
            history_file = queue_path.with_name("work-history.jsonl")
            queue = {
                "tasks": [
                    {
                        "id": "blocker",
                        "state": "awaiting_merge",
                        "blocks": ["dependent"],
                    },
                    {
                        "id": "dependent",
                        "state": "blocked",
                        "blocked_by": ["blocker"],
                        "pending_blockers": 1,
                    },
                ]
            }
            with open(queue_path, "w", encoding="utf-8") as f:
                json.dump(queue, f)

            args = aet_state.argparse.Namespace(
                command="transition",
                task_id="blocker",
                from_stage="awaiting_merge",
                to_stage="abandoned",
                queue=str(queue_path),
                dry_run=False,
                reason="no longer needed",
            )

            rc = aet_state.cmd_transition(args)
            self.assertEqual(rc, 0)

            with open(queue_path, "r", encoding="utf-8") as f:
                after = json.load(f)
            by_id = {t["id"]: t for t in after["tasks"]}
            self.assertNotIn("blocker", by_id)
            self.assertEqual(by_id["dependent"]["state"], "ready")
            self.assertEqual(by_id["dependent"]["pending_blockers"], 0)
            release_entries = [h for h in by_id["dependent"]["history"] if h["by"] == "release"]
            self.assertEqual(len(release_entries), 1)
            self.assertEqual(release_entries[0]["from"], "blocked")
            self.assertEqual(release_entries[0]["to"], "ready")

            with open(history_file, "r", encoding="utf-8") as f:
                settled = json.loads(f.readline())
            self.assertEqual(settled["id"], "blocker")
            self.assertEqual(settled["state"], "abandoned")

    def test_record_merge_drives_merged_and_promotes(self):
        """record-merge reaches merged, seals the task, and unblocks dependents."""
        with tempfile.TemporaryDirectory() as tmpdir:
            queue_path = Path(tmpdir) / "work-queue.json"
            history_file = queue_path.with_name("work-history.jsonl")
            queue = {
                "tasks": [
                    {
                        "id": "blocker",
                        "state": "awaiting_merge",
                        "branch": "feat-blocker",
                        "blocks": ["dependent"],
                    },
                    {
                        "id": "dependent",
                        "state": "blocked",
                        "blocked_by": ["blocker"],
                        "pending_blockers": 1,
                    },
                ]
            }
            with open(queue_path, "w", encoding="utf-8") as f:
                json.dump(queue, f)

            responses = {
                ("git", "fetch", "origin"): (0, "", ""),
                ("git", "rev-parse", "feat-blocker"): (0, "abc1234\n", ""),
                ("git", "merge-base", "--is-ancestor", "abc1234", "origin/main"): (0, "", ""),
            }

            args = aet_state.argparse.Namespace(
                command="record-merge",
                task_id="blocker",
                queue=str(queue_path),
                dry_run=False,
            )

            with patch.object(aet_state.subprocess, "run", side_effect=_subprocess_mock(responses)):
                rc = aet_state.cmd_record_merge(args)

            self.assertEqual(rc, 0)
            with open(queue_path, "r", encoding="utf-8") as f:
                after = json.load(f)
            by_id = {t["id"]: t for t in after["tasks"]}
            self.assertNotIn("blocker", by_id)
            self.assertEqual(by_id["dependent"]["state"], "ready")
            self.assertEqual(by_id["dependent"]["pending_blockers"], 0)

            with open(history_file, "r", encoding="utf-8") as f:
                settled = json.loads(f.readline())
            self.assertEqual(settled["id"], "blocker")
            self.assertEqual(settled["state"], "merged")
            self.assertEqual(settled["merge_commit"], "abc1234")
            merge_entries = [h for h in settled["history"] if h["by"] == "record-merge"]
            self.assertEqual(len(merge_entries), 1)
            self.assertEqual(merge_entries[0]["to"], "merged")

    def test_frontier_promotes_planned_dependent_on_merge(self):
        """record-merge promotes a dependent still at ``planned`` (frh-16).

        Dependents curated before frh-15 sit at ``planned`` rather than
        ``blocked``. Once their last blocker merges, the forward frontier must
        still promote them to ``ready`` and record the actual from-state in the
        release history entry.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            queue_path = Path(tmpdir) / "work-queue.json"
            queue = {
                "tasks": [
                    {
                        "id": "blocker",
                        "state": "awaiting_merge",
                        "branch": "feat-blocker",
                        "blocks": ["dependent"],
                    },
                    {
                        "id": "dependent",
                        "state": "planned",
                        "blocked_by": ["blocker"],
                        "pending_blockers": 1,
                    },
                ]
            }
            with open(queue_path, "w", encoding="utf-8") as f:
                json.dump(queue, f)

            responses = {
                ("git", "fetch", "origin"): (0, "", ""),
                ("git", "rev-parse", "feat-blocker"): (0, "abc1234\n", ""),
                ("git", "merge-base", "--is-ancestor", "abc1234", "origin/main"): (0, "", ""),
            }

            args = aet_state.argparse.Namespace(
                command="record-merge",
                task_id="blocker",
                queue=str(queue_path),
                dry_run=False,
            )

            with patch.object(
                aet_state.subprocess, "run", side_effect=_subprocess_mock(responses)
            ):
                rc = aet_state.cmd_record_merge(args)

            self.assertEqual(rc, 0)
            with open(queue_path, "r", encoding="utf-8") as f:
                after = json.load(f)
            by_id = {t["id"]: t for t in after["tasks"]}
            self.assertNotIn("blocker", by_id)
            self.assertEqual(by_id["dependent"]["state"], "ready")
            self.assertEqual(by_id["dependent"]["pending_blockers"], 0)
            release_entries = [
                h for h in by_id["dependent"]["history"] if h["by"] == "release"
            ]
            self.assertEqual(len(release_entries), 1)
            self.assertEqual(release_entries[0]["from"], "planned")
            self.assertEqual(release_entries[0]["to"], "ready")


class TestHealHistoryAware(unittest.TestCase):
    """heal reconciles tasks whose blockers already settled to history."""

    def _write_queue_and_history(self, tmpdir, tasks, settled):
        tmp = Path(tmpdir)
        plans_dir = tmp / "plans"
        plans_dir.mkdir()
        for task in tasks:
            plan = plans_dir / f"{task['id']}.md"
            plan.write_text("# Plan\n", encoding="utf-8")
            task.setdefault("plan_file", str(plan))
            task.setdefault("branch", None)
        queue_path = tmp / "work-queue.json"
        queue_path.write_text(json.dumps({"tasks": tasks}), encoding="utf-8")
        history_path = tmp / "work-history.jsonl"
        with open(history_path, "w", encoding="utf-8") as f:
            for record in settled:
                f.write(json.dumps(record) + "\n")
        return queue_path

    def _run_heal(self, queue_path, apply):
        args = aet_state.argparse.Namespace(
            command="heal",
            queue=str(queue_path),
            apply=apply,
            force=False,
        )
        with patch.object(aet_state.subprocess, "run", side_effect=_git_mock({})):
            return aet_state.cmd_heal(args)

    def test_heal_promotes_task_blocked_on_settled_history(self):
        """A task blocked on an already-archived blocker heals to ready with pb=0.

        Regression: a task added after its blocker merged stored a stale
        pending_blockers count and could never be promoted, and heal used to
        report "No healable discrepancies found" because archived blockers
        derived as unknown rather than terminal.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            queue_path = self._write_queue_and_history(
                tmpdir,
                [{
                    "id": "t2",
                    "state": "blocked",
                    "blocked_by": ["t1"],
                    "pending_blockers": 1,
                }],
                [{"id": "t1", "state": "merged"}],
            )

            self.assertEqual(self._run_heal(queue_path, apply=True), 0)

            with open(queue_path, "r", encoding="utf-8") as f:
                after = json.load(f)
            task = after["tasks"][0]
            self.assertEqual(task["state"], "ready")
            self.assertEqual(task["pending_blockers"], 0)

    def test_heal_recounts_pending_blockers_for_live_and_settled(self):
        """A still-blocked task's stale counter is reconciled without a transition."""
        with tempfile.TemporaryDirectory() as tmpdir:
            queue_path = self._write_queue_and_history(
                tmpdir,
                [
                    {"id": "t3", "state": "ready"},
                    {
                        "id": "t4",
                        "state": "blocked",
                        "blocked_by": ["t1", "t3"],
                        "pending_blockers": 2,
                    },
                ],
                [{"id": "t1", "state": "merged"}],
            )

            self.assertEqual(self._run_heal(queue_path, apply=True), 0)

            with open(queue_path, "r", encoding="utf-8") as f:
                after = json.load(f)
            by_id = {t["id"]: t for t in after["tasks"]}
            self.assertEqual(by_id["t4"]["state"], "blocked")
            self.assertEqual(by_id["t4"]["pending_blockers"], 1)

    def test_heal_dry_run_reports_without_mutating(self):
        """Without --apply, heal reports the recount but leaves the queue untouched."""
        import io

        with tempfile.TemporaryDirectory() as tmpdir:
            queue_path = self._write_queue_and_history(
                tmpdir,
                [{
                    "id": "t2",
                    "state": "blocked",
                    "blocked_by": ["t1"],
                    "pending_blockers": 1,
                }],
                [{"id": "t1", "state": "merged"}],
            )

            stdout_capture = io.StringIO()
            with patch.object(sys, "stdout", stdout_capture):
                self.assertEqual(self._run_heal(queue_path, apply=False), 0)

            output = stdout_capture.getvalue()
            self.assertIn("t2", output)
            self.assertIn("pending_blockers -> 0", output)

            with open(queue_path, "r", encoding="utf-8") as f:
                after = json.load(f)
            task = after["tasks"][0]
            self.assertEqual(task["state"], "blocked")
            self.assertEqual(task["pending_blockers"], 1)


if __name__ == "__main__":
    unittest.main()
