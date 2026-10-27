"""Tests for aet-work worktree helpers."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from aet import worktree


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, check=True
    ).stdout


class TestMirrorLinkedPrd(unittest.TestCase):
    """R-8 and R-9: only the linked untracked PRD reaches the task worktree."""

    def test_mirror_copies_only_linked_untracked_prd(self):
        with tempfile.TemporaryDirectory() as repo_root:
            _init_repo_with_origin(repo_root)
            prds = Path(repo_root, "docs", "prds")
            prds.mkdir(parents=True)
            Path(prds, "linked-prd.md").write_text("linked", encoding="utf-8")
            Path(prds, "other-prd.md").write_text("other", encoding="utf-8")
            Path(repo_root, "docs", "adr").mkdir(parents=True)
            Path(repo_root, "docs", "adr", "099-draft.md").write_text("adr", encoding="utf-8")
            worktree_dir = worktree.create_worktree(repo_root, "x", "origin/main")
            task = _task_linking("docs/prds/linked-prd.md")

            mirrored = worktree.mirror_linked_prd(repo_root, worktree_dir, task)

            self.assertEqual(mirrored, "docs/prds/linked-prd.md")
            self.assertEqual(
                Path(worktree_dir, "docs", "prds", "linked-prd.md").read_text(encoding="utf-8"),
                "linked",
            )
            self.assertFalse(Path(worktree_dir, "docs", "prds", "other-prd.md").exists())
            self.assertFalse(Path(worktree_dir, "docs", "adr", "099-draft.md").exists())

    def test_mirrored_prd_absent_from_status_and_add_all(self):
        with tempfile.TemporaryDirectory() as repo_root:
            _init_repo_with_origin(repo_root)
            Path(repo_root, "docs", "prds").mkdir(parents=True)
            Path(repo_root, "docs", "prds", "linked-prd.md").write_text("linked", encoding="utf-8")
            worktree_dir = worktree.create_worktree(repo_root, "x", "origin/main")

            worktree.mirror_linked_prd(
                repo_root, worktree_dir, _task_linking("docs/prds/linked-prd.md")
            )

            self.assertEqual(_git("-C", worktree_dir, "status", "--porcelain"), "")
            _git("-C", worktree_dir, "add", "-A")
            self.assertEqual(_git("-C", worktree_dir, "diff", "--cached", "--name-only"), "")

    def test_root_status_still_lists_operator_draft(self):
        with tempfile.TemporaryDirectory() as repo_root:
            _init_repo_with_origin(repo_root)
            Path(repo_root, "docs", "prds").mkdir(parents=True)
            Path(repo_root, "docs", "prds", "linked-prd.md").write_text("linked", encoding="utf-8")
            worktree_dir = worktree.create_worktree(repo_root, "x", "origin/main")
            sibling_dir = worktree.create_worktree(repo_root, "y", "origin/main")
            Path(sibling_dir, "docs", "prds").mkdir(parents=True)
            Path(sibling_dir, "docs", "prds", "linked-prd.md").write_text("draft", encoding="utf-8")

            worktree.mirror_linked_prd(
                repo_root, worktree_dir, _task_linking("docs/prds/linked-prd.md")
            )

            root_status = _git("-C", repo_root, "status", "--porcelain", "-uall")
            self.assertIn("?? docs/prds/linked-prd.md", root_status)
            sibling_status = _git("-C", sibling_dir, "status", "--porcelain", "-uall")
            self.assertIn("?? docs/prds/linked-prd.md", sibling_status)

    def test_no_mirror_for_tracked_or_unlinked_prd(self):
        with tempfile.TemporaryDirectory() as repo_root:
            _init_repo_with_origin(repo_root)
            prd = Path(repo_root, "docs", "prds", "tracked-prd.md")
            prd.parent.mkdir(parents=True)
            prd.write_text("base", encoding="utf-8")
            _git("-C", repo_root, "add", ".")
            _git("-C", repo_root, "commit", "-q", "-m", "add prd")
            _git("-C", repo_root, "update-ref", "refs/remotes/origin/main", "HEAD")
            prd.write_text("modified", encoding="utf-8")
            Path(repo_root, "docs", "prds", "draft-prd.md").write_text("draft", encoding="utf-8")
            worktree_dir = worktree.create_worktree(repo_root, "x", "origin/main")

            tracked = worktree.mirror_linked_prd(
                repo_root, worktree_dir, _task_linking("docs/prds/tracked-prd.md")
            )
            unlinked = worktree.mirror_linked_prd(repo_root, worktree_dir, _task_linking(None))

            self.assertIsNone(tracked)
            self.assertIsNone(unlinked)
            self.assertEqual(
                Path(worktree_dir, "docs", "prds", "tracked-prd.md").read_text(encoding="utf-8"),
                "base",
            )
            self.assertFalse(Path(worktree_dir, "docs", "prds", "draft-prd.md").exists())

    def test_user_excludes_still_apply_after_mirror(self):
        with tempfile.TemporaryDirectory() as repo_root:
            _init_repo_with_origin(repo_root)
            user_ignore = Path(repo_root, "..", Path(repo_root).name + "-ignore").resolve()
            user_ignore.write_text("*.swp\n", encoding="utf-8")
            self.addCleanup(user_ignore.unlink)
            _git("-C", repo_root, "config", "core.excludesFile", str(user_ignore))
            Path(repo_root, "docs", "prds").mkdir(parents=True)
            Path(repo_root, "docs", "prds", "linked-prd.md").write_text("linked", encoding="utf-8")
            worktree_dir = worktree.create_worktree(repo_root, "x", "origin/main")

            worktree.mirror_linked_prd(
                repo_root, worktree_dir, _task_linking("docs/prds/linked-prd.md")
            )
            Path(worktree_dir, "notes.swp").write_text("swap", encoding="utf-8")

            self.assertEqual(_git("-C", worktree_dir, "status", "--porcelain"), "")


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


    def test_conflicting_refresh_halts_instead_of_crashing(self):
        """Regression: an existing worktree holding work halts cleanly on conflict."""
        with tempfile.TemporaryDirectory() as tmp:
            remote = os.path.join(tmp, "remote.git")
            repo_root = os.path.join(tmp, "repo")
            subprocess.run(["git", "init", "-q", "--bare", remote], check=True)
            subprocess.run(["git", "clone", "-q", remote, repo_root], check=True)
            subprocess.run(
                ["git", "-C", repo_root, "config", "user.email", "test@example.com"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", repo_root, "config", "user.name", "Test User"],
                check=True,
            )
            Path(repo_root, "shared.txt").write_text("old", encoding="utf-8")
            subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
            subprocess.run(
                ["git", "-C", repo_root, "commit", "-q", "-m", "old base"], check=True
            )
            subprocess.run(
                ["git", "-C", repo_root, "push", "-q", "origin", "HEAD:main"], check=True
            )
            subprocess.run(["git", "-C", repo_root, "branch", "-q", "-M", "main"], check=True)

            worktree_dir = worktree.create_worktree(repo_root, "task-001")

            # The task branch commits a conflicting change.
            Path(worktree_dir, "shared.txt").write_text("task", encoding="utf-8")
            subprocess.run(["git", "-C", worktree_dir, "add", "."], check=True)
            subprocess.run(
                ["git", "-C", worktree_dir, "commit", "-q", "-m", "task commit"],
                check=True,
            )
            task_sha = subprocess.run(
                ["git", "-C", repo_root, "rev-parse", "task-001"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()

            # The base advances with a conflicting change.
            Path(repo_root, "shared.txt").write_text("main", encoding="utf-8")
            subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
            subprocess.run(
                ["git", "-C", repo_root, "commit", "-q", "-m", "main advance"], check=True
            )
            subprocess.run(
                ["git", "-C", repo_root, "push", "-q", "origin", "main"], check=True
            )

            with self.assertRaises(worktree.WorktreeBlockedError):
                worktree.create_worktree(repo_root, "task-001")

            # The worktree and its commits survive the halt.
            self.assertTrue(os.path.isdir(worktree_dir))
            still = subprocess.run(
                ["git", "-C", repo_root, "rev-parse", "task-001"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            self.assertEqual(still, task_sha)


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

    def test_create_worktree_accepts_a_local_base_in_a_repo_with_no_remote(self):
        """A project with no remote must still get a worktree off its trunk."""
        with tempfile.TemporaryDirectory() as repo_root:
            self._init_repo(repo_root)
            Path(repo_root, "README.md").write_text("# test", encoding="utf-8")
            subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
            subprocess.run(
                ["git", "-C", repo_root, "commit", "-q", "-m", "init"], check=True
            )
            head = subprocess.run(
                ["git", "-C", repo_root, "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()

            worktree_dir = worktree.create_worktree(repo_root, "task-local", "main")

            self.assertTrue(os.path.isdir(worktree_dir))
            branch_sha = subprocess.run(
                ["git", "-C", repo_root, "rev-parse", "task-local"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            self.assertEqual(branch_sha, head)

    def test_create_worktree_treats_slashed_branch_name_as_a_local_base(self):
        """``fix/x`` is a branch, not remote ``fix`` + ref ``x`` — the leading
        segment is only a remote when it names a configured one."""
        with tempfile.TemporaryDirectory() as repo_root:
            self._init_repo(repo_root)
            Path(repo_root, "README.md").write_text("# test", encoding="utf-8")
            subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
            subprocess.run(
                ["git", "-C", repo_root, "commit", "-q", "-m", "init"], check=True
            )
            subprocess.run(
                ["git", "-C", repo_root, "branch", "fix/catalog-job-runtime"], check=True
            )
            base_sha = subprocess.run(
                ["git", "-C", repo_root, "rev-parse", "fix/catalog-job-runtime"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()

            worktree_dir = worktree.create_worktree(
                repo_root, "task-slashed", "fix/catalog-job-runtime"
            )

            self.assertTrue(os.path.isdir(worktree_dir))
            branch_sha = subprocess.run(
                ["git", "-C", repo_root, "rev-parse", "task-slashed"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            self.assertEqual(branch_sha, base_sha)

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

    def test_hygiene_passes_with_untracked_prd_and_modified_file(self):
        """No run step reads the root tree, so its edits do not halt a run."""
        with tempfile.TemporaryDirectory() as repo_root:
            self._init_repo_with_origin(repo_root)
            prd = Path(repo_root, "docs", "prds", "new-prd.md")
            prd.parent.mkdir(parents=True, exist_ok=True)
            prd.write_text("# PRD\n", encoding="utf-8")
            Path(repo_root, "README.md").write_text("# edited", encoding="utf-8")

            ok, msg = worktree.check_base_hygiene(repo_root, "main", "main")

            self.assertTrue(ok, msg)

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

    def test_hygiene_halts_when_ahead_with_code(self):
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

    def test_hygiene_passes_when_behind_origin(self):
        """Behind origin is the expected state after an origin-only flush."""
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

            self.assertTrue(ok, msg)

    def test_hygiene_passes_when_origin_gained_code(self):
        """A flush adds code to origin only; local main behind it carries nothing unpushed."""
        with tempfile.TemporaryDirectory() as repo_root:
            self._init_repo_with_origin(repo_root)
            Path(repo_root, "flushed.py").write_text("x", encoding="utf-8")
            subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
            subprocess.run(
                ["git", "-C", repo_root, "commit", "-q", "-m", "flushed task"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", repo_root, "update-ref", "refs/remotes/origin/main", "HEAD"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", repo_root, "reset", "-q", "--hard", "HEAD~1"],
                check=True,
            )

            ok, msg = worktree.check_base_hygiene(repo_root, "main", "main")

            self.assertTrue(ok, msg)


def _task_linking(prd: str | None) -> dict:
    """Return a task record whose spec links ``prd``."""
    frontmatter = {"source_prd": prd} if prd else {}
    return {"id": "x", "spec": {"frontmatter": frontmatter, "body": ""}}


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


class TestRenderTaskPlan(unittest.TestCase):
    def test_renders_plan_from_spec(self):
        """A task record with a spec renders its plan into the worktree."""
        with tempfile.TemporaryDirectory() as repo_root:
            worktree_dir = os.path.join(repo_root, ".worktrees", "x")
            task = {
                "id": "x",
                "spec": {
                    "frontmatter": {"id": "x", "size": "S", "pipeline": "standard"},
                    "title": "Plan X",
                    "body": "## Task List\n\n- [ ] one\n",
                    "tasks": ["- [ ] one"],
                },
            }
            rendered = worktree.render_task_plan(repo_root, worktree_dir, task)
            self.assertTrue(rendered)
            plan = Path(worktree_dir, "docs", "plans", "x.md")
            self.assertTrue(plan.exists())
            text = plan.read_text(encoding="utf-8")
            self.assertIn("id: x", text)
            self.assertIn("# Plan X", text)
            self.assertIn("- [ ] one", text)

    def test_legacy_fallback_copies_plan_file(self):
        """A task without a spec falls back to copying the referenced plan file."""
        with tempfile.TemporaryDirectory() as repo_root:
            worktree_dir = os.path.join(repo_root, ".worktrees", "x")
            plan = Path(repo_root, "docs", "plans", "x.md")
            plan.parent.mkdir(parents=True, exist_ok=True)
            plan.write_text("legacy plan", encoding="utf-8")
            task = {"id": "x", "plan_file": "docs/plans/x.md"}
            rendered = worktree.render_task_plan(repo_root, worktree_dir, task)
            self.assertTrue(rendered)
            self.assertEqual(
                Path(worktree_dir, "docs", "plans", "x.md").read_text(
                    encoding="utf-8"
                ),
                "legacy plan",
            )

    def test_noop_when_no_spec_or_plan_file(self):
        """render_task_plan returns False when there is nothing to render."""
        with tempfile.TemporaryDirectory() as repo_root:
            worktree_dir = os.path.join(repo_root, ".worktrees", "x")
            rendered = worktree.render_task_plan(
                repo_root, worktree_dir, {"id": "x"}
            )
            self.assertFalse(rendered)
            self.assertFalse(Path(worktree_dir, "docs", "plans", "x.md").exists())


class TestTeardownWorktree(unittest.TestCase):
    """Teardown cleanup for AET-generated deferred files plus refusal on real work."""

    def test_teardown_removes_worktree_with_deferred_untracked_plan(self):
        """An untracked deferred plan file is cleaned so removal succeeds."""
        with tempfile.TemporaryDirectory() as repo_root:
            _init_repo_with_origin(repo_root)
            worktree_dir = worktree.create_worktree(repo_root, "task-001", "origin/main")
            plan = Path(worktree_dir, "docs", "plans", "task-001.md")
            plan.parent.mkdir(parents=True, exist_ok=True)
            plan.write_text("plan", encoding="utf-8")

            result = worktree.teardown_worktree(repo_root, "task-001")

            self.assertTrue(result["removed"], result)
            self.assertFalse(os.path.isdir(worktree_dir))

    def test_teardown_refuses_non_deferred_untracked_file(self):
        """A non-deferred untracked file is real work and blocks teardown."""
        with tempfile.TemporaryDirectory() as repo_root:
            _init_repo_with_origin(repo_root)
            worktree_dir = worktree.create_worktree(repo_root, "task-001", "origin/main")
            Path(worktree_dir, "src").mkdir(parents=True, exist_ok=True)
            Path(worktree_dir, "src", "code.py").write_text("code", encoding="utf-8")

            result = worktree.teardown_worktree(repo_root, "task-001")

            self.assertFalse(result["removed"])
            self.assertTrue(os.path.isdir(worktree_dir))
            self.assertIn("src/code.py", result["obstructions"])

    def test_teardown_removes_worktree_with_committed_work(self):
        """Committed work lives on the branch ref and survives removal.

        Regression for teardown unioning the ``base..HEAD`` diff into its
        obstructions, which stranded every worktree that had done any work.
        """
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

            result = worktree.teardown_worktree(repo_root, "task-001")

            self.assertTrue(result["removed"], result)
            self.assertFalse(os.path.isdir(worktree_dir))
            # The commit survives on the branch the worktree was removed from.
            log = subprocess.run(
                ["git", "-C", repo_root, "log", "-1", "--format=%s", "task-001"],
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertEqual(log.stdout.strip(), "implement")


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


class TestBranchCheckedOutWorktrees(unittest.TestCase):
    def test_branch_checked_out_worktrees(self):
        """Each worktree that has the branch checked out is listed; others are not."""
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = os.path.realpath(os.path.join(tmp, "repo"))
            _init_repo_with_origin(repo_root)
            subprocess.run(["git", "-C", repo_root, "branch", "epic"], check=True)
            epic_wt = os.path.realpath(os.path.join(tmp, "epic-wt"))
            detached_wt = os.path.realpath(os.path.join(tmp, "detached-wt"))
            subprocess.run(
                ["git", "-C", repo_root, "worktree", "add", "-q", epic_wt, "epic"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", repo_root, "worktree", "add", "-q", "--detach", detached_wt, "main"],
                check=True,
            )

            self.assertEqual(worktree.branch_checked_out_worktrees(repo_root, "main"), [repo_root])
            self.assertEqual(worktree.branch_checked_out_worktrees(repo_root, "epic"), [epic_wt])
            self.assertEqual(worktree.branch_checked_out_worktrees(repo_root, "other"), [])
