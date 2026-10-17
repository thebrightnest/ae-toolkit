"""Tests for the aet-ship direct merge command (`aet ship merge`)."""

from __future__ import annotations

import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from typer.testing import CliRunner

from aet import integration_lock, plan_parser, validation
from aet.backends import create_backend
from aet.backends.git_refs_backend import GitRefsBackend
from aet.cli import ship
from aet.integrate import IntegrateResult


class TestShipMergeParser(unittest.TestCase):
    """Argument parsing for the merge subcommand."""

    def test_merge_subcommand_defaults_branch_to_none(self):
        """aet ship merge defaults --branch to None for runtime trunk resolution."""
        with patch.object(ship, "cmd_merge", return_value=0) as mock_cmd:
            runner = CliRunner()
            result = runner.invoke(ship.app, ["merge", "t1"])
            self.assertEqual(result.exit_code, 0)
            mock_cmd.assert_called_once()
            args = mock_cmd.call_args[0][0]
            self.assertEqual(args.plan, "t1")
            self.assertIsNone(args.branch)

    def test_merge_subcommand_parses_branch(self):
        """aet ship merge accepts an explicit --branch."""
        with patch.object(ship, "cmd_merge", return_value=0) as mock_cmd:
            runner = CliRunner()
            result = runner.invoke(ship.app, ["merge", "t1", "--branch", "dev"])
            self.assertEqual(result.exit_code, 0)
            mock_cmd.assert_called_once()
            args = mock_cmd.call_args[0][0]
            self.assertEqual(args.plan, "t1")
            self.assertEqual(args.branch, "dev")


class TestShipMergeConflictHandling(unittest.TestCase):
    """Conflict and refusal handling in `cmd_merge`."""

    def test_cmd_merge_handles_staged_conflict(self):
        """cmd_merge reports failure when integrate returns staged_conflict."""
        args = SimpleNamespace(plan="t1", branch="dev", task_id="t1", spec={"tasks": []})
        staged_res = IntegrateResult("staged_conflict", detail={"stderr_tail": "rebase conflict in src/cli.py"})
        with patch.object(ship, "_resolve_ship_task", return_value=None), \
             patch.object(ship, "_resolve_feature_branch", return_value="t1"), \
             patch.object(ship, "_find_target_worktree", return_value=Path("/fake/worktree")), \
             patch.object(ship, "integrate", return_value=staged_res), \
             patch("sys.stderr", new=io.StringIO()) as fake_err:
            rc = ship.cmd_merge(args)
        self.assertEqual(rc, 1)
        self.assertIn("src/cli.py", fake_err.getvalue())

    def test_cmd_merge_handles_guard_refused(self):
        """cmd_merge reports failure when integrate returns guard_refused."""
        args = SimpleNamespace(plan="t1", branch="dev", task_id="t1", spec={"tasks": []})
        refused_res = IntegrateResult("guard_refused", detail="Release guard refused")
        with patch.object(ship, "_resolve_ship_task", return_value=None), \
             patch.object(ship, "_resolve_feature_branch", return_value="t1"), \
             patch.object(ship, "_find_target_worktree", return_value=Path("/fake/worktree")), \
             patch.object(ship, "integrate", return_value=refused_res), \
             patch("sys.stderr", new=io.StringIO()) as fake_err:
            rc = ship.cmd_merge(args)
        self.assertEqual(rc, 1)
        self.assertIn("Release guard refused", fake_err.getvalue())


class TestShipMergeCommand(unittest.TestCase):
    """Behavior-driven tests for `cmd_merge`."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        base = Path(self.tmpdir.name)

        self.repo = base / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "-C", str(self.repo), "init", "-q"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "config", "user.email", "test@example.com"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "config", "user.name", "Test User"], check=True)
        (self.repo / ".agents").mkdir(parents=True, exist_ok=True)
        (self.repo / "README.md").write_text("hello\n", encoding="utf-8")
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
            "- [x] task one\n\n"
            "---\n\n"
            "*Stage: implemented*\n"
        )
        self.plan_path.write_text(self._default_content, encoding="utf-8")
        self._save_task(self._spec())

        self.cwd = os.getcwd()
        self.addCleanup(os.chdir, self.cwd)
        os.chdir(self.repo)

    def _spec(self, content: str | None = None) -> dict:
        text = content if content is not None else self.plan_path.read_text(encoding="utf-8")
        return plan_parser.extract_plan_spec_from_text(text, "t1")

    def _save_task(self, spec: dict, task_id: str = "t1") -> None:
        backend = GitRefsBackend(
            queue_file=str(self.repo / ".agents" / "aet-queue"),
            history_file=str(self.repo / ".agents" / "work-history.jsonl"),
        )
        data = backend.load()
        queue = data["queue"]
        task = next((t for t in queue if t.get("id") == task_id), None)
        if task is None:
            task = {
                "id": task_id,
                "state": "awaiting_merge",
                "stage": "qa-complete",
                "branch": task_id,
                "plan_file": str(Path("docs/plans") / f"{task_id}.md"),
            }
            queue.append(task)
        task["spec"] = spec
        backend.save(queue)

    def test_merge_defaults_branch_to_none_for_runtime_resolution(self):
        """Typer defaults --branch to None so cmd_merge resolves the trunk at runtime."""
        with patch.object(ship, "cmd_merge", return_value=0) as mock_cmd:
            runner = CliRunner()
            result = runner.invoke(ship.app, ["merge", "t1"])
            self.assertEqual(result.exit_code, 0)
            mock_cmd.assert_called_once()
            args = mock_cmd.call_args[0][0]
            self.assertIsNone(args.branch)

    def test_merge_refuses_to_proceed_when_integrate_fails(self):
        """If integrate reports failure, cmd_merge exits non-zero."""
        args = SimpleNamespace(plan="t1", branch="dev", task_id="t1", spec=self._spec())
        with patch.object(ship, "_resolve_ship_task", return_value=None), \
             patch.object(ship, "_resolve_feature_branch", return_value="t1"), \
             patch.object(ship, "_find_target_worktree", return_value=self.repo), \
             patch.object(ship, "integrate", return_value=IntegrateResult("staged_conflict", detail="Gate failed")):
            rc = ship.cmd_merge(args)
        self.assertNotEqual(rc, 0)

    def test_merge_stops_on_conflict_detection(self):
        """Detected conflicts in integrate stop the merge."""
        args = SimpleNamespace(plan="t1", branch="dev", task_id="t1", spec=self._spec())
        with patch.object(ship, "_resolve_ship_task", return_value=None), \
             patch.object(ship, "_resolve_feature_branch", return_value="t1"), \
             patch.object(ship, "_find_target_worktree", return_value=self.repo), \
             patch.object(ship, "integrate", return_value=IntegrateResult("staged_conflict", detail="conflict!")):
            rc = ship.cmd_merge(args)
        self.assertNotEqual(rc, 0)

    def test_merge_happy_path_calls_integrate_and_archives(self):
        """A clean merge calls integrate and archives the plan."""
        args = SimpleNamespace(plan="t1", branch="dev", task_id="t1", spec=self._spec())
        merged_res = IntegrateResult("merged", detail="abc123")
        with patch.object(ship, "_resolve_ship_task", return_value=None), \
             patch.object(ship, "_resolve_feature_branch", return_value="t1"), \
             patch.object(ship, "_find_target_worktree", return_value=self.repo), \
             patch.object(ship, "integrate", return_value=merged_res) as mock_integrate, \
             patch.object(ship, "archive_plan_file") as mock_archive:
            rc = ship.cmd_merge(args)
        self.assertEqual(rc, 0)
        mock_integrate.assert_called_once()
        mock_archive.assert_called_once_with("t1")

    def test_merge_calls_integrate_with_task_recorded_branch(self):
        """cmd_merge passes task dict with recorded branch to integrate."""
        task = {
            "id": "t1",
            "branch": "feature/custom-branch-name",
            "spec": {"tasks": [{"id": "t1"}]},
        }
        args = SimpleNamespace(plan="t1", branch="dev", task=task, spec=task["spec"], task_id="t1")
        merged_res = IntegrateResult("merged", detail="abc123")
        with patch.object(ship, "_resolve_ship_task", return_value=None), \
             patch.object(ship, "_resolve_feature_branch", return_value="feature/custom-branch-name"), \
             patch.object(ship, "_find_target_worktree", return_value=self.repo), \
             patch.object(ship, "integrate", return_value=merged_res) as mock_integrate, \
             patch.object(ship, "archive_plan_file"):
            rc = ship.cmd_merge(args)
        self.assertEqual(rc, 0)
        mock_integrate.assert_called_once()
        call_task = mock_integrate.call_args[1]["task"]
        self.assertEqual(call_task["branch"], "feature/custom-branch-name")

    def _init_repo_with_task_branch(self, task_id: str) -> Path:
        """Create a real temp git repo whose HEAD is on ``main`` and which also
        has a branch named *task_id* carrying a commit absent from main."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.addCleanup(os.chdir, self.cwd)
        repo = Path(tmp.name)

        def git(*args: str) -> None:
            subprocess.run(
                ["git", "-C", str(repo), *args],
                check=True,
                capture_output=True,
                text=True,
            )

        git("init", "-q")
        git("symbolic-ref", "HEAD", "refs/heads/main")
        git("config", "user.email", "test@example.com")
        git("config", "user.name", "Test")
        (repo / "base.txt").write_text("base\n", encoding="utf-8")
        git("add", "base.txt")
        git("commit", "-q", "-m", "base on main")
        git("checkout", "-q", "-b", task_id)
        (repo / f"{task_id}.txt").write_text("feature\n", encoding="utf-8")
        git("add", f"{task_id}.txt")
        git("commit", "-q", "-m", f"work for {task_id}")
        git("checkout", "-q", "main")

        # Add a task record so cmd_merge can resolve the spec.
        (repo / ".agents").mkdir(parents=True, exist_ok=True)
        backend = GitRefsBackend(
            queue_file=str(repo / ".agents" / "aet-queue"),
            history_file=str(repo / ".agents" / "work-history.jsonl"),
        )
        spec = {
            "frontmatter": {"id": task_id},
            "title": f"Plan {task_id}",
            "body": "",
            "tasks": ["- [x] task one"],
        }
        backend.save(
            [
                {
                    "id": task_id,
                    "state": "awaiting_merge",
                    "stage": "qa-complete",
                    "branch": task_id,
                    "plan_file": f"docs/plans/{task_id}.md",
                    "spec": spec,
                }
            ]
        )
        return repo

    def test_merge_resolves_feature_branch_from_task_not_checkout(self):
        """Regression: the merge source is the task's branch, not the checkout."""
        os.chdir(self._init_repo_with_task_branch("t1"))
        captured = {}

        def fake_integrate(*args, **kwargs):
            captured["task"] = kwargs.get("task")
            captured["integration_branch"] = kwargs.get("integration_branch")
            return IntegrateResult("merged", detail="abc123")

        with patch.object(ship, "_find_target_worktree", return_value=Path("/fake/wt")), \
             patch.object(ship, "integrate", side_effect=fake_integrate), \
             patch.object(ship, "archive_plan_file"):
            rc = ship.cmd_merge(SimpleNamespace(plan="t1", branch="main"))
        self.assertEqual(rc, 0)
        self.assertEqual(captured["task"]["branch"], "t1")
        self.assertEqual(captured["integration_branch"], "main")

    def test_resolve_feature_branch_uses_task_id_not_checkout(self):
        """_resolve_feature_branch returns the task's branch (HEAD is on main),
        and fails closed (None) for an unknown task rather than the checkout."""
        os.chdir(self._init_repo_with_task_branch("t1"))
        self.assertEqual(ship._resolve_feature_branch("t1"), "t1")
        self.assertIsNone(ship._resolve_feature_branch("no-such-task"))

    def test_merge_refuses_self_merge(self):
        """A resolved feature branch equal to the target aborts before any merge."""
        with patch.object(ship, "_resolve_feature_branch", return_value="main"), \
             patch.object(ship, "integrate") as mock_integrate:
            rc = ship.cmd_merge(SimpleNamespace(plan="t1", branch="main"))
        self.assertNotEqual(rc, 0)
        mock_integrate.assert_not_called()

    def test_merge_fails_closed_when_branch_unresolvable(self):
        """When no branch resolves for the task, refuse rather than record a
        merge that did not happen."""
        with patch.object(ship, "_resolve_feature_branch", return_value=None), \
             patch.object(ship, "integrate") as mock_integrate:
            rc = ship.cmd_merge(SimpleNamespace(plan="t1", branch="main"))
        self.assertNotEqual(rc, 0)
        mock_integrate.assert_not_called()


class _StopAfterTargetResolution(Exception):
    """Halts cmd_merge once the target branch has been resolved and announced."""


class TestShipMergeTargetBranchAutoResolution(unittest.TestCase):
    """Target branch resolution in cmd_merge."""

    def test_target_branch_defaults_to_task_integration_branch(self):
        """When --branch is omitted, target_branch defaults to task's integration_branch."""
        args = SimpleNamespace(
            plan="t1",
            command="merge",
            branch=None,
            base=None,
        )
        task = {
            "id": "t1",
            "integration_branch": "feat/my-epic",
            "spec": {"tasks": [{"id": "t1"}]},
        }
        with patch.object(ship, "_resolve_ship_task", return_value=None), \
             patch.object(ship, "_resolve_trunk_ref", return_value="origin/main"), \
             patch.object(ship, "_resolve_feature_branch", return_value="feat/t1"), \
             patch.object(ship, "_find_target_worktree", side_effect=_StopAfterTargetResolution), \
             patch.dict(os.environ, {"AET_INTEGRATION_MODE": "single-pr"}), \
             patch("sys.stdout", new=io.StringIO()) as fake_out:
            args.task = task
            args.spec = task["spec"]
            args.task_id = "t1"
            with self.assertRaises(_StopAfterTargetResolution):
                ship.cmd_merge(args)
            self.assertIn("into feat/my-epic", fake_out.getvalue())

    def test_explicit_branch_overrides_task_integration_branch(self):
        """When --branch is explicitly provided, it overrides task's integration_branch."""
        args = SimpleNamespace(
            plan="t1",
            command="merge",
            branch="custom-target",
            base=None,
        )
        task = {
            "id": "t1",
            "integration_branch": "feat/my-epic",
            "spec": {"tasks": [{"id": "t1"}]},
        }
        with patch.object(ship, "_resolve_ship_task", return_value=None), \
             patch.object(ship, "_resolve_trunk_ref", return_value="origin/main"), \
             patch.object(ship, "_resolve_feature_branch", return_value="feat/t1"), \
             patch.object(ship, "_find_target_worktree", side_effect=_StopAfterTargetResolution), \
             patch("sys.stdout", new=io.StringIO()) as fake_out:
            args.task = task
            args.spec = task["spec"]
            args.task_id = "t1"
            with self.assertRaises(_StopAfterTargetResolution):
                ship.cmd_merge(args)
            self.assertIn("into custom-target", fake_out.getvalue())


class TestShipMergeIntegration(unittest.TestCase):
    """End-to-end integration test for `aet ship merge`."""

    def test_ship_merge_acquires_lock_and_produces_squash_commit(self):
        """`aet ship merge` acquires integration_lock and produces a squash commit on the target."""
        with tempfile.TemporaryDirectory() as repo_root, tempfile.TemporaryDirectory() as origin_root:
            subprocess.run(["git", "init", "--bare", "-q", origin_root], check=True)
            subprocess.run(["git", "init", "-q", repo_root], check=True)
            subprocess.run(["git", "-C", repo_root, "config", "user.email", "test@example.com"], check=True)
            subprocess.run(["git", "-C", repo_root, "config", "user.name", "Test User"], check=True)
            Path(repo_root, "README.md").write_text("# test\n", encoding="utf-8")
            subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
            subprocess.run(["git", "-C", repo_root, "commit", "-q", "-m", "initial"], check=True)
            subprocess.run(["git", "-C", repo_root, "branch", "-M", "main"], check=True)
            subprocess.run(["git", "-C", repo_root, "remote", "add", "origin", origin_root], check=True)
            subprocess.run(["git", "-C", repo_root, "push", "-q", "-u", "origin", "main"], check=True)
            subprocess.run(["git", "-C", repo_root, "update-ref", "refs/remotes/origin/main", "HEAD"], check=True)

            # Create target branch
            subprocess.run(["git", "-C", repo_root, "checkout", "-q", "-b", "target-branch"], check=True)
            subprocess.run(["git", "-C", repo_root, "push", "-q", "-u", "origin", "target-branch"], check=True)
            subprocess.run(
                ["git", "-C", repo_root, "update-ref", "refs/remotes/origin/target-branch", "HEAD"],
                check=True,
            )
            subprocess.run(["git", "-C", repo_root, "checkout", "-q", "main"], check=True)

            agents_dir = Path(repo_root, ".agents")
            agents_dir.mkdir(parents=True, exist_ok=True)
            (agents_dir / "aet-config.json").write_text(
                json.dumps({
                    "trunk_branch": "main",
                    "integration_branch": "target-branch",
                    "integration_mode": "single-pr",
                }),
                encoding="utf-8",
            )

            # Create task branch with 2 commits
            task_id = "task-merge-lock"
            subprocess.run(["git", "-C", repo_root, "checkout", "-q", "-b", task_id, "target-branch"], check=True)
            Path(repo_root, "file1.txt").write_text("content 1\n", encoding="utf-8")
            subprocess.run(["git", "-C", repo_root, "add", "file1.txt"], check=True)
            subprocess.run(["git", "-C", repo_root, "commit", "-q", "-m", "commit 1"], check=True)
            Path(repo_root, "file2.txt").write_text("content 2\n", encoding="utf-8")
            subprocess.run(["git", "-C", repo_root, "add", "file2.txt"], check=True)
            subprocess.run(["git", "-C", repo_root, "commit", "-q", "-m", "commit 2"], check=True)
            subprocess.run(["git", "-C", repo_root, "checkout", "-q", "main"], check=True)

            # Setup plan file
            plan_dir = Path(repo_root, "docs", "plans", "active")
            plan_dir.mkdir(parents=True, exist_ok=True)
            plan_path = plan_dir / f"{task_id}.md"
            plan_path.write_text(
                f"---\nid: {task_id}\nstatus: awaiting_merge\n---\n# Plan\n- [x] done\n",
                encoding="utf-8",
            )

            backend = create_backend(
                config_path=str(agents_dir / "aet-config.json"),
                queue_file=str(agents_dir / "aet-queue"),
                history_file=str(agents_dir / "work-history.jsonl"),
            )
            backend.save([
                {
                    "id": task_id,
                    "state": "awaiting_merge",
                    "stage": "qa-complete",
                    "branch": task_id,
                    "plan_file": f"docs/plans/active/{task_id}.md",
                    "spec": {
                        "frontmatter": {"id": task_id},
                        "title": f"Plan {task_id}",
                        "body": "- [x] done",
                        "tasks": [{"id": task_id}],
                    },
                }
            ])

            cwd = os.getcwd()
            try:
                os.chdir(repo_root)
                lock_acquired = False
                original_lock = integration_lock.integration_lock

                from contextlib import contextmanager

                @contextmanager
                def spy_lock(*args, **kwargs):
                    nonlocal lock_acquired
                    lock_acquired = True
                    with original_lock(*args, **kwargs):
                        yield

                real_integrate = ship.integrate
                seen_worktrees: list[str] = []

                def spy_integrate(*a, **kw):
                    seen_worktrees.append(kw["worktree_dir"])
                    return real_integrate(*a, **kw)

                skip_check = validation.CheckResult("SKIP", None, True, "")
                with patch("aet.integrate.integration_lock", side_effect=spy_lock), \
                     patch("aet.cli.ship.integrate", side_effect=spy_integrate), \
                     patch("aet.validation.pre_integration_check", return_value=skip_check), \
                     patch("aet.gate.check_task_evidence", return_value=(True, [])):
                    args = SimpleNamespace(plan=task_id, branch="target-branch")
                    rc = ship.cmd_merge(args)

                self.assertEqual(rc, 0)
                self.assertTrue(lock_acquired, "integration_lock was not acquired during ship merge")

                # The ephemeral merge worktree lives outside the repo (no IDE watcher
                # contention) and is fully cleaned up afterwards.
                self.assertEqual(len(seen_worktrees), 1)
                merge_wt = Path(seen_worktrees[0]).resolve()
                self.assertNotIn(Path(repo_root).resolve(), merge_wt.parents)
                self.assertTrue(merge_wt.name.startswith(f"aet-merge-{task_id}-"))
                self.assertFalse(merge_wt.exists())
                wt_list = subprocess.run(
                    ["git", "-C", repo_root, "worktree", "list", "--porcelain"],
                    capture_output=True, text=True, check=True,
                ).stdout
                self.assertNotIn(str(merge_wt), wt_list)

                # Verify target branch received squash commit
                log = subprocess.run(
                    ["git", "-C", repo_root, "log", "origin/target-branch", "--oneline"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                self.assertIn(f"Integrate {task_id}", log.stdout)
                # Verify commit 1 and commit 2 are squashed (not distinct commits in target log)
                self.assertNotIn("commit 1", log.stdout)
                self.assertNotIn("commit 2", log.stdout)

                # Verify plan was archived
                self.assertFalse(plan_path.exists())
                archived = Path(repo_root, "docs", "plans", "archive", f"{task_id}.md")
                self.assertTrue(archived.exists())
            finally:
                os.chdir(cwd)


if __name__ == "__main__":
    unittest.main()
