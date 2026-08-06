"""Tests for aet-work worktree helpers."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from aet import worktree


class TestCopyUntrackedFiles(unittest.TestCase):
    def test_copies_untracked_plan_prd_and_adr_into_worktree(self):
        """Untracked docs referenced by a plan are copied to the worktree."""
        with tempfile.TemporaryDirectory() as repo_root:
            worktree_dir = os.path.join(repo_root, ".worktrees", "x-demo")

            # Initialize a repo so git ls-files works.
            subprocess.run(["git", "init", "-q", repo_root], check=True)
            subprocess.run(
                ["git", "-C", repo_root, "config", "user.email", "test@example.com"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", repo_root, "config", "user.name", "Test User"],
                check=True,
            )

            # Create tracked directories so pathspecs match.
            for subdir in [
                "docs/plans",
                "docs/prds",
                "docs/adr",
                "docs/audits",
                "docs/retros",
                "docs/product-briefs",
            ]:
                Path(repo_root, subdir).mkdir(parents=True, exist_ok=True)

            # Create untracked files.
            untracked_files = [
                "docs/plans/x-demo.md",
                "docs/prds/x-demo-prd.md",
                "docs/adr/099-x-demo.md",
                "docs/audits/x-demo-audit.md",
                "docs/retros/x-demo-retro.md",
                "docs/product-briefs/x-demo-brief.md",
            ]
            for rel_path in untracked_files:
                Path(repo_root, rel_path).write_text("content", encoding="utf-8")

            worktree.copy_untracked_files(repo_root, worktree_dir)

            for rel_path in untracked_files:
                dest = Path(worktree_dir, rel_path)
                self.assertTrue(dest.exists(), f"Expected {rel_path} to be copied")
                self.assertEqual(dest.read_text(encoding="utf-8"), "content")


class TestPrepareWorktreeDependencies(unittest.TestCase):
    def test_creates_relative_symlinks_for_configured_dependencies(self):
        """Configured dependencies are symlinked from repo root into the worktree."""
        with tempfile.TemporaryDirectory() as repo_root:
            worktree_dir = os.path.join(repo_root, ".worktrees", "x-demo")
            Path(repo_root, ".agents").mkdir(parents=True, exist_ok=True)
            Path(repo_root, "app", "node_modules", "pkg").mkdir(parents=True, exist_ok=True)
            Path(repo_root, "api", "vendor", "lib").mkdir(parents=True, exist_ok=True)

            config = {
                "symlink_dependencies": [
                    {"name": "node_modules", "source": "app/node_modules", "target": "app/node_modules"},
                    {"name": "vendor", "source": "api/vendor", "target": "api/vendor"},
                ]
            }
            Path(repo_root, ".agents", "aet-config.json").write_text(
                json.dumps(config), encoding="utf-8"
            )

            results = worktree.prepare_worktree_dependencies(repo_root, worktree_dir)

            self.assertEqual(len(results), 2)
            self.assertEqual(results[0]["status"], "created")
            self.assertEqual(results[1]["status"], "created")

            node_link = Path(worktree_dir, "app", "node_modules")
            vendor_link = Path(worktree_dir, "api", "vendor")
            self.assertTrue(node_link.is_symlink())
            self.assertTrue(vendor_link.is_symlink())
            self.assertTrue(node_link.resolve().samefile(Path(repo_root, "app", "node_modules")))
            self.assertTrue(vendor_link.resolve().samefile(Path(repo_root, "api", "vendor")))

            # Symlinks should be relative so they survive repo relocation.
            self.assertFalse(os.path.isabs(os.readlink(node_link)))

    def test_reports_missing_source_directories_as_failed(self):
        """Missing source directories are reported, not silently ignored."""
        with tempfile.TemporaryDirectory() as repo_root:
            worktree_dir = os.path.join(repo_root, ".worktrees", "x-demo")
            Path(repo_root, ".agents").mkdir(parents=True, exist_ok=True)
            config = {
                "symlink_dependencies": [
                    {"name": "node_modules", "source": "app/node_modules", "target": "app/node_modules"},
                ]
            }
            Path(repo_root, ".agents", "aet-config.json").write_text(
                json.dumps(config), encoding="utf-8"
            )

            results = worktree.prepare_worktree_dependencies(repo_root, worktree_dir)

            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["status"], "failed")
            self.assertIn("source does not exist", results[0]["message"])

    def test_skips_existing_targets(self):
        """Existing directories or symlinks are left in place."""
        with tempfile.TemporaryDirectory() as repo_root:
            worktree_dir = os.path.join(repo_root, ".worktrees", "x-demo")
            Path(repo_root, ".agents").mkdir(parents=True, exist_ok=True)
            Path(repo_root, "app", "node_modules").mkdir(parents=True, exist_ok=True)
            Path(worktree_dir, "app", "node_modules").mkdir(parents=True, exist_ok=True)

            config = {
                "symlink_dependencies": [
                    {"name": "node_modules", "source": "app/node_modules", "target": "app/node_modules"},
                ]
            }
            Path(repo_root, ".agents", "aet-config.json").write_text(
                json.dumps(config), encoding="utf-8"
            )

            results = worktree.prepare_worktree_dependencies(repo_root, worktree_dir)

            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["status"], "skipped")

    def test_returns_empty_when_config_missing(self):
        """No config means no action."""
        with tempfile.TemporaryDirectory() as repo_root:
            worktree_dir = os.path.join(repo_root, ".worktrees", "x-demo")
            results = worktree.prepare_worktree_dependencies(repo_root, worktree_dir)
            self.assertEqual(results, [])


class TestDependencyWarmupRequired(unittest.TestCase):
    def test_returns_missing_dependencies_when_configured_but_absent(self):
        with tempfile.TemporaryDirectory() as repo_root:
            worktree_dir = os.path.join(repo_root, ".worktrees", "x-demo")
            Path(worktree_dir).mkdir(parents=True, exist_ok=True)
            Path(repo_root, ".agents").mkdir(parents=True, exist_ok=True)
            config = {
                "symlink_dependencies": [
                    {"name": "node_modules", "source": "app/node_modules", "target": "app/node_modules"},
                    {"name": "vendor", "source": "api/vendor", "target": "api/vendor"},
                ]
            }
            Path(repo_root, ".agents", "aet-config.json").write_text(
                json.dumps(config), encoding="utf-8"
            )

            missing = worktree.dependency_warmup_required(repo_root, worktree_dir)
            self.assertEqual(len(missing), 2)
            self.assertEqual(missing[0]["name"], "node_modules")
            self.assertEqual(missing[0]["target"], "app/node_modules")

    def test_returns_empty_when_dependencies_present(self):
        with tempfile.TemporaryDirectory() as repo_root:
            worktree_dir = os.path.join(repo_root, ".worktrees", "x-demo")
            Path(worktree_dir, "app", "node_modules").mkdir(parents=True, exist_ok=True)
            Path(repo_root, ".agents").mkdir(parents=True, exist_ok=True)
            config = {
                "symlink_dependencies": [
                    {"name": "node_modules", "source": "app/node_modules", "target": "app/node_modules"},
                ]
            }
            Path(repo_root, ".agents", "aet-config.json").write_text(
                json.dumps(config), encoding="utf-8"
            )

            missing = worktree.dependency_warmup_required(repo_root, worktree_dir)
            self.assertEqual(missing, [])

    def test_returns_empty_when_config_missing(self):
        with tempfile.TemporaryDirectory() as repo_root:
            worktree_dir = os.path.join(repo_root, ".worktrees", "x-demo")
            missing = worktree.dependency_warmup_required(repo_root, worktree_dir)
            self.assertEqual(missing, [])


class TestCreateWorktree(unittest.TestCase):
    def _init_repo(self, repo_root: str) -> None:
        subprocess.run(["git", "init", "-q", repo_root], check=True)
        subprocess.run(
            ["git", "-C", repo_root, "config", "user.email", "test@example.com"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", repo_root, "config", "user.name", "Test User"],
            check=True,
        )

    def test_refresh_diverged_branch_leaves_repo_root_head_unchanged(self):
        """Regression: rebasing a diverged task branch must not checkout in repo_root."""
        with tempfile.TemporaryDirectory() as repo_root:
            self._init_repo(repo_root)

            # Old base commit.
            Path(repo_root, "base.txt").write_text("old", encoding="utf-8")
            subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
            subprocess.run(
                ["git", "-C", repo_root, "commit", "-q", "-m", "old base"],
                check=True,
            )
            old_base = subprocess.run(
                ["git", "-C", repo_root, "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=True,

            ).stdout.strip()

            # Task branch diverges from the old base. Use a temporary worktree so
            # repo_root never checks out the task branch.
            subprocess.run(
                ["git", "-C", repo_root, "branch", "task-001", old_base],
                check=True,
            )
            with tempfile.TemporaryDirectory() as task_temp:
                subprocess.run(
                    ["git", "-C", repo_root, "worktree", "add", task_temp, "task-001"],
                    check=True,
                )
                try:
                    Path(task_temp, "task.txt").write_text("task work", encoding="utf-8")
                    subprocess.run(["git", "-C", task_temp, "add", "."], check=True)
                    subprocess.run(
                        ["git", "-C", task_temp, "commit", "-q", "-m", "task commit"],
                        check=True,
                    )
                finally:
                    subprocess.run(
                        ["git", "-C", repo_root, "worktree", "remove", "-f", task_temp],
                        check=True,
                        capture_output=True,
                    )

            # repo_root is on a feature branch.
            subprocess.run(
                ["git", "-C", repo_root, "checkout", "-q", "-b", "feature"],
                check=True,
            )
            Path(repo_root, "feature.txt").write_text("feature work", encoding="utf-8")
            subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
            subprocess.run(
                ["git", "-C", repo_root, "commit", "-q", "-m", "feature commit"],
                check=True,
            )

            # Advance main so the task branch diverges from the current base.
            subprocess.run(["git", "-C", repo_root, "checkout", "-q", "main"], check=True)
            Path(repo_root, "main.txt").write_text("main advance", encoding="utf-8")
            subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
            subprocess.run(
                ["git", "-C", repo_root, "commit", "-q", "-m", "main advance"],
                check=True,
            )

            # Return repo_root to the feature branch before refreshing.
            subprocess.run(
                ["git", "-C", repo_root, "checkout", "-q", "feature"], check=True
            )
            before = subprocess.run(
                ["git", "-C", repo_root, "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()

            worktree.create_worktree(repo_root, "task-001", "main")

            after = subprocess.run(
                ["git", "-C", repo_root, "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            self.assertEqual(after, before)
            self.assertEqual(after, "feature")

    def test_refresh_conflict_rebuilds_branch_from_base(self):
        """On rebase conflict the branch is deleted and recreated from base."""
        with tempfile.TemporaryDirectory() as repo_root:
            self._init_repo(repo_root)

            # Old base commit creates a file that will conflict.
            Path(repo_root, "shared.txt").write_text("old", encoding="utf-8")
            subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
            subprocess.run(
                ["git", "-C", repo_root, "commit", "-q", "-m", "old base"],
                check=True,
            )
            old_base = subprocess.run(
                ["git", "-C", repo_root, "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()

            subprocess.run(
                ["git", "-C", repo_root, "branch", "task-001", old_base],
                check=True,
            )
            with tempfile.TemporaryDirectory() as task_temp:
                subprocess.run(
                    ["git", "-C", repo_root, "worktree", "add", task_temp, "task-001"],
                    check=True,
                )
                try:
                    Path(task_temp, "shared.txt").write_text("task", encoding="utf-8")
                    subprocess.run(["git", "-C", task_temp, "add", "."], check=True)
                    subprocess.run(
                        ["git", "-C", task_temp, "commit", "-q", "-m", "task commit"],
                        check=True,
                    )
                finally:
                    subprocess.run(
                        ["git", "-C", repo_root, "worktree", "remove", "-f", task_temp],
                        check=True,
                        capture_output=True,
                    )

            # repo_root is on a feature branch.
            subprocess.run(
                ["git", "-C", repo_root, "checkout", "-q", "-b", "feature"],
                check=True,
            )
            Path(repo_root, "feature.txt").write_text("feature work", encoding="utf-8")
            subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
            subprocess.run(
                ["git", "-C", repo_root, "commit", "-q", "-m", "feature commit"],
                check=True,
            )

            # Advance main with a conflicting change.
            subprocess.run(["git", "-C", repo_root, "checkout", "-q", "main"], check=True)
            Path(repo_root, "shared.txt").write_text("main", encoding="utf-8")
            subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
            subprocess.run(
                ["git", "-C", repo_root, "commit", "-q", "-m", "main advance"],
                check=True,
            )
            main_sha = subprocess.run(
                ["git", "-C", repo_root, "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()

            subprocess.run(
                ["git", "-C", repo_root, "checkout", "-q", "feature"], check=True
            )
            before = subprocess.run(
                ["git", "-C", repo_root, "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()

            worktree.create_worktree(repo_root, "task-001", "main")

            after = subprocess.run(
                ["git", "-C", repo_root, "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            self.assertEqual(after, before)
            self.assertEqual(after, "feature")

            # Branch was recreated from base.
            branch_sha = subprocess.run(
                ["git", "-C", repo_root, "rev-parse", "task-001"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            self.assertEqual(branch_sha, main_sha)

            # Worktree exists.
            self.assertTrue(os.path.isdir(os.path.join(repo_root, ".worktrees", "task-001")))


class TestNonMainBase(unittest.TestCase):
    def _init_repo(self, repo_root: str) -> None:
        subprocess.run(["git", "init", "-q", repo_root], check=True)
        subprocess.run(
            ["git", "-C", repo_root, "config", "user.email", "test@example.com"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", repo_root, "config", "user.name", "Test User"],
            check=True,
        )

    def _setup_dev_base(self, repo_root: str) -> str:
        """Create a 'dev' branch and an origin/dev remote-tracking ref."""
        Path(repo_root, "README.md").write_text("# test", encoding="utf-8")
        subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
        subprocess.run(
            ["git", "-C", repo_root, "commit", "-q", "-m", "init on main"],
            check=True,
        )
        # Create a dev branch and a remote-tracking ref for it.
        subprocess.run(["git", "-C", repo_root, "branch", "dev"], check=True)
        dev_sha = subprocess.run(
            ["git", "-C", repo_root, "rev-parse", "dev"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        subprocess.run(
            ["git", "-C", repo_root, "update-ref", "refs/remotes/origin/dev", dev_sha],
            check=True,
        )
        return dev_sha

    def test_create_worktree_uses_non_main_base(self):
        """A resolved integration branch other than main is used as the base."""
        with tempfile.TemporaryDirectory() as repo_root:
            self._init_repo(repo_root)
            dev_sha = self._setup_dev_base(repo_root)

            worktree_dir = worktree.create_worktree(repo_root, "task-dev", "origin/dev")

            self.assertTrue(os.path.isdir(worktree_dir))
            branch_sha = subprocess.run(
                ["git", "-C", repo_root, "rev-parse", "task-dev"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            self.assertEqual(branch_sha, dev_sha)

    def test_remove_worktree_counts_against_non_main_base(self):
        """Cleanup counts against the resolved integration branch, not main."""
        with tempfile.TemporaryDirectory() as repo_root:
            self._init_repo(repo_root)
            self._setup_dev_base(repo_root)

            worktree_dir = worktree.create_worktree(repo_root, "task-dev", "origin/dev")
            self.assertTrue(os.path.isdir(worktree_dir))

            # With no commits ahead of origin/dev, cleanup succeeds.
            removed = worktree.remove_worktree(repo_root, "task-dev", "origin/dev")
            self.assertTrue(removed)
            self.assertFalse(os.path.isdir(worktree_dir))

    def test_remove_worktree_refuses_when_ahead_of_non_main_base(self):
        """Cleanup refuses when the task branch is ahead of the integration base."""
        with tempfile.TemporaryDirectory() as repo_root:
            self._init_repo(repo_root)
            self._setup_dev_base(repo_root)

            worktree_dir = worktree.create_worktree(repo_root, "task-dev", "origin/dev")
            Path(worktree_dir, "task.txt").write_text("work", encoding="utf-8")
            subprocess.run(["git", "-C", worktree_dir, "add", "."], check=True)
            subprocess.run(
                ["git", "-C", worktree_dir, "commit", "-q", "-m", "task commit"],
                check=True,
            )

            removed = worktree.remove_worktree(repo_root, "task-dev", "origin/dev")
            self.assertFalse(removed)
            self.assertTrue(os.path.isdir(worktree_dir))


class TestDeferredPaths(unittest.TestCase):
    def test_is_deferred_path_recognizes_docs_plans(self):
        self.assertTrue(worktree.is_deferred_path("docs/plans/foo.md"))
        self.assertTrue(worktree.is_deferred_path("docs/plans/nested/bar.md"))
        self.assertTrue(worktree.is_deferred_path("docs/plans"))

    def test_is_deferred_path_rejects_non_plan_paths(self):
        self.assertFalse(worktree.is_deferred_path("docs/prds/foo.md"))
        self.assertFalse(worktree.is_deferred_path("src/aet/foo.py"))
        self.assertFalse(worktree.is_deferred_path("docs/plans-backup/foo.md"))
        self.assertFalse(worktree.is_deferred_path("README.md"))


class TestCheckBaseHygiene(unittest.TestCase):
    def _init_repo(self, repo_root: str) -> None:
        subprocess.run(["git", "init", "-q", repo_root], check=True)
        subprocess.run(
            ["git", "-C", repo_root, "config", "user.email", "test@example.com"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", repo_root, "config", "user.name", "Test User"],
            check=True,
        )
        Path(repo_root, "README.md").write_text("# test", encoding="utf-8")
        subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
        subprocess.run(["git", "-C", repo_root, "commit", "-q", "-m", "init"], check=True)

    def _init_repo_with_origin(self, repo_root: str) -> None:
        """Initialize a repo with a main branch and a local origin/main ref."""
        self._init_repo(repo_root)
        subprocess.run(["git", "-C", repo_root, "branch", "-M", "main"], check=True)
        subprocess.run(
            ["git", "-C", repo_root, "remote", "add", "origin", repo_root],
            check=True,
        )
        subprocess.run(
            ["git", "-C", repo_root, "update-ref", "refs/remotes/origin/main", "HEAD"],
            check=True,
        )

    def test_queue_sidecars_do_not_trip_dirty_check(self):
        """The lock and lease sidecars linger by design; hygiene must ignore them."""
        with tempfile.TemporaryDirectory() as repo_root:
            self._init_repo(repo_root)
            agents_dir = Path(repo_root, ".agents")
            agents_dir.mkdir()
            for sidecar in ("work-queue.json.lock", "work-queue.lease"):
                (agents_dir / sidecar).write_text("", encoding="utf-8")

            ok, msg = worktree.check_base_hygiene(repo_root)

            self.assertTrue(ok, f"sidecars should be ignored, got: {msg}")

    def test_other_untracked_files_still_fail_hygiene(self):
        """Control: the ignore list must not widen beyond the queue artifacts."""
        with tempfile.TemporaryDirectory() as repo_root:
            self._init_repo(repo_root)
            agents_dir = Path(repo_root, ".agents")
            agents_dir.mkdir()
            (agents_dir / "notes.txt").write_text("x", encoding="utf-8")

            ok, msg = worktree.check_base_hygiene(repo_root)

            self.assertFalse(ok)
            self.assertEqual(msg, "Working tree is dirty")

    def test_untracked_plan_is_allowed(self):
        """An untracked docs/plans file is deferred; hygiene ignores it."""
        with tempfile.TemporaryDirectory() as repo_root:
            self._init_repo_with_origin(repo_root)
            plan = Path(repo_root, "docs", "plans", "new.md")
            plan.parent.mkdir(parents=True, exist_ok=True)
            plan.write_text("---\nid: new\n---\n", encoding="utf-8")

            ok, msg = worktree.check_base_hygiene(repo_root, "main", "main")

            self.assertTrue(ok, msg)

    def test_modified_plan_is_allowed(self):
        """A modified docs/plans file is deferred; hygiene ignores it."""
        with tempfile.TemporaryDirectory() as repo_root:
            self._init_repo_with_origin(repo_root)
            plan = Path(repo_root, "docs", "plans", "existing.md")
            plan.parent.mkdir(parents=True, exist_ok=True)
            plan.write_text("---\nid: existing\n---\n", encoding="utf-8")
            subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
            subprocess.run(
                ["git", "-C", repo_root, "commit", "-q", "-m", "add plan"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", repo_root, "update-ref", "refs/remotes/origin/main", "HEAD"],
                check=True,
            )
            plan.write_text("---\nid: existing\nstatus: queued\n---\n", encoding="utf-8")

            ok, msg = worktree.check_base_hygiene(repo_root, "main", "main")

            self.assertTrue(ok, msg)

    def test_non_plan_dirty_still_halts(self):
        """A dirty non-deferred path still fails hygiene even with a clean plan."""
        with tempfile.TemporaryDirectory() as repo_root:
            self._init_repo_with_origin(repo_root)
            plan = Path(repo_root, "docs", "plans", "new.md")
            plan.parent.mkdir(parents=True, exist_ok=True)
            plan.write_text("---\nid: new\n---\n", encoding="utf-8")
            Path(repo_root, "dirty.txt").write_text("x", encoding="utf-8")

            ok, msg = worktree.check_base_hygiene(repo_root, "main", "main")

            self.assertFalse(ok)
            self.assertEqual(msg, "Working tree is dirty")

    def test_ahead_with_only_plan_commits_passes(self):
        """Local main may be ahead of origin if every diverging path is a plan."""
        with tempfile.TemporaryDirectory() as repo_root:
            self._init_repo_with_origin(repo_root)
            plan = Path(repo_root, "docs", "plans", "new.md")
            plan.parent.mkdir(parents=True, exist_ok=True)
            plan.write_text("---\nid: new\n---\n", encoding="utf-8")
            subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
            subprocess.run(
                ["git", "-C", repo_root, "commit", "-q", "-m", "add plan"],
                check=True,
            )

            ok, msg = worktree.check_base_hygiene(repo_root, "main", "main")

            self.assertTrue(ok, msg)

    def test_ahead_with_mixed_plan_and_code_fails(self):
        """A commit mixing a plan and a source file is still a hygiene violation."""
        with tempfile.TemporaryDirectory() as repo_root:
            self._init_repo_with_origin(repo_root)
            plan = Path(repo_root, "docs", "plans", "new.md")
            plan.parent.mkdir(parents=True, exist_ok=True)
            plan.write_text("---\nid: new\n---\n", encoding="utf-8")
            code = Path(repo_root, "src", "code.py")
            code.parent.mkdir(parents=True, exist_ok=True)
            code.write_text("x", encoding="utf-8")
            subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
            subprocess.run(
                ["git", "-C", repo_root, "commit", "-q", "-m", "mixed commit"],
                check=True,
            )

            ok, msg = worktree.check_base_hygiene(repo_root, "main", "main")

            self.assertFalse(ok)
            self.assertIn("ahead", msg.lower())

    def test_behind_origin_still_halts(self):
        """A local main behind origin fails hygiene regardless of plan paths."""
        with tempfile.TemporaryDirectory() as repo_root:
            self._init_repo_with_origin(repo_root)
            new_head = subprocess.run(
                [
                    "git",
                    "-C",
                    repo_root,
                    "commit-tree",
                    "HEAD^{tree}",
                    "-p",
                    "HEAD",
                    "-m",
                    "remote commit",
                ],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            subprocess.run(
                ["git", "-C", repo_root, "update-ref", "refs/remotes/origin/main", new_head],
                check=True,
            )

            ok, msg = worktree.check_base_hygiene(repo_root, "main", "main")

            self.assertFalse(ok)
            self.assertIn("behind", msg.lower())


def _init_repo_with_origin(repo_root: str) -> None:
    """Initialize a repo with a clean main branch tracking origin."""
    subprocess.run(["git", "init", "-q", repo_root], check=True)
    subprocess.run(
        ["git", "-C", repo_root, "config", "user.email", "test@example.com"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", repo_root, "config", "user.name", "Test User"],
        check=True,
    )
    Path(repo_root, "README.md").write_text("# test", encoding="utf-8")
    subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
    subprocess.run(
        ["git", "-C", repo_root, "commit", "-q", "-m", "initial"],
        check=True,
    )
    subprocess.run(["git", "-C", repo_root, "branch", "-M", "main"], check=True)
    subprocess.run(
        ["git", "-C", repo_root, "remote", "add", "origin", repo_root],
        check=True,
    )
    subprocess.run(
        ["git", "-C", repo_root, "update-ref", "refs/remotes/origin/main", "HEAD"],
        check=True,
    )


class TestOverlayDeferredPlans(unittest.TestCase):
    def test_overlays_untracked_plan(self):
        """Deferred docs/plans/ files are copied regardless of git state."""
        with tempfile.TemporaryDirectory() as repo_root:
            _init_repo_with_origin(repo_root)
            Path(repo_root, "docs", "plans").mkdir(parents=True, exist_ok=True)
            Path(repo_root, "docs", "plans", "x.md").write_text(
                "plan", encoding="utf-8"
            )
            worktree_dir = os.path.join(repo_root, ".worktrees", "x")

            worktree.copy_untracked_files(repo_root, worktree_dir)

            copied = Path(worktree_dir, "docs", "plans", "x.md")
            self.assertTrue(copied.exists())
            self.assertEqual(copied.read_text(encoding="utf-8"), "plan")

    def test_overlays_modified_tracked_plan(self):
        """A tracked but modified plan is overlayed with the working-tree version."""
        with tempfile.TemporaryDirectory() as repo_root:
            _init_repo_with_origin(repo_root)
            plan = Path(repo_root, "docs", "plans", "x.md")
            plan.parent.mkdir(parents=True, exist_ok=True)
            plan.write_text("base", encoding="utf-8")
            subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
            subprocess.run(
                ["git", "-C", repo_root, "commit", "-q", "-m", "add plan"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", repo_root, "update-ref", "refs/remotes/origin/main", "HEAD"],
                check=True,
            )
            plan.write_text("modified", encoding="utf-8")
            worktree_dir = os.path.join(repo_root, ".worktrees", "x")

            worktree.copy_untracked_files(repo_root, worktree_dir)

            self.assertEqual(
                Path(worktree_dir, "docs", "plans", "x.md").read_text(
                    encoding="utf-8"
                ),
                "modified",
            )

    def test_overlays_plan_absent_from_base(self):
        """A plan not present in the base is still copied into the worktree."""
        with tempfile.TemporaryDirectory() as repo_root:
            _init_repo_with_origin(repo_root)
            plan = Path(repo_root, "docs", "plans", "x.md")
            plan.parent.mkdir(parents=True, exist_ok=True)
            plan.write_text("new", encoding="utf-8")
            worktree_dir = os.path.join(repo_root, ".worktrees", "x")

            worktree.copy_untracked_files(repo_root, worktree_dir)

            self.assertTrue(Path(worktree_dir, "docs", "plans", "x.md").exists())

    def test_does_not_overlay_prd_by_content(self):
        """Non-deferred directories keep the untracked-only mirror behavior."""
        with tempfile.TemporaryDirectory() as repo_root:
            _init_repo_with_origin(repo_root)
            prd = Path(repo_root, "docs", "prds", "tracked.md")
            prd.parent.mkdir(parents=True, exist_ok=True)
            prd.write_text("base", encoding="utf-8")
            subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
            subprocess.run(
                ["git", "-C", repo_root, "commit", "-q", "-m", "add prd"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", repo_root, "update-ref", "refs/remotes/origin/main", "HEAD"],
                check=True,
            )
            prd.write_text("modified", encoding="utf-8")
            Path(repo_root, "docs", "prds", "new.md").write_text(
                "untracked", encoding="utf-8"
            )
            worktree_dir = worktree.create_worktree(repo_root, "x", "origin/main")

            worktree.copy_untracked_files(repo_root, worktree_dir)

            # Untracked PRD is mirrored.
            self.assertTrue(Path(worktree_dir, "docs", "prds", "new.md").exists())
            # Modified tracked PRD is left at the base version.
            self.assertEqual(
                Path(worktree_dir, "docs", "prds", "tracked.md").read_text(
                    encoding="utf-8"
                ),
                "base",
            )


class TestSeedTaskPlan(unittest.TestCase):
    def test_seeds_plan_with_explicit_path_and_decoys(self):
        """The seed commit contains exactly the task plan, ignoring decoys."""
        with tempfile.TemporaryDirectory() as repo_root:
            _init_repo_with_origin(repo_root)
            worktree_dir = worktree.create_worktree(repo_root, "task-001", "origin/main")

            plan = Path(repo_root, "docs", "plans", "task-001.md")
            plan.parent.mkdir(parents=True, exist_ok=True)
            plan.write_text("plan", encoding="utf-8")
            Path(repo_root, "docs", "plans", "decoy-plan.md").write_text(
                "decoy plan", encoding="utf-8"
            )
            Path(repo_root, "docs", "prds").mkdir(parents=True, exist_ok=True)
            Path(repo_root, "docs", "prds", "decoy-prd.md").write_text(
                "decoy prd", encoding="utf-8"
            )

            worktree.copy_untracked_files(repo_root, worktree_dir)
            seeded = worktree.seed_task_plan(
                repo_root, worktree_dir, str(plan), "task-001", "main"
            )
            self.assertTrue(seeded)

            # The commit contains exactly one file.
            files = subprocess.run(
                [
                    "git",
                    "-C",
                    worktree_dir,
                    "diff-tree",
                    "--no-commit-id",
                    "--name-only",
                    "-r",
                    "HEAD",
                ],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip().split("\n")
            self.assertEqual(files, ["docs/plans/task-001.md"])

            # Decoys remain untracked in the worktree.
            status = subprocess.run(
                ["git", "-C", worktree_dir, "status", "--short", "--untracked-files=all"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            self.assertIn("docs/plans/decoy-plan.md", status)
            self.assertIn("docs/prds/decoy-prd.md", status)

    def test_skips_when_base_carries_plan(self):
        """Seeding is skipped when the integration base already has the plan path."""
        with tempfile.TemporaryDirectory() as repo_root:
            _init_repo_with_origin(repo_root)
            plan = Path(repo_root, "docs", "plans", "task-001.md")
            plan.parent.mkdir(parents=True, exist_ok=True)
            plan.write_text("plan", encoding="utf-8")
            subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
            subprocess.run(
                ["git", "-C", repo_root, "commit", "-q", "-m", "add plan"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", repo_root, "update-ref", "refs/remotes/origin/main", "HEAD"],
                check=True,
            )
            worktree_dir = worktree.create_worktree(repo_root, "task-001", "origin/main")

            seeded = worktree.seed_task_plan(
                repo_root, worktree_dir, str(plan), "task-001", "main"
            )
            self.assertFalse(seeded)
            ahead = subprocess.run(
                ["git", "-C", worktree_dir, "rev-list", "--count", "origin/main..HEAD"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            self.assertEqual(ahead, "0")

    def test_skip_avoids_duplicate_plan_on_unpushed_integration_commit(self):
        """A plan on an unpushed local integration commit does not cause add/add conflicts."""
        with tempfile.TemporaryDirectory() as repo_root:
            _init_repo_with_origin(repo_root)
            plan = Path(repo_root, "docs", "plans", "task-001.md")
            plan.parent.mkdir(parents=True, exist_ok=True)
            plan.write_text("plan", encoding="utf-8")
            subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
            subprocess.run(
                ["git", "-C", repo_root, "commit", "-q", "-m", "add plan to main"],
                check=True,
            )
            # Simulate an unpushed local commit: origin/main stays behind.
            subprocess.run(
                ["git", "-C", repo_root, "update-ref", "refs/remotes/origin/main", "HEAD^"],
                check=True,
            )
            worktree_dir = worktree.create_worktree(repo_root, "task-001", "origin/main")
            worktree.copy_untracked_files(repo_root, worktree_dir)

            seeded = worktree.seed_task_plan(
                repo_root, worktree_dir, str(plan), "task-001", "main"
            )
            self.assertFalse(seeded)

            Path(worktree_dir, "src").mkdir(parents=True, exist_ok=True)
            Path(worktree_dir, "src", "code.py").write_text("code", encoding="utf-8")
            subprocess.run(["git", "-C", worktree_dir, "add", "."], check=True)
            subprocess.run(
                ["git", "-C", worktree_dir, "commit", "-q", "-m", "implement"],
                check=True,
            )

            subprocess.run(["git", "-C", repo_root, "checkout", "-q", "main"], check=True)
            merge = subprocess.run(
                ["git", "-C", repo_root, "merge", "task-001"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(merge.returncode, 0, merge.stderr)
            self.assertEqual(plan.read_text(encoding="utf-8"), "plan")

    def test_skips_when_worktree_already_carries_unchanged_plan(self):
        """Resuming a run does not fail when the plan was already seeded."""
        with tempfile.TemporaryDirectory() as repo_root:
            _init_repo_with_origin(repo_root)
            worktree_dir = worktree.create_worktree(
                repo_root, "task-001", "origin/main"
            )
            plan = Path(repo_root, "docs", "plans", "task-001.md")
            plan.parent.mkdir(parents=True, exist_ok=True)
            plan.write_text("plan", encoding="utf-8")

            worktree.copy_untracked_files(repo_root, worktree_dir)
            first = worktree.seed_task_plan(
                repo_root, worktree_dir, str(plan), "task-001", "main"
            )
            self.assertTrue(first)

            # A second call with the same plan content finds nothing to commit.
            second = worktree.seed_task_plan(
                repo_root, worktree_dir, str(plan), "task-001", "main"
            )
            self.assertFalse(second)

            ahead = subprocess.run(
                ["git", "-C", worktree_dir, "rev-list", "--count", "origin/main..HEAD"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            self.assertEqual(ahead, "1")


class TestRemoveWorktreeClassification(unittest.TestCase):
    def test_removes_plan_only_worktree(self):
        """A worktree whose only commit touches a deferred path is removed."""
        with tempfile.TemporaryDirectory() as repo_root:
            _init_repo_with_origin(repo_root)
            worktree_dir = worktree.create_worktree(repo_root, "task-001", "origin/main")
            plan = Path(worktree_dir, "docs", "plans", "task-001.md")
            plan.parent.mkdir(parents=True, exist_ok=True)
            plan.write_text("plan", encoding="utf-8")
            subprocess.run(["git", "-C", worktree_dir, "add", "."], check=True)
            subprocess.run(
                ["git", "-C", worktree_dir, "commit", "-q", "-m", "seed plan"],
                check=True,
            )

            removed = worktree.remove_worktree(repo_root, "task-001", "origin/main")

            self.assertTrue(removed)
            self.assertFalse(os.path.isdir(worktree_dir))

    def test_retains_implementation_worktree(self):
        """A worktree with a non-deferred change is retained."""
        with tempfile.TemporaryDirectory() as repo_root:
            _init_repo_with_origin(repo_root)
            worktree_dir = worktree.create_worktree(repo_root, "task-001", "origin/main")
            Path(worktree_dir, "src").mkdir(parents=True, exist_ok=True)
            Path(worktree_dir, "src", "code.py").write_text("code", encoding="utf-8")
            subprocess.run(["git", "-C", worktree_dir, "add", "."], check=True)
            subprocess.run(
                ["git", "-C", worktree_dir, "commit", "-q", "-m", "implement"],
                check=True,
            )

            removed = worktree.remove_worktree(repo_root, "task-001", "origin/main")

            self.assertFalse(removed)
            self.assertTrue(os.path.isdir(worktree_dir))

    def test_remove_worktree_uses_configured_base(self):
        """Cleanup classification uses the configured base branch, not main."""
        with tempfile.TemporaryDirectory() as repo_root:
            subprocess.run(["git", "init", "-q", repo_root], check=True)
            subprocess.run(
                ["git", "-C", repo_root, "config", "user.email", "test@example.com"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", repo_root, "config", "user.name", "Test User"],
                check=True,
            )
            Path(repo_root, "README.md").write_text("# test", encoding="utf-8")
            subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
            subprocess.run(
                ["git", "-C", repo_root, "commit", "-q", "-m", "init on main"],
                check=True,
            )
            subprocess.run(["git", "-C", repo_root, "branch", "dev"], check=True)
            dev_sha = subprocess.run(
                ["git", "-C", repo_root, "rev-parse", "dev"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            subprocess.run(
                ["git", "-C", repo_root, "update-ref", "refs/remotes/origin/dev", dev_sha],
                check=True,
            )

            worktree_dir = worktree.create_worktree(repo_root, "task-dev", "origin/dev")
            plan = Path(worktree_dir, "docs", "plans", "task-dev.md")
            plan.parent.mkdir(parents=True, exist_ok=True)
            plan.write_text("plan", encoding="utf-8")
            subprocess.run(["git", "-C", worktree_dir, "add", "."], check=True)
            subprocess.run(
                ["git", "-C", worktree_dir, "commit", "-q", "-m", "seed plan"],
                check=True,
            )

            removed = worktree.remove_worktree(repo_root, "task-dev", "origin/dev")
            self.assertTrue(removed)
            self.assertFalse(os.path.isdir(worktree_dir))


if __name__ == "__main__":
    unittest.main()
